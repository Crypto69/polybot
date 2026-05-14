"""Late-window convergence decision logic.

Replicates the pattern observed in Bonereaper's trades, calibrated for our entry cap:
buy a side that the market itself thinks is the winner, when supply still exists
at our price ceiling, and only when our independent BTC spot reading agrees.

Decision rules (in order):
  1. Only fire when t_remaining < cfg.seconds_before_close.
  2. Find the "winner side" — the side whose best ask is in [low_floor, max_entry_price]
     with at least min_book_size_shares available at <= max_entry_price.
  3. If BOTH sides satisfy → skip (market is genuinely uncertain).
  4. If NEITHER side satisfies → skip.
  5. Cross-check against BTC spot: the winner side must agree with the spot direction
     vs the window's open price.
  6. If everything aligns → BUY at max_entry_price for cfg.order_size_shares.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from .book import BookSnapshot
from .config import Config
from .markets import LiveMarket
from .spot import SpotReading


class Action(str, Enum):
    BUY = "BUY"
    SKIP = "SKIP"


class Side(str, Enum):
    UP = "UP"
    DOWN = "DOWN"


@dataclass(frozen=True)
class Decision:
    action: Action
    side: Optional[Side]
    price: Optional[float]
    size: Optional[float]
    reason: str


def _side_has_buyable(book: Optional[BookSnapshot], cfg: Config) -> bool:
    """Does this side have enough size at or below our entry cap, with best ask >= floor?"""
    if not book or not book.best_ask:
        return False
    # Don't buy if the side is already so far above 0.5 that there's no upside left
    # (best ask must be in the low_floor..max_entry_price range)
    if not (cfg.low_price_floor <= book.best_ask.price <= cfg.max_entry_price):
        return False
    return book.buyable_at(cfg.max_entry_price) >= cfg.min_book_size_shares


def _spot_direction_for_market(
    market: LiveMarket, spot_now: float, spot_at_open: Optional[float], cfg: Config
) -> Optional[Side]:
    """Which side does our independent spot reading favor?

    Returns None if confidence is below threshold (BTC hasn't moved enough to be sure)
    or if we don't know the open price.
    """
    if spot_at_open is None or spot_at_open <= 0:
        return None
    move_bps = (spot_now - spot_at_open) / spot_at_open * 10_000
    if abs(move_bps) < cfg.spot_confidence_bps:
        return None
    return Side.UP if move_bps > 0 else Side.DOWN


def decide(
    *,
    cfg: Config,
    market: LiveMarket,
    yes_book: Optional[BookSnapshot],   # "Up"
    no_book: Optional[BookSnapshot],    # "Down"
    spot_now: float,
    spot_at_open: Optional[float],
    now: float,
) -> Decision:
    # Rule 1: time gate
    t_left = market.end_ts - now
    if t_left > cfg.seconds_before_close:
        return Decision(Action.SKIP, None, None, None,
                        f"too early: {t_left:.0f}s left")
    if t_left < cfg.min_t_remaining_seconds:
        return Decision(Action.SKIP, None, None, None,
                        f"too late: {t_left:.1f}s left (< {cfg.min_t_remaining_seconds}s buffer)")

    # Rule 2/3/4: find the side(s) that satisfy the buyable predicate
    up_buyable = _side_has_buyable(yes_book, cfg)
    down_buyable = _side_has_buyable(no_book, cfg)

    if up_buyable and down_buyable:
        return Decision(Action.SKIP, None, None, None,
                        "both sides have entry-priced supply: market is uncertain")
    if not up_buyable and not down_buyable:
        return Decision(Action.SKIP, None, None, None,
                        "neither side has entry-priced supply")

    winner_side = Side.UP if up_buyable else Side.DOWN
    winner_book = yes_book if up_buyable else no_book

    # Rule 5: spot confirmation
    spot_pick = _spot_direction_for_market(market, spot_now, spot_at_open, cfg)
    if spot_pick is None:
        return Decision(Action.SKIP, winner_side, None, None,
                        f"spot move below confidence threshold "
                        f"({cfg.spot_confidence_bps} bps required)")
    if spot_pick != winner_side:
        return Decision(Action.SKIP, winner_side, None, None,
                        f"spot disagrees: book says {winner_side.value}, spot says {spot_pick.value}")

    # Rule 6: BUY
    assert winner_book is not None and winner_book.best_ask is not None
    return Decision(
        Action.BUY,
        winner_side,
        cfg.max_entry_price,
        cfg.order_size_shares,
        f"late-window buy: {winner_side.value} @ {cfg.max_entry_price}, "
        f"{t_left:.0f}s left, ask {winner_book.best_ask.price}",
    )
