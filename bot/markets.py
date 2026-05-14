"""Discover currently-open BTC up/down markets on Polymarket.

The slugs follow the pattern btc-updown-{Nm}-{unix_ts_window_start}.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

import requests

from .config import Config


@dataclass(frozen=True)
class LiveMarket:
    slug: str
    condition_id: str
    question: str
    window_minutes: int                # 5 or 15
    start_ts: int                      # unix seconds — window OPEN
    end_ts: int                        # unix seconds — window CLOSE / resolution
    yes_token_id: str                  # "Up"
    no_token_id: str                   # "Down"
    tick_size: float
    neg_risk: bool
    fee_rate: float                    # from feeSchedule.rate, e.g. 0.07
    fee_exponent: int                  # from feeSchedule.exponent

    def t_remaining(self, now: Optional[float] = None) -> float:
        return self.end_ts - (now if now is not None else time.time())


def _fetch_market(cfg: Config, slug: str) -> Optional[dict]:
    try:
        r = requests.get(f"{cfg.gamma_host}/markets", params={"slug": slug}, timeout=5)
    except requests.RequestException:
        return None
    if r.status_code != 200:
        return None
    data = r.json()
    if not isinstance(data, list) or not data:
        return None
    return data[0]


def _parse(raw: dict) -> Optional[LiveMarket]:
    """Convert a gamma API market dict to a LiveMarket. Returns None if unparseable."""
    slug = raw.get("slug", "")
    parts = slug.split("-")
    # btc-updown-15m-1778705100  → ["btc", "updown", "15m", "1778705100"]
    if len(parts) != 4 or parts[0] != "btc" or parts[1] != "updown":
        return None
    try:
        window_minutes = int(parts[2].rstrip("m"))
        start_ts = int(parts[3])
    except ValueError:
        return None
    end_ts = start_ts + window_minutes * 60

    tokens = raw.get("clobTokenIds")
    if isinstance(tokens, str):
        import json
        tokens = json.loads(tokens)
    if not tokens or len(tokens) != 2:
        return None
    yes_id, no_id = tokens[0], tokens[1]

    fee = raw.get("feeSchedule") or {}
    return LiveMarket(
        slug=slug,
        condition_id=raw["conditionId"],
        question=raw.get("question", ""),
        window_minutes=window_minutes,
        start_ts=start_ts,
        end_ts=end_ts,
        yes_token_id=yes_id,
        no_token_id=no_id,
        tick_size=float(raw.get("orderPriceMinTickSize", 0.01)),
        neg_risk=bool(raw.get("negRisk", False)),
        fee_rate=float(fee.get("rate", 0.07)),
        fee_exponent=int(fee.get("exponent", 1)),
    )


def discover_open_markets(cfg: Config, now: Optional[float] = None) -> list[LiveMarket]:
    """Probe gamma API for currently-open btc-updown 5m and 15m markets near `now`.

    Strategy: compute the candidate window-start timestamps (rounded to 5 and 15-min
    boundaries) within +/- a few slots, then GET each by slug.
    """
    now = int(now if now is not None else time.time())
    slot15 = (now // 900) * 900
    slot5 = (now // 300) * 300

    candidate_slugs: list[str] = []
    # ±2 slots in each direction is plenty (covers the currently-open and the next one or two)
    for off in range(-1, 4):
        candidate_slugs.append(f"btc-updown-15m-{slot15 + off * 900}")
        candidate_slugs.append(f"btc-updown-5m-{slot5 + off * 300}")

    out: list[LiveMarket] = []
    for slug in candidate_slugs:
        raw = _fetch_market(cfg, slug)
        if not raw:
            continue
        if not raw.get("acceptingOrders") or raw.get("closed"):
            continue
        m = _parse(raw)
        if not m:
            continue
        # Only keep markets whose window has not yet closed
        if m.end_ts > now:
            out.append(m)

    # Sort soonest-resolving first
    out.sort(key=lambda m: m.end_ts)
    return out


def fee_for_buy(market: LiveMarket, price: float) -> float:
    """Taker fee as a fraction of notional, for a BUY at `price`.

    Verified empirically against Bonereaper's on-chain trades:
      fee_rate * (1 - price) ^ exponent
    """
    return market.fee_rate * (1.0 - price) ** market.fee_exponent


def fetch_resolution(cfg: Config, condition_id: str) -> Optional[str]:
    """Return 'UP' / 'DOWN' if the market has resolved, else None.

    Uses the CLOB API (clob.polymarket.com/markets/<condition_id>) because gamma's
    slug-based lookup returns empty for short-duration markets after they close.
    """
    try:
        r = requests.get(f"{cfg.clob_host}/markets/{condition_id}", timeout=5)
    except requests.RequestException:
        return None
    if r.status_code != 200:
        return None
    m = r.json()
    if not isinstance(m, dict) or not m.get("closed"):
        return None
    for t in m.get("tokens", []):
        if not isinstance(t, dict):
            continue
        if t.get("winner") is True:
            outcome = (t.get("outcome") or "").lower()
            if outcome == "up":
                return "UP"
            if outcome == "down":
                return "DOWN"
    return None
