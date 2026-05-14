"""CLOB order book snapshot reader. HTTP polling; WSS upgrade can come later."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import requests

from .config import Config


@dataclass(frozen=True)
class Level:
    price: float
    size: float


@dataclass(frozen=True)
class BookSnapshot:
    token_id: str
    bids: list[Level]      # sorted by price descending (best first)
    asks: list[Level]      # sorted by price ascending (best first)

    @property
    def best_bid(self) -> Optional[Level]:
        return self.bids[0] if self.bids else None

    @property
    def best_ask(self) -> Optional[Level]:
        return self.asks[0] if self.asks else None

    def buyable_at(self, max_price: float) -> float:
        """Cumulative ask size at or below max_price (shares we could BUY at <= max_price)."""
        return sum(l.size for l in self.asks if l.price <= max_price)

    def sellable_at(self, min_price: float) -> float:
        """Cumulative bid size at or above min_price (shares we could SELL at >= min_price)."""
        return sum(l.size for l in self.bids if l.price >= min_price)


def fetch_book(cfg: Config, token_id: str) -> Optional[BookSnapshot]:
    """Fetch one book snapshot. Returns None on 4xx/5xx or empty book."""
    try:
        r = requests.get(f"{cfg.clob_host}/book", params={"token_id": token_id}, timeout=5)
    except requests.RequestException:
        return None
    if r.status_code != 200:
        return None
    data = r.json()
    if not isinstance(data, dict) or "error" in data:
        return None

    def levels(raw, reverse: bool) -> list[Level]:
        out = [Level(price=float(x["price"]), size=float(x["size"])) for x in raw or []]
        out.sort(key=lambda l: l.price, reverse=reverse)
        return out

    return BookSnapshot(
        token_id=token_id,
        bids=levels(data.get("bids", []), reverse=True),
        asks=levels(data.get("asks", []), reverse=False),
    )
