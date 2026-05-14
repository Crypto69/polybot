"""BTC/USD spot reader. Cheap proxy for Chainlink BTC/USD Data Stream.

Fetches Binance + Coinbase, returns midpoint. Both update sub-second; rest of the
trading logic only needs to know "is BTC above or below the window-open price"
with confidence. We can swap in Chainlink Data Streams later if we hit edge issues.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import requests


@dataclass(frozen=True)
class SpotReading:
    binance: Optional[float]
    coinbase: Optional[float]

    @property
    def mid(self) -> Optional[float]:
        prices = [p for p in (self.binance, self.coinbase) if p is not None]
        return sum(prices) / len(prices) if prices else None


def _fetch_binance() -> Optional[float]:
    try:
        r = requests.get(
            "https://api.binance.com/api/v3/ticker/price",
            params={"symbol": "BTCUSDT"},
            timeout=3,
        )
        return float(r.json()["price"])
    except Exception:
        return None


def _fetch_coinbase() -> Optional[float]:
    try:
        r = requests.get(
            "https://api.coinbase.com/v2/prices/BTC-USD/spot",
            timeout=3,
        )
        return float(r.json()["data"]["amount"])
    except Exception:
        return None


def fetch_spot() -> SpotReading:
    return SpotReading(binance=_fetch_binance(), coinbase=_fetch_coinbase())
