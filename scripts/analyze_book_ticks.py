"""Analyze book trajectory data: when does the price cross our $0.95 cap?

Reads the book_ticks table and produces:
  - per-market table of [t=300s, 240s, 180s, 120s, 90s, 60s, 30s, 10s] → winner_ask
  - aggregate: how long does the book sit in our [low_floor, max_entry_price] band?
  - distribution of "crossing time" — when the winner first hit max_entry_price
"""
from __future__ import annotations

import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from bot.config import load_config  # noqa: E402

cfg = load_config()
DB = cfg.db_path

CHECKPOINTS = [300, 240, 180, 120, 90, 60, 45, 30, 20, 10, 5]


def winner_ask(yes_ask, no_ask):
    if yes_ask is None and no_ask is None:
        return None
    if yes_ask is None:
        return no_ask
    if no_ask is None:
        return yes_ask
    return max(yes_ask, no_ask)


def main() -> int:
    if not DB.exists():
        print(f"No journal at {DB}. Run the bot first.")
        return 1

    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row

    n = conn.execute("SELECT COUNT(*) AS n FROM book_ticks").fetchone()["n"]
    n_markets = conn.execute(
        "SELECT COUNT(DISTINCT market_slug) AS n FROM book_ticks"
    ).fetchone()["n"]
    print(f"Total ticks: {n}, markets: {n_markets}")
    if n == 0:
        print("No ticks yet — let the bot run longer.")
        return 0

    # --- Per-market trajectory at sentinel checkpoints ---
    print(f"\n=== Winner-side ask at checkpoints (t={CHECKPOINTS} sec from close) ===")
    print(f"{'market':35s}  " + "  ".join(f"t={c:>3d}" for c in CHECKPOINTS))

    rows = conn.execute(
        "SELECT market_slug, t_remaining, yes_best_ask, no_best_ask "
        "FROM book_ticks ORDER BY market_slug, t_remaining DESC"
    ).fetchall()
    by_market = defaultdict(list)
    for r in rows:
        by_market[r["market_slug"]].append(r)

    for slug, ticks in by_market.items():
        cells = []
        for cp in CHECKPOINTS:
            # Find the tick closest to (but >=) cp
            closest = None
            best_diff = float("inf")
            for t in ticks:
                if t["t_remaining"] >= cp:
                    diff = t["t_remaining"] - cp
                    if diff < best_diff:
                        best_diff = diff
                        closest = t
            if closest is None or best_diff > 30:  # require within 30s
                cells.append("  -- ")
            else:
                w = winner_ask(closest["yes_best_ask"], closest["no_best_ask"])
                cells.append(f"{w:.2f}" if w is not None else " --")
        print(f"  {slug:35s}  " + "  ".join(f"{c:>5s}" for c in cells))

    # --- "Crossing time": when does the winner first cross max_entry_price? ---
    print(f"\n=== When does winner first reach >= ${cfg.max_entry_price}? ===")
    print(f"{'market':35s}  {'first_cross_at':>14s}  {'time_in_band':>13s}")
    cap = cfg.max_entry_price
    floor = cfg.low_price_floor
    for slug, ticks in by_market.items():
        ticks_sorted = sorted(ticks, key=lambda t: -t["t_remaining"])
        first_cross_t = None
        in_band_seconds = 0
        last_t = None
        for t in ticks_sorted:
            w = winner_ask(t["yes_best_ask"], t["no_best_ask"])
            if w is None:
                continue
            if floor <= w <= cap:
                if last_t is not None:
                    in_band_seconds += last_t - t["t_remaining"]
                last_t = t["t_remaining"]
            else:
                last_t = None
            if first_cross_t is None and w >= cap:
                first_cross_t = t["t_remaining"]
        first_str = f"{first_cross_t:.0f}s" if first_cross_t is not None else "never"
        print(f"  {slug:35s}  {first_str:>14s}  {in_band_seconds:>12.0f}s")

    # --- Aggregate: of all ticks in observation window, % in our band ---
    print(f"\n=== Of all observed ticks, share in each price bucket (winner-side) ===")
    buckets = [(0, 0.50), (0.50, 0.70), (0.70, floor), (floor, 0.85),
               (0.85, 0.90), (0.90, cap), (cap, 0.97), (0.97, 0.99), (0.99, 1.001)]
    counts = [0] * len(buckets)
    total = 0
    for r in rows:
        w = winner_ask(r["yes_best_ask"], r["no_best_ask"])
        if w is None:
            continue
        total += 1
        for i, (lo, hi) in enumerate(buckets):
            if lo <= w < hi:
                counts[i] += 1
                break
    for (lo, hi), n in zip(buckets, counts):
        bar = "#" * int(50 * n / total) if total else ""
        print(f"  {lo:.2f}-{hi:.3f}  {n:5d}  {100*n/total if total else 0:5.1f}%  {bar}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
