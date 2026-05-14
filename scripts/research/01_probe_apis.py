"""Probe Polymarket data-api endpoints for the target trader.

Saves sample responses to /tmp/bonereader_*.json for inspection.
"""
import json
import requests

ADDR = "0xeebde7a0e019a63e6b476eb425505b7b3e6eba30"

endpoints = {
    "positions": f"https://data-api.polymarket.com/positions?user={ADDR}&limit=500",
    "trades_recent": f"https://data-api.polymarket.com/trades?user={ADDR}&limit=10",
    "activity_recent": f"https://data-api.polymarket.com/activity?user={ADDR}&limit=10",
    "value": f"https://data-api.polymarket.com/value?user={ADDR}",
}

for name, url in endpoints.items():
    r = requests.get(url, timeout=15)
    print(f"{name}: {r.status_code} len={len(r.text)}")
    try:
        data = r.json()
    except Exception:
        data = r.text
    with open(f"/tmp/bonereader_{name}.json", "w") as f:
        json.dump(data, f, indent=2)
    if isinstance(data, list):
        print(f"  list len={len(data)}")
        if data:
            print(f"  sample keys: {list(data[0].keys()) if isinstance(data[0], dict) else type(data[0])}")
    elif isinstance(data, dict):
        print(f"  dict keys: {list(data.keys())[:20]}")
