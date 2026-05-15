"""Read-only real-time dashboard backend for polybot.

DESIGN: this process is **strictly decoupled** from the trading loop. It never
writes to trades.db, never imports the trading loop, and never holds a write
lock — it opens the SQLite journal read-only and tails it. The bot can be
running live the whole time; the worst this can do is read a slightly stale row.

Data flow:

    trades.db  ──poll(0.5s)──►  in-memory tail cursors
                                      │
                                      ├─ broadcast new decisions/orders/ticks
                                      │  to every connected WebSocket client
                                      │
    gamma/CLOB API ──resolve(8s)──►  realised P&L (BUY decisions enriched with
                                     market outcomes; formula single-sourced
                                     with scripts/analyze_dry_run.py)

The frontend gets a full `snapshot` on connect, then incremental deltas.
"""
from __future__ import annotations

import asyncio
import json
import sqlite3
import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from bot.account import fetch_pusd_balance  # noqa: E402
from bot.auth import _read_env_var           # noqa: E402
from bot.config import load_config          # noqa: E402
from bot.markets import fetch_resolution    # noqa: E402

CFG = load_config()
DB_PATH = CFG.db_path

# Fee model — mirrors bot.markets.fee_for_buy defaults and scripts/analyze_dry_run.py.
# Kept as constants here so a closed market (where we no longer hold a LiveMarket
# object) still scores P&L identically to the offline analysis tooling.
FEE_RATE = 0.07
FEE_EXP = 1

POLL_INTERVAL_SEC = 0.5      # how often we tail the journal for new rows
STATS_INTERVAL_SEC = 8.0     # how often we re-resolve outcomes / recompute P&L
MARKETS_INTERVAL_SEC = 12.0  # how often we refresh the open-market clock
WALLET_INTERVAL_SEC = 20.0   # how often we read on-chain pUSD (one eth_call)
RECENT_LIMIT = 200           # rows of history sent in the initial snapshot


# --------------------------------------------------------------------------- #
# SQLite read-only access                                                      #
# --------------------------------------------------------------------------- #

def _ro_conn() -> sqlite3.Connection:
    """Open the journal read-only. Never blocks the bot's writes."""
    conn = sqlite3.connect(
        f"file:{DB_PATH}?mode=ro", uri=True, timeout=2.0,
    )
    conn.row_factory = sqlite3.Row
    return conn


def _rows(sql: str, params: tuple = ()) -> list[dict]:
    """Run a read query, tolerating a transient lock from the bot's writer."""
    for attempt in range(4):
        try:
            with _ro_conn() as c:
                return [dict(r) for r in c.execute(sql, params).fetchall()]
        except sqlite3.OperationalError as e:
            if "locked" in str(e) and attempt < 3:
                time.sleep(0.05)
                continue
            raise
        except sqlite3.OperationalError:
            # DB not created yet (bot never run) — behave as empty.
            return []
    return []


# --------------------------------------------------------------------------- #
# P&L — single-sourced with scripts/analyze_dry_run.py                          #
# --------------------------------------------------------------------------- #

def _trade_pnl(side: str, price: float, size: float, winner: str) -> dict:
    """Net/gross P&L for one BUY contract block, after taker fee.

    Identical accounting to scripts/analyze_dry_run.py:
      win  -> gross = (1 - price) * size
      loss -> gross = -price * size
      fee  -> FEE_RATE * (1 - price)^FEE_EXP * (size * price)   [notional-scaled]
    """
    size = size or 1.0
    fee = FEE_RATE * (1.0 - price) ** FEE_EXP * size * price
    if side == winner:
        gross = (1.0 - price) * size
    else:
        gross = -price * size
    return {"gross": gross, "fee": fee, "net": gross - fee, "won": side == winner}


# --------------------------------------------------------------------------- #
# Shared state                                                                 #
# --------------------------------------------------------------------------- #

class State:
    """In-memory mirror of what we've tailed + derived stats."""

    def __init__(self) -> None:
        self.last_decision_id = 0
        self.last_order_id = 0
        self.last_tick_id = 0
        # condition_id -> "UP" | "DOWN" | None (None = asked, not resolved yet)
        self.resolutions: dict[str, Optional[str]] = {}
        self.stats: dict[str, Any] = {}
        self.equity: list[dict] = []
        self.markets: list[dict] = []
        self.latest_tick: Optional[dict] = None
        self.wallet: dict[str, Any] = {}

    def config_view(self) -> dict:
        return {
            "max_entry_price": CFG.max_entry_price,
            "low_price_floor": CFG.low_price_floor,
            "seconds_before_close": CFG.seconds_before_close,
            "min_t_remaining_seconds": CFG.min_t_remaining_seconds,
            "spot_confidence_bps": CFG.spot_confidence_bps,
            "order_size_shares": CFG.order_size_shares,
            "daily_loss_cap_usd": CFG.daily_loss_cap_usd,
            "max_open_positions": CFG.max_open_positions,
        }


STATE = State()


# --------------------------------------------------------------------------- #
# WebSocket connection manager                                                 #
# --------------------------------------------------------------------------- #

class Hub:
    def __init__(self) -> None:
        self._clients: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def join(self, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._clients.add(ws)

    async def leave(self, ws: WebSocket) -> None:
        async with self._lock:
            self._clients.discard(ws)

    async def broadcast(self, msg: dict) -> None:
        if not self._clients:
            return
        payload = json.dumps(msg, default=str)
        async with self._lock:
            dead: list[WebSocket] = []
            for ws in self._clients:
                try:
                    await ws.send_text(payload)
                except Exception:
                    dead.append(ws)
            for ws in dead:
                self._clients.discard(ws)


HUB = Hub()


# --------------------------------------------------------------------------- #
# Snapshot + stats computation                                                 #
# --------------------------------------------------------------------------- #

def _build_pnl(buys: list[dict], mode_filter: Optional[int]) -> dict:
    """Aggregate realised P&L over BUY decisions, using cached resolutions."""
    rows = buys if mode_filter is None else [b for b in buys if b["dry_run"] == mode_filter]
    wins = losses = unresolved = 0
    gross = net = fees = 0.0
    for b in rows:
        winner = STATE.resolutions.get(b["condition_id"])
        if winner is None:
            unresolved += 1
            continue
        r = _trade_pnl(b["side"], b["price"], b["size"], winner)
        gross += r["gross"]
        net += r["net"]
        fees += r["fee"]
        wins += int(r["won"])
        losses += int(not r["won"])
    resolved = wins + losses
    return {
        "buys": len(rows),
        "resolved": resolved,
        "unresolved": unresolved,
        "wins": wins,
        "losses": losses,
        "win_rate": (wins / resolved) if resolved else None,
        "gross": round(gross, 4),
        "net": round(net, 4),
        "fees": round(fees, 4),
        "per_trade": round(net / resolved, 4) if resolved else None,
    }


def _recompute_stats() -> None:
    """Recompute P&L + equity curve from all BUY decisions (cheap, no I/O)."""
    buys = _rows(
        "SELECT id, ts, market_slug, condition_id, side, price, size, dry_run "
        "FROM decisions WHERE action='BUY' ORDER BY ts ASC"
    )
    counts = _rows("SELECT action, COUNT(*) n FROM decisions GROUP BY action")
    decision_counts = {r["action"]: r["n"] for r in counts}

    equity: list[dict] = []
    cum = 0.0
    for b in buys:
        winner = STATE.resolutions.get(b["condition_id"])
        if winner is None:
            continue
        r = _trade_pnl(b["side"], b["price"], b["size"], winner)
        cum += r["net"]
        equity.append({
            "ts": b["ts"],
            "slug": b["market_slug"],
            "side": b["side"],
            "price": b["price"],
            "won": r["won"],
            "net": round(r["net"], 4),
            "cum_net": round(cum, 4),
            "dry_run": b["dry_run"],
        })

    STATE.equity = equity
    STATE.stats = {
        "all": _build_pnl(buys, None),
        "live": _build_pnl(buys, 0),
        "dry": _build_pnl(buys, 1),
        "decision_counts": decision_counts,
        "resolved_markets": sum(1 for v in STATE.resolutions.values() if v),
        "tracked_markets": len(STATE.resolutions),
        "updated_ts": time.time(),
    }


def _open_positions() -> list[dict]:
    """BUY decisions whose market has not resolved yet — what we're 'holding'."""
    buys = _rows(
        "SELECT ts, market_slug, condition_id, side, price, size, dry_run "
        "FROM decisions WHERE action='BUY' ORDER BY ts DESC"
    )
    out: list[dict] = []
    seen: set[str] = set()
    for b in buys:
        if STATE.resolutions.get(b["condition_id"]):
            continue
        slug = b["market_slug"]
        if slug in seen:           # one position per market (latest BUY wins)
            continue
        seen.add(slug)
        # btc-updown-5m-1778841300 -> window end = start + minutes*60
        end_ts = None
        try:
            parts = slug.split("-")
            end_ts = int(parts[3]) + int(parts[2].rstrip("m")) * 60
        except (IndexError, ValueError):
            pass
        out.append({**b, "end_ts": end_ts})
    return out


def _wallet_addrs() -> dict:
    """Resolve the active funder/signer pair without ever exposing keys.

    Mirrors bot.auth.make_client: Path B (deposit wallet) if MM_* is configured,
    else legacy Path A (EOA).
    """
    mm = _read_env_var("MM_WALLET_ADDRESS")
    deposit = _read_env_var("DEPOSIT_WALLET")
    if mm and deposit and _read_env_var("MM_PRIVATE_KEY"):
        return {"path": "B", "deposit": deposit, "eoa": mm}
    eoa = _read_env_var("WALLET_ADDRESS")
    return {"path": "A", "deposit": eoa, "eoa": eoa}


def _compute_wallet() -> dict:
    """On-chain pUSD + cost basis of open positions. Networked — call off-thread."""
    a = _wallet_addrs()
    positions = _open_positions()
    # Cost basis of signalled-open positions (orders mostly fail to fill in
    # this account, so this is the at-risk notional of open BUY signals).
    open_value = sum((p["price"] or 0) * (p["size"] or 0) for p in positions)
    cash: Optional[float] = None
    err: Optional[str] = None
    if a["deposit"]:
        try:
            cash = float(fetch_pusd_balance(a["deposit"]))
        except Exception as e:
            err = str(e)
    total = (cash or 0.0) + open_value
    return {
        "path": a["path"],
        "deposit": a["deposit"],
        "eoa": a["eoa"],
        "pusd_cash": round(cash, 2) if cash is not None else None,
        "open_value": round(open_value, 2),
        "total_equity": round(total, 2) if cash is not None else None,
        "error": err,
        "updated_ts": time.time(),
    }


def build_snapshot() -> dict:
    decisions = _rows(
        "SELECT id, ts, market_slug, t_remaining, action, side, price, size, "
        "reason, yes_best_ask, yes_best_bid, no_best_ask, no_best_bid, "
        "spot_mid, spot_at_open, dry_run FROM decisions "
        f"ORDER BY id DESC LIMIT {RECENT_LIMIT}"
    )
    orders = _rows(
        "SELECT id, ts, market_slug, side, price, size, fill_price, fill_size, "
        "fee_paid, order_id, status, error, dry_run FROM orders "
        "ORDER BY id DESC LIMIT 50"
    )
    return {
        "type": "snapshot",
        "data": {
            "config": STATE.config_view(),
            "stats": STATE.stats,
            "equity": STATE.equity,
            "decisions": list(reversed(decisions)),  # chronological for the feed
            "orders": orders,
            "positions": _open_positions(),
            "markets": STATE.markets,
            "wallet": STATE.wallet,
            "latest_tick": STATE.latest_tick,
            "server_ts": time.time(),
            "db_path": str(DB_PATH),
        },
    }


# --------------------------------------------------------------------------- #
# Background pollers                                                            #
# --------------------------------------------------------------------------- #

async def _init_cursors() -> None:
    for tbl, attr in (
        ("decisions", "last_decision_id"),
        ("orders", "last_order_id"),
        ("book_ticks", "last_tick_id"),
    ):
        rows = _rows(f"SELECT COALESCE(MAX(id),0) m FROM {tbl}")
        setattr(STATE, attr, rows[0]["m"] if rows else 0)


async def db_poller() -> None:
    """Tail the journal; broadcast every new row as it lands."""
    while True:
        try:
            new_dec = _rows(
                "SELECT id, ts, market_slug, t_remaining, action, side, price, "
                "size, reason, yes_best_ask, yes_best_bid, no_best_ask, "
                "no_best_bid, spot_mid, spot_at_open, dry_run FROM decisions "
                "WHERE id > ? ORDER BY id ASC", (STATE.last_decision_id,),
            )
            for d in new_dec:
                STATE.last_decision_id = d["id"]
                # New traded market we haven't tried to resolve yet.
                if d["action"] == "BUY":
                    STATE.resolutions.setdefault(d["condition_id"], None)
                await HUB.broadcast({"type": "decision", "data": d})

            new_ord = _rows(
                "SELECT id, ts, market_slug, side, price, size, fill_price, "
                "fill_size, fee_paid, order_id, status, error, dry_run "
                "FROM orders WHERE id > ? ORDER BY id ASC", (STATE.last_order_id,),
            )
            for o in new_ord:
                STATE.last_order_id = o["id"]
                await HUB.broadcast({"type": "order", "data": o})

            new_tick = _rows(
                "SELECT id, ts, market_slug, t_remaining, yes_best_ask, "
                "yes_best_bid, no_best_ask, no_best_bid, yes_buyable_at_cap, "
                "no_buyable_at_cap, spot_mid, spot_at_open FROM book_ticks "
                "WHERE id > ? ORDER BY id ASC", (STATE.last_tick_id,),
            )
            for t in new_tick:
                STATE.last_tick_id = t["id"]
                STATE.latest_tick = t
            if new_tick:
                await HUB.broadcast({"type": "tick", "data": STATE.latest_tick})
        except Exception as e:
            print(f"[poller] {e}", flush=True)
        await asyncio.sleep(POLL_INTERVAL_SEC)


async def stats_refresher() -> None:
    """Resolve outcomes for traded markets, recompute P&L, broadcast."""
    while True:
        try:
            pending = [
                cid for cid, v in list(STATE.resolutions.items()) if v is None
            ]
            for cid in pending:
                try:
                    outcome = await asyncio.to_thread(fetch_resolution, CFG, cid)
                except Exception:
                    outcome = None
                if outcome:
                    STATE.resolutions[cid] = outcome
            _recompute_stats()
            await HUB.broadcast({
                "type": "stats",
                "data": {"stats": STATE.stats, "equity": STATE.equity},
            })
        except Exception as e:
            print(f"[stats] {e}", flush=True)
        await asyncio.sleep(STATS_INTERVAL_SEC)


async def markets_refresher() -> None:
    """Refresh the open-market clock without dragging in the trading loop."""
    while True:
        try:
            from bot.markets import discover_open_markets
            ms = await asyncio.to_thread(discover_open_markets, CFG)
            STATE.markets = [
                {
                    "slug": m.slug,
                    "question": m.question,
                    "window_minutes": m.window_minutes,
                    "start_ts": m.start_ts,
                    "end_ts": m.end_ts,
                }
                for m in ms
            ]
            await HUB.broadcast({"type": "markets", "data": STATE.markets})
        except Exception as e:
            print(f"[markets] {e}", flush=True)
        await asyncio.sleep(MARKETS_INTERVAL_SEC)


async def wallet_refresher() -> None:
    """Read on-chain pUSD + open-position value; broadcast wallet/equity."""
    while True:
        try:
            STATE.wallet = await asyncio.to_thread(_compute_wallet)
            await HUB.broadcast({"type": "wallet", "data": STATE.wallet})
        except Exception as e:
            print(f"[wallet] {e}", flush=True)
        await asyncio.sleep(WALLET_INTERVAL_SEC)


# --------------------------------------------------------------------------- #
# App                                                                          #
# --------------------------------------------------------------------------- #

@asynccontextmanager
async def lifespan(app: FastAPI):
    await _init_cursors()
    # Seed resolution keys for every BUY already in the journal.
    for b in _rows("SELECT DISTINCT condition_id FROM decisions WHERE action='BUY'"):
        STATE.resolutions.setdefault(b["condition_id"], None)
    _recompute_stats()
    tasks = [
        asyncio.create_task(db_poller()),
        asyncio.create_task(stats_refresher()),
        asyncio.create_task(markets_refresher()),
        asyncio.create_task(wallet_refresher()),
    ]
    try:
        yield
    finally:
        for t in tasks:
            t.cancel()


app = FastAPI(title="polybot dashboard", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # local-only tool; tighten if ever exposed
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/snapshot")
async def api_snapshot() -> JSONResponse:
    return JSONResponse(build_snapshot()["data"])


@app.get("/api/health")
async def api_health() -> dict:
    return {"ok": True, "db": str(DB_PATH), "clients": len(HUB._clients)}


@app.websocket("/ws")
async def ws(ws: WebSocket) -> None:
    await HUB.join(ws)
    try:
        await ws.send_text(json.dumps(build_snapshot(), default=str))
        while True:
            # We don't expect client messages; this keeps the socket alive
            # and lets us notice disconnects promptly.
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        await HUB.leave(ws)


# Serve the built SPA if it exists (production single-process mode).
_DIST = Path(__file__).resolve().parent / "frontend" / "dist"
if _DIST.is_dir():
    app.mount("/", StaticFiles(directory=str(_DIST), html=True), name="spa")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8787, log_level="warning")
