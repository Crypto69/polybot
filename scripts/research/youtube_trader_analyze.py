"""Analyze YouTube tutorial trader's history.

Per-trade win/loss is computed from the resolved positions (positions endpoint reports
realized payout = currentValue when redeemable + cashPnl). For trades whose underlying
condition is not yet in /positions (still open or already redeemed/no-position), we fall
back to clob.polymarket.com/markets/<conditionId> to read the winning token.
"""

import json
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import requests

DATA = Path("/Volumes/ExternalHD/code/polybot/research/data")
CLOB = "https://clob.polymarket.com"


def fetch_market(condition_id: str) -> dict | None:
    try:
        r = requests.get(f"{CLOB}/markets/{condition_id}", timeout=15)
        if r.status_code != 200:
            return None
        return r.json()
    except Exception:  # noqa: BLE001
        return None


def main() -> None:
    trades = json.loads((DATA / "yt_proxy_trades.json").read_text())
    positions = json.loads((DATA / "yt_proxy_positions.json").read_text())

    if not trades:
        print("No trades.")
        return

    # ---- Basic counts -------------------------------------------------------
    n = len(trades)
    times = sorted(t["timestamp"] for t in trades)
    first = datetime.fromtimestamp(times[0], tz=timezone.utc)
    last = datetime.fromtimestamp(times[-1], tz=timezone.utc)
    dollar_vol = sum(float(t["size"]) * float(t["price"]) for t in trades)
    share_vol = sum(float(t["size"]) for t in trades)
    sides = Counter(t["side"] for t in trades)
    outcomes = Counter(t["outcome"] for t in trades)
    slugs = Counter(t.get("eventSlug", "") for t in trades)

    # Slot type: 5m / 15m / other
    slot_kinds: Counter[str] = Counter()
    for t in trades:
        slug = t.get("slug", "")
        if "btc-updown-5m" in slug:
            slot_kinds["btc-5m"] += 1
        elif "btc-updown-15m" in slug:
            slot_kinds["btc-15m"] += 1
        elif "btc" in slug.lower():
            slot_kinds["btc-other"] += 1
        else:
            slot_kinds["non-btc"] += 1

    prices = [float(t["price"]) for t in trades]
    sizes = [float(t["size"]) for t in trades]

    def pct_at_or_above(threshold: float) -> float:
        return 100.0 * sum(1 for p in prices if p >= threshold) / len(prices)

    # Time remaining at entry: market slots are named with start unix seconds and
    # are 5min long. trade timestamp - slot_start = seconds into the window.
    # t_remaining = 300 - (ts - slot_start)
    times_remaining: list[float] = []
    for t in trades:
        slug = t.get("slug", "")
        try:
            slot_start = int(slug.rsplit("-", 1)[-1])
            window_len = 900 if "btc-updown-15m" in slug else 300
            elapsed = int(t["timestamp"]) - slot_start
            remaining = window_len - elapsed
            if 0 <= remaining <= window_len:
                times_remaining.append(remaining)
        except Exception:  # noqa: BLE001
            pass

    # ---- Resolve win/loss per trade ----------------------------------------
    # Build a map conditionId -> winning outcome string (Up/Down) using CLOB
    cond_ids = {t["conditionId"] for t in trades}
    print(f"Fetching {len(cond_ids)} unique markets from CLOB...")
    market_winner: dict[str, str | None] = {}
    market_resolved: dict[str, bool] = {}
    for i, cid in enumerate(sorted(cond_ids)):
        m = fetch_market(cid)
        if not m:
            market_winner[cid] = None
            market_resolved[cid] = False
            continue
        toks = m.get("tokens", []) or []
        winner_outcome = None
        any_winner = False
        for tk in toks:
            if tk.get("winner") is True:
                winner_outcome = tk.get("outcome")
                any_winner = True
                break
        market_resolved[cid] = bool(m.get("closed")) and any_winner
        market_winner[cid] = winner_outcome
        if (i + 1) % 25 == 0:
            print(f"  {i+1}/{len(cond_ids)}")

    wins = 0
    losses = 0
    unresolved = 0
    realized_pnl = 0.0   # sum over resolved trades of (size if win else 0) - cost
    resolved_cost = 0.0
    resolved_payout = 0.0
    for t in trades:
        cid = t["conditionId"]
        if not market_resolved.get(cid):
            unresolved += 1
            continue
        size = float(t["size"])
        price = float(t["price"])
        cost = size * price
        winner = market_winner.get(cid)
        if winner is None:
            unresolved += 1
            continue
        won = (winner == t["outcome"])
        payout = size if won else 0.0
        resolved_cost += cost
        resolved_payout += payout
        realized_pnl += (payout - cost)
        if won:
            wins += 1
        else:
            losses += 1

    resolved_n = wins + losses
    win_rate = (100.0 * wins / resolved_n) if resolved_n else 0.0

    # ---- Print report -------------------------------------------------------
    def pct(d: dict, total: int) -> dict:
        return {k: f"{v} ({100.0*v/total:.0f}%)" for k, v in d.items()}

    print()
    print("=" * 70)
    print("YOUTUBE TUTORIAL TRADER — allaboutai (Glittering-Headrest)")
    print("=" * 70)
    print(f"EOA:           0x95C6603e5dCaEaD9Be26549d8ea2bF23B67Ed1B5")
    print(f"Proxy/Deposit: 0xca12a788a13a0c46968828a125ccbc09cea2ea73")
    print()
    print(f"Trades:        {n}")
    print(f"First trade:   {first.isoformat()}")
    print(f"Last trade:    {last.isoformat()}")
    print(f"Span:          {(times[-1]-times[0])/3600:.1f} hours")
    print(f"$ volume:      ${dollar_vol:,.2f}")
    print(f"Share volume:  {share_vol:,.2f}")
    print(f"Avg trade $:   ${dollar_vol/n:.2f}")
    print(f"Avg trade sz:  {share_vol/n:.2f} shares")
    print()
    print(f"Sides:         {dict(sides)}")
    print(f"Outcomes:      {dict(outcomes)}")
    print(f"Slot type:     {dict(slot_kinds)}")
    print()
    print("Price distribution (entry):")
    print(f"  min/median/max: {min(prices):.3f} / {statistics.median(prices):.3f} / {max(prices):.3f}")
    print(f"  >= 0.85:  {pct_at_or_above(0.85):.0f}%")
    print(f"  >= 0.90:  {pct_at_or_above(0.90):.0f}%")
    print(f"  >= 0.95:  {pct_at_or_above(0.95):.0f}%")
    print(f"  >= 0.97:  {pct_at_or_above(0.97):.0f}%")
    print(f"  >= 0.98:  {pct_at_or_above(0.98):.0f}%")
    print(f"  >= 0.99:  {pct_at_or_above(0.99):.0f}%")
    print()
    print("Size distribution (shares):")
    print(f"  min/median/max: {min(sizes):.2f} / {statistics.median(sizes):.2f} / {max(sizes):.2f}")
    sz_buckets = Counter()
    for s in sizes:
        if s < 4: sz_buckets["<4"] += 1
        elif s < 5: sz_buckets["4-5"] += 1
        elif s < 6: sz_buckets["5-6"] += 1
        elif s < 8: sz_buckets["6-8"] += 1
        else: sz_buckets["8+"] += 1
    print(f"  buckets:  {dict(sz_buckets)}")
    print()
    if times_remaining:
        print("Time remaining at entry (seconds):")
        print(f"  min/median/max: {min(times_remaining):.0f} / {statistics.median(times_remaining):.0f} / {max(times_remaining):.0f}")
        tr_buckets = Counter()
        for r in times_remaining:
            if r < 15: tr_buckets["<15s"] += 1
            elif r < 30: tr_buckets["15-30s"] += 1
            elif r < 60: tr_buckets["30-60s"] += 1
            elif r < 120: tr_buckets["1-2min"] += 1
            else: tr_buckets["2min+"] += 1
        print(f"  buckets:  {dict(tr_buckets)}")
    print()
    print("RESOLVED TRADES:")
    print(f"  Wins:        {wins}")
    print(f"  Losses:      {losses}")
    print(f"  Unresolved:  {unresolved}")
    print(f"  Win rate:    {win_rate:.1f}% ({wins}/{resolved_n})")
    print(f"  Cost paid:   ${resolved_cost:.2f}")
    print(f"  Payout:      ${resolved_payout:.2f}")
    print(f"  Realized P&L: ${realized_pnl:+.2f}")
    print()

    # Top markets by repeat trades
    top_events = slugs.most_common(8)
    print("Most-traded events:")
    for slug, cnt in top_events:
        print(f"  {cnt:3d}  {slug}")
    print()

    # Save processed metrics
    out = {
        "n_trades": n,
        "first": first.isoformat(),
        "last": last.isoformat(),
        "dollar_volume": dollar_vol,
        "wins": wins,
        "losses": losses,
        "unresolved": unresolved,
        "win_rate_pct": win_rate,
        "realized_pnl": realized_pnl,
        "resolved_cost": resolved_cost,
        "resolved_payout": resolved_payout,
        "side_counts": dict(sides),
        "outcome_counts": dict(outcomes),
        "slot_kinds": dict(slot_kinds),
        "price_pct_at_or_above": {
            "0.85": pct_at_or_above(0.85),
            "0.90": pct_at_or_above(0.90),
            "0.95": pct_at_or_above(0.95),
            "0.97": pct_at_or_above(0.97),
            "0.98": pct_at_or_above(0.98),
            "0.99": pct_at_or_above(0.99),
        },
    }
    (DATA / "yt_summary.json").write_text(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
