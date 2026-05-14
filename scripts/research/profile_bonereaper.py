"""Pull and analyze Bonereaper's recent trades to verify the late-window thesis."""
from __future__ import annotations

import json
import re
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

import requests

ADDR = "0xeebde7a0e019a63e6b476eb425505b7b3e6eba30"
ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "research" / "bonereaper_trades_raw.json"
OUT.parent.mkdir(parents=True, exist_ok=True)

session = requests.Session()


def fetch_with_retry(url, params, tries=4, base_delay=2):
    for i in range(tries):
        try:
            r = session.get(url, params=params, timeout=30)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            if i == tries - 1:
                raise
            print(f"  retry {i+1} after {e!r}")
            time.sleep(base_delay * (2**i))


def window_minutes(title: str) -> int | None:
    m = re.search(r"(\d{1,2}):(\d{2})(AM|PM)-(\d{1,2}):(\d{2})(AM|PM)", title)
    if not m:
        return None

    def to_min(h, mn, ampm):
        h = int(h) % 12
        if ampm == "PM":
            h += 12
        return h * 60 + int(mn)

    a = to_min(m.group(1), m.group(2), m.group(3))
    b = to_min(m.group(4), m.group(5), m.group(6))
    return (b - a) % (24 * 60)


def fetch_trades(pages: int = 8, page_size: int = 500):
    all_trades = []
    cursor = None
    for p in range(pages):
        params = {"user": ADDR, "limit": page_size}
        if cursor is not None:
            params["before"] = cursor
        chunk = fetch_with_retry("https://data-api.polymarket.com/trades", params)
        if not chunk:
            break
        all_trades.extend(chunk)
        print(f"  page {p+1}: +{len(chunk)} (total {len(all_trades)})")
        cursor = chunk[-1]["timestamp"]
        if len(chunk) < page_size:
            break
    return all_trades


def main():
    print(f"Pulling trades for {ADDR} ...")
    trades = fetch_trades()
    OUT.write_text(json.dumps(trades))
    print(f"Saved {len(trades)} trades to {OUT.relative_to(ROOT)}")
    print()

    if not trades:
        print("No trades — aborting analysis.")
        return

    # Time range
    ts = [int(t["timestamp"]) for t in trades]
    print(f"Time range: {datetime.fromtimestamp(min(ts))} -> {datetime.fromtimestamp(max(ts))}")

    sides = Counter(t["side"] for t in trades)
    print(f"Sides: {dict(sides)}    (BUY-only ⇒ holds-to-resolution thesis)")

    # Price distribution for BUYs
    buckets = [(0, 0.50), (0.50, 0.80), (0.80, 0.90), (0.90, 0.95),
               (0.95, 0.97), (0.97, 0.99), (0.99, 1.001)]
    counts = [0] * len(buckets)
    sizes = [0.0] * len(buckets)
    for t in trades:
        if t["side"] != "BUY":
            continue
        p, sz = float(t["price"]), float(t["size"])
        for i, (lo, hi) in enumerate(buckets):
            if lo <= p < hi:
                counts[i] += 1
                sizes[i] += sz * p
                break

    n_total = sum(counts)
    d_total = sum(sizes)
    print(f"\nPrice distribution of BUYs (n={n_total}, $vol={d_total:.0f}):")
    print(f"  bucket          n_trades  pct_n   $vol      pct_$")
    for (lo, hi), n, d in zip(buckets, counts, sizes):
        print(f"  {lo:.2f}-{hi:.2f}     {n:6d}    {100*n/n_total:5.1f}%  ${d:9.0f}  {100*d/d_total:5.1f}%")

    above_95 = sum(sizes[4:])
    print(f"\nTHESIS: dollar vol at price >= 0.95 = {100*above_95/d_total:.1f}%   (video claim: 60%)")

    # Window length distribution
    windows = Counter(window_minutes(t.get("title", "")) for t in trades if window_minutes(t.get("title", "")))
    print(f"\nMarket window length (mins): {dict(windows.most_common())}")

    # Distinct markets
    slugs = Counter(t["slug"] for t in trades)
    print(f"\nDistinct markets traded: {len(slugs)}")
    print("Top 5:")
    for slug, c in slugs.most_common(5):
        print(f"  [{c:4d}] {slug}")


if __name__ == "__main__":
    main()
