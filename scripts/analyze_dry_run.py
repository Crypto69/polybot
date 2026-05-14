"""Post-mortem analysis of the dry-run journal.

For each market we observed:
  1. Look up the actual resolution from gamma API (waits until window ends).
  2. For every BUY decision, simulate the trade: fee, payoff, P/L.
  3. Aggregate: hypothetical win rate, gross/net edge, per-trade $ outcome.
"""
from __future__ import annotations

import json
import sqlite3
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from bot.config import load_config  # noqa: E402

cfg = load_config()
DB = cfg.db_path
GAMMA = cfg.gamma_host


def fetch_resolution(slug: str) -> dict | None:
    """Return the resolved market record, or None if it's not yet resolved."""
    r = requests.get(f"{GAMMA}/markets", params={"slug": slug}, timeout=10)
    if r.status_code != 200:
        return None
    data = r.json()
    if not isinstance(data, list) or not data:
        return None
    m = data[0]
    if not m.get("closed"):
        return None
    # outcomePrices is a JSON-string list like '["1","0"]' — first is YES, second is NO
    outcome = m.get("outcomePrices")
    if isinstance(outcome, str):
        try:
            outcome = json.loads(outcome)
        except Exception:
            return None
    return {
        "slug": slug,
        "winner": "UP" if outcome and float(outcome[0]) > 0.5 else "DOWN",
        "outcome_raw": outcome,
    }


def main() -> int:
    if not DB.exists():
        print(f"No journal at {DB}. Run the bot first.")
        return 1

    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row

    # Distinct markets that we made any decision on
    market_rows = conn.execute(
        "SELECT DISTINCT market_slug FROM decisions"
    ).fetchall()
    print(f"Markets touched: {len(market_rows)}")

    # Fetch resolutions
    resolutions = {}
    for r in market_rows:
        slug = r["market_slug"]
        rez = fetch_resolution(slug)
        if rez:
            resolutions[slug] = rez["winner"]
    print(f"Resolved markets: {len(resolutions)}")

    # Decision summary
    print("\n=== Decision summary (all markets) ===")
    for r in conn.execute(
        "SELECT action, COUNT(*) AS n FROM decisions GROUP BY action ORDER BY n DESC"
    ):
        print(f"  {r['action']:5s}  {r['n']}")

    print("\n=== SKIP reasons ===")
    for r in conn.execute(
        "SELECT reason, COUNT(*) AS n FROM decisions WHERE action='SKIP' "
        "GROUP BY reason ORDER BY n DESC LIMIT 15"
    ):
        # Collapse "too early: Xs left" variants
        reason = r["reason"].split(":")[0]
        print(f"  [{r['n']:5d}] {reason}")

    # Hypothetical PnL on BUY decisions
    print("\n=== Hypothetical BUY trades ===")
    buys = conn.execute(
        "SELECT * FROM decisions WHERE action='BUY' ORDER BY ts ASC"
    ).fetchall()
    print(f"  Total BUY decisions: {len(buys)}")

    if buys:
        wins = losses = unresolved = 0
        gross_pnl = 0.0
        net_pnl = 0.0
        per_market = defaultdict(int)

        for b in buys:
            slug = b["market_slug"]
            per_market[slug] += 1
            if slug not in resolutions:
                unresolved += 1
                continue
            winner = resolutions[slug]
            if b["side"] == winner:
                wins += 1
                # We bought 1 contract at price b['price'], received 1.0 on win
                # PnL per contract = 1.0 - price; fee = rate * (1 - price) * size * price
                size = b["size"] or 1.0
                price = b["price"]
                fee_rate = 0.07
                fee = fee_rate * (1.0 - price) * size * price
                gross = (1.0 - price) * size
                gross_pnl += gross
                net_pnl += gross - fee
            else:
                losses += 1
                size = b["size"] or 1.0
                price = b["price"]
                fee_rate = 0.07
                fee = fee_rate * (1.0 - price) * size * price
                gross = -price * size
                gross_pnl += gross
                net_pnl += gross - fee

        resolved = wins + losses
        print(f"  Resolved: {resolved}, Unresolved: {unresolved}")
        if resolved:
            print(f"  Win-rate: {wins}/{resolved} = {100*wins/resolved:.1f}%")
            print(f"  Gross PnL: ${gross_pnl:+.4f}")
            print(f"  Net PnL (after fees): ${net_pnl:+.4f}")
            print(f"  Per-trade net: ${net_pnl/resolved:+.4f}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
