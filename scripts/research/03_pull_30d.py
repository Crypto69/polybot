"""Pull full 30-day activity history using start/end timestamp windows.

Strategy: walk backwards in time, pulling /activity?start=X&end=Y in 4-hour windows
so we never hit the 3500-row limit. /activity contains both TRADE and REDEEM/MERGE.
"""
import json
import time
from pathlib import Path

import requests

ADDR = "0xeebde7a0e019a63e6b476eb425505b7b3e6eba30"
OUT = Path("/Volumes/ExternalHD/code/polybot/docs/research/data")
OUT.mkdir(parents=True, exist_ok=True)
BASE = "https://data-api.polymarket.com"

# Today is 2026-05-14 per env. Pull last 30 days.
NOW = 1778803200  # 2026-05-14 16:00 UTC approx (covers today)
WINDOW = 4 * 3600  # 4 hours per window
DAYS = 35  # bit of a buffer
START = NOW - DAYS * 86400


def fetch_window(start: int, end: int):
    """Pull all activity in [start, end). Page via offset within window."""
    out = []
    offset = 0
    while True:
        url = f"{BASE}/activity?user={ADDR}&start={start}&end={end}&limit=500&offset={offset}"
        r = requests.get(url, timeout=30)
        if r.status_code != 200:
            print(f"   ! {r.status_code} window={start}..{end} offset={offset}")
            break
        batch = r.json()
        if not batch:
            break
        out.extend(batch)
        if len(batch) < 500:
            break
        offset += 500
        if offset >= 3500:
            # Window too big; split it
            print(f"   ! window too big at {start}..{end}, splitting")
            mid = (start + end) // 2
            out = []
            out.extend(fetch_window(start, mid))
            out.extend(fetch_window(mid, end))
            return out
        time.sleep(0.05)
    return out


def main():
    all_acts = []
    seen_tx = set()
    cursor = NOW
    windows_done = 0
    while cursor > START:
        win_start = cursor - WINDOW
        win_end = cursor
        batch = fetch_window(win_start, win_end)
        new = 0
        for a in batch:
            key = (a.get("transactionHash"), a.get("asset"), a.get("timestamp"), a.get("type"), a.get("size"))
            if key not in seen_tx:
                seen_tx.add(key)
                all_acts.append(a)
                new += 1
        print(f"window {win_start}..{win_end}: {len(batch)} fetched, {new} new (total={len(all_acts)})")
        cursor = win_start
        windows_done += 1
        # Save progress every 20 windows
        if windows_done % 20 == 0:
            with open(OUT / "activity_30d.json", "w") as f:
                json.dump(all_acts, f)
        time.sleep(0.05)

    with open(OUT / "activity_30d.json", "w") as f:
        json.dump(all_acts, f)
    print(f"DONE: {len(all_acts)} total activities saved")


if __name__ == "__main__":
    main()
