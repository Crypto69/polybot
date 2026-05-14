"""Pull full trade history + positions for the YouTube tutorial trader (allaboutai).

EOA:           0x95C6603e5dCaEaD9Be26549d8ea2bF23B67Ed1B5
Deposit/proxy: 0xca12a788a13a0c46968828a125ccbc09cea2ea73
"""

import json
import time
from pathlib import Path

import requests

OUT_DIR = Path("/Volumes/ExternalHD/code/polybot/research/data")
OUT_DIR.mkdir(parents=True, exist_ok=True)

EOA = "0x95C6603e5dCaEaD9Be26549d8ea2bF23B67Ed1B5"
PROXY = "0xca12a788a13a0c46968828a125ccbc09cea2ea73"

DATA_API = "https://data-api.polymarket.com"


def pull_trades(addr: str) -> list[dict]:
    """Paginate /trades?user=<addr> with offset until empty."""
    out: list[dict] = []
    offset = 0
    limit = 500
    while True:
        url = f"{DATA_API}/trades?user={addr}&limit={limit}&offset={offset}"
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        batch = r.json()
        if not batch:
            break
        out.extend(batch)
        if len(batch) < limit:
            break
        offset += limit
        time.sleep(0.2)
    return out


def pull_positions(addr: str) -> list[dict]:
    """Pull all positions (paginate by offset)."""
    out: list[dict] = []
    offset = 0
    limit = 500
    while True:
        url = f"{DATA_API}/positions?user={addr}&limit={limit}&offset={offset}&sortBy=CURRENT&sortDirection=DESC"
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        batch = r.json()
        if not batch:
            break
        out.extend(batch)
        if len(batch) < limit:
            break
        offset += limit
        time.sleep(0.2)
    return out


def pull_value(addr: str) -> dict | None:
    url = f"{DATA_API}/value?user={addr}"
    r = requests.get(url, timeout=30)
    if r.status_code != 200:
        return None
    return r.json()


def pull_pnl(addr: str) -> dict | None:
    # Try a few PnL endpoints
    urls = [
        f"{DATA_API}/user-pnl?user_address={addr}&interval=all&fidelity=1d",
        f"{DATA_API}/positions/value?user={addr}",
    ]
    out = {}
    for u in urls:
        try:
            r = requests.get(u, timeout=15)
            out[u] = {"status": r.status_code, "body": r.text[:600]}
        except Exception as e:  # noqa: BLE001
            out[u] = {"error": str(e)}
    return out


def main() -> None:
    for label, addr in [("eoa", EOA), ("proxy", PROXY)]:
        print(f"--- {label} {addr} ---")
        trades = pull_trades(addr)
        positions = pull_positions(addr)
        value = pull_value(addr)
        pnl = pull_pnl(addr)
        (OUT_DIR / f"yt_{label}_trades.json").write_text(json.dumps(trades, indent=2))
        (OUT_DIR / f"yt_{label}_positions.json").write_text(json.dumps(positions, indent=2))
        (OUT_DIR / f"yt_{label}_value.json").write_text(json.dumps(value, indent=2))
        (OUT_DIR / f"yt_{label}_pnl_probe.json").write_text(json.dumps(pnl, indent=2))
        print(f"  trades:   {len(trades)}")
        print(f"  positions:{len(positions)}")
        print(f"  value:    {value}")


if __name__ == "__main__":
    main()
