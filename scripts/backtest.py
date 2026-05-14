"""Replay recorded book_ticks through the strategy with different parameter values.

For each market in the journal:
  1. Pull its true resolution from gamma API (winner = UP/DOWN).
  2. Walk its ticks in chronological order (decreasing t_remaining).
  3. For each parameter combination, find the first tick that satisfies all
     decision rules and "place" a hypothetical BUY at max_entry_price.
  4. Score that BUY against the resolution: win = +(1 - price - fee), loss = -(price + fee).

Outputs a sweep table so we can pick optimal `seconds_before_close`,
`max_entry_price`, and `spot_confidence_bps` BEFORE risking real money.
"""
from __future__ import annotations

import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import requests

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from bot.config import load_config  # noqa: E402

cfg = load_config()
DB = cfg.db_path
GAMMA = cfg.gamma_host

FEE_RATE = 0.07          # verified empirically against Bonereaper trades


@dataclass(frozen=True)
class Tick:
    t_remaining: float
    yes_ask: Optional[float]
    no_ask: Optional[float]
    yes_buyable_at_cap: Optional[float]
    no_buyable_at_cap: Optional[float]
    spot_mid: Optional[float]
    spot_at_open: Optional[float]


def fetch_resolution(slug: str) -> Optional[str]:
    """Return 'UP' / 'DOWN' / None (if not yet resolved)."""
    try:
        r = requests.get(f"{GAMMA}/markets", params={"slug": slug}, timeout=10)
        if r.status_code != 200:
            return None
        data = r.json()
        if not data:
            return None
        m = data[0]
        if not m.get("closed"):
            return None
        outcome = m.get("outcomePrices")
        if isinstance(outcome, str):
            import json
            outcome = json.loads(outcome)
        if not outcome:
            return None
        return "UP" if float(outcome[0]) > 0.5 else "DOWN"
    except Exception:
        return None


def infer_resolution_from_ticks(ticks: list[Tick]) -> Optional[str]:
    """Fallback when gamma hasn't published the resolution yet.

    Look at the LATEST tick (smallest t_remaining). If one side's ask is near 1.0
    and the other near 0.0, the near-1.0 side won.
    """
    if not ticks:
        return None
    # Find the tick with smallest t_remaining (closest to resolution)
    last = min(ticks, key=lambda t: t.t_remaining)
    if last.t_remaining > 30:
        return None  # too far from resolution to infer
    # In a converged market: winner ask ~0.99-1.00, loser ask ~0.00-0.02
    if last.yes_ask is not None and last.yes_ask >= 0.95 and (last.no_ask is None or last.no_ask <= 0.10):
        return "UP"
    if last.no_ask is not None and last.no_ask >= 0.95 and (last.yes_ask is None or last.yes_ask <= 0.10):
        return "DOWN"
    return None


def simulate_one_market(
    ticks: list[Tick], winner: str,
    *, seconds_before_close: float, max_entry_price: float,
    low_price_floor: float, min_book_size: float,
    spot_confidence_bps: float,
) -> Optional[dict]:
    """Walk ticks (decreasing t_remaining) and find first BUY entry. Return dict or None."""
    ticks_sorted = sorted(ticks, key=lambda t: -t.t_remaining)
    for t in ticks_sorted:
        if t.t_remaining > seconds_before_close:
            continue
        if t.t_remaining <= 0:
            break

        yes_ok = (t.yes_ask is not None
                  and low_price_floor <= t.yes_ask <= max_entry_price
                  and (t.yes_buyable_at_cap or 0) >= min_book_size)
        no_ok = (t.no_ask is not None
                 and low_price_floor <= t.no_ask <= max_entry_price
                 and (t.no_buyable_at_cap or 0) >= min_book_size)
        if yes_ok == no_ok:  # both or neither
            continue

        winner_side = "UP" if yes_ok else "DOWN"
        winner_book_ask = t.yes_ask if yes_ok else t.no_ask

        if t.spot_at_open is None or t.spot_mid is None or t.spot_at_open <= 0:
            continue
        move_bps = (t.spot_mid - t.spot_at_open) / t.spot_at_open * 10_000
        if abs(move_bps) < spot_confidence_bps:
            continue
        spot_pick = "UP" if move_bps > 0 else "DOWN"
        if spot_pick != winner_side:
            continue

        # BUY would have fired here
        # Effective entry price: we'd post at max_entry_price; assume filled at the ask
        entry_price = winner_book_ask
        won = (winner_side == winner)
        fee = FEE_RATE * (1 - entry_price)
        # Per-share PnL
        if won:
            pnl_per_share = (1 - entry_price) - fee * entry_price
        else:
            pnl_per_share = -entry_price - fee * entry_price
        return {
            "t_at_entry": t.t_remaining,
            "side": winner_side,
            "entry_price": entry_price,
            "won": won,
            "pnl_per_share": pnl_per_share,
        }
    return None


def load_data() -> dict[str, list[Tick]]:
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    out: dict[str, list[Tick]] = {}
    for r in conn.execute(
        "SELECT * FROM book_ticks ORDER BY market_slug, t_remaining DESC"
    ):
        out.setdefault(r["market_slug"], []).append(Tick(
            t_remaining=r["t_remaining"],
            yes_ask=r["yes_best_ask"],
            no_ask=r["no_best_ask"],
            yes_buyable_at_cap=r["yes_buyable_at_cap"],
            no_buyable_at_cap=r["no_buyable_at_cap"],
            spot_mid=r["spot_mid"],
            spot_at_open=r["spot_at_open"],
        ))
    return out


def resolve_all(by_market: dict[str, list[Tick]]) -> dict[str, str]:
    """Resolve every market via gamma; fall back to tick inference."""
    out = {}
    print(f"Resolving {len(by_market)} markets ...")
    for slug, ticks in by_market.items():
        winner = fetch_resolution(slug)
        if winner is None:
            winner = infer_resolution_from_ticks(ticks)
        if winner:
            out[slug] = winner
    print(f"  Resolved {len(out)}/{len(by_market)} markets")
    return out


def sweep(by_market: dict[str, list[Tick]], resolutions: dict[str, str]) -> None:
    """Run the parameter sweep and print results."""
    seconds_options = [60, 90, 120, 180, 240, 300]
    cap_options = [0.90, 0.92, 0.95, 0.97]
    spot_options = [3, 5, 10]
    floor = 0.55
    min_size = 5.0
    size_per_trade = 5.0  # shares — matches cfg.order_size_shares

    print(f"\n=== Parameter sweep ===")
    print(f"Markets: {len(by_market)}, resolutions known: {len(resolutions)}")
    print(f"Per-trade size: {size_per_trade} shares")
    print()
    print(f"{'sec_close':>9s} {'cap':>5s} {'spot_bps':>9s}  "
          f"{'fires':>5s}  {'wins':>5s}  {'WR':>6s}  "
          f"{'tot_pnl':>9s}  {'avg_pnl':>9s}  {'avg_entry':>9s}  {'avg_t_entry':>11s}")

    rows = []
    for sec in seconds_options:
        for cap in cap_options:
            for spot in spot_options:
                fires = wins = 0
                tot_pnl = 0.0
                entry_prices = []
                entry_times = []
                for slug, ticks in by_market.items():
                    if slug not in resolutions:
                        continue
                    winner = resolutions[slug]
                    sim = simulate_one_market(
                        ticks, winner,
                        seconds_before_close=sec,
                        max_entry_price=cap,
                        low_price_floor=floor,
                        min_book_size=min_size,
                        spot_confidence_bps=spot,
                    )
                    if sim is None:
                        continue
                    fires += 1
                    if sim["won"]:
                        wins += 1
                    tot_pnl += sim["pnl_per_share"] * size_per_trade
                    entry_prices.append(sim["entry_price"])
                    entry_times.append(sim["t_at_entry"])

                wr = (100 * wins / fires) if fires else 0.0
                avg_pnl = tot_pnl / fires if fires else 0
                avg_entry = sum(entry_prices) / len(entry_prices) if entry_prices else 0
                avg_t = sum(entry_times) / len(entry_times) if entry_times else 0
                rows.append({
                    "sec": sec, "cap": cap, "spot": spot,
                    "fires": fires, "wins": wins, "wr": wr,
                    "tot_pnl": tot_pnl, "avg_pnl": avg_pnl,
                    "avg_entry": avg_entry, "avg_t": avg_t,
                })
                print(f"{sec:9d} {cap:5.2f} {spot:9d}  "
                      f"{fires:5d}  {wins:5d}  {wr:5.1f}%  "
                      f"${tot_pnl:+8.4f}  ${avg_pnl:+8.4f}  "
                      f"{avg_entry:9.4f}  {avg_t:10.1f}s")

    # Best by total PnL (and by avg PnL for fires>=3)
    print()
    rows_with_signal = [r for r in rows if r["fires"] >= 3]
    if rows_with_signal:
        best = max(rows_with_signal, key=lambda r: r["tot_pnl"])
        best_avg = max(rows_with_signal, key=lambda r: r["avg_pnl"])
        print(f"BEST total PnL (with >=3 fires): "
              f"sec={best['sec']} cap={best['cap']} spot={best['spot']} "
              f"-> {best['fires']} trades, WR={best['wr']:.1f}%, "
              f"tot=${best['tot_pnl']:+.4f}, avg=${best['avg_pnl']:+.4f}")
        print(f"BEST avg  PnL (with >=3 fires): "
              f"sec={best_avg['sec']} cap={best_avg['cap']} spot={best_avg['spot']} "
              f"-> {best_avg['fires']} trades, WR={best_avg['wr']:.1f}%, "
              f"tot=${best_avg['tot_pnl']:+.4f}, avg=${best_avg['avg_pnl']:+.4f}")


def main() -> int:
    if not DB.exists():
        print(f"No journal at {DB}.")
        return 1
    by_market = load_data()
    if not by_market:
        print("No book_ticks. Run the dry-run with probe mode first.")
        return 1
    print(f"Loaded {sum(len(v) for v in by_market.values())} ticks across {len(by_market)} markets.")

    resolutions = resolve_all(by_market)
    if not resolutions:
        print("No resolutions available — can't backtest. Markets may not be closed yet.")
        return 1

    sweep(by_market, resolutions)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
