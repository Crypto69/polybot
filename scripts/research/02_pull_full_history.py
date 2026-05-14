"""Pull complete trade + activity history for the target trader.

Saves to /Volumes/ExternalHD/code/polybot/research/data/
"""
import json
import os
import time
from pathlib import Path

import requests

ADDR = "0xeebde7a0e019a63e6b476eb425505b7b3e6eba30"
OUT = Path("/Volumes/ExternalHD/code/polybot/research/data")
OUT.mkdir(parents=True, exist_ok=True)

# data-api.polymarket.com supports limit + offset on /trades and /activity
BASE = "https://data-api.polymarket.com"


def paginate(endpoint: str, page_size: int = 500, max_pages: int = 1000):
    """Pull until empty or max_pages reached."""
    out = []
    offset = 0
    pages = 0
    while pages < max_pages:
        url = f"{BASE}/{endpoint}?user={ADDR}&limit={page_size}&offset={offset}"
        r = requests.get(url, timeout=30)
        if r.status_code != 200:
            print(f"  ! {r.status_code} at offset={offset}")
            break
        batch = r.json()
        if not batch:
            break
        out.extend(batch)
        print(f"  offset={offset} got {len(batch)} (total={len(out)})")
        if len(batch) < page_size:
            break
        offset += page_size
        pages += 1
        time.sleep(0.15)
    return out


def main():
    for ep in ["trades", "activity"]:
        print(f"=== Pulling {ep} ===")
        data = paginate(ep, page_size=500)
        path = OUT / f"{ep}.json"
        with open(path, "w") as f:
            json.dump(data, f)
        print(f"  saved {len(data)} -> {path}")

    # Positions snapshot
    print("=== Pulling positions ===")
    r = requests.get(f"{BASE}/positions?user={ADDR}&limit=500", timeout=30)
    pos = r.json()
    with open(OUT / "positions.json", "w") as f:
        json.dump(pos, f, indent=2)
    print(f"  saved {len(pos)} positions")

    # Value
    r = requests.get(f"{BASE}/value?user={ADDR}", timeout=30)
    with open(OUT / "value.json", "w") as f:
        json.dump(r.json(), f, indent=2)
    print(f"  value: {r.json()}")


if __name__ == "__main__":
    main()
