"""Risk caps. Multiple independent checks — all must pass for a BUY to proceed.

Checks (in order, fail-fast):
  1. Account-state query succeeded (else block — never trade blind)
  2. Per-market cooldown — never re-submit on a market we already touched this session
  3. Per-market position — never re-enter a market where we already hold tokens
  4. Per-market open order — never duplicate an order already sitting on the book
  5. Global open order count — at most cfg.max_open_positions concurrent
  6. Hard balance floor — refuse if (current pUSD - this order's collateral) < cfg.min_pusd_floor
  7. Daily loss cap — refuse if (session_start_balance - current pUSD) >= cfg.daily_loss_cap_usd
"""
from __future__ import annotations

from decimal import Decimal

from .account import AccountState
from .config import Config


def allowed_to_trade(
    cfg: Config,
    *,
    state: AccountState,
    market_condition_id: str,
    traded_markets: set[str],            # in-memory set of markets we've submitted on this session
    session_start_balance: Decimal,
    order_collateral_usd: Decimal,
) -> tuple[bool, str]:
    """Return (allowed, reason). False on any failed check."""
    if state.error:
        return False, f"account state unavailable: {state.error}"

    if market_condition_id in traded_markets:
        return False, "already submitted on this market this session"

    if market_condition_id in state.position_markets:
        return False, "already hold a position on this market"

    if market_condition_id in state.open_order_markets:
        return False, "already have an open order on this market"

    if state.open_order_count >= cfg.max_open_positions:
        return False, f"max_open_positions reached ({state.open_order_count}/{cfg.max_open_positions})"

    min_floor = Decimal(str(cfg.min_pusd_floor_usd))
    projected_balance = state.pusd_balance - order_collateral_usd
    if projected_balance < min_floor:
        return False, (
            f"hard balance floor: projected pUSD {projected_balance:.4f} "
            f"< floor {min_floor} (current {state.pusd_balance:.4f}, order {order_collateral_usd:.4f})"
        )

    realized_loss = max(Decimal(0), session_start_balance - state.pusd_balance)
    if realized_loss >= Decimal(str(cfg.daily_loss_cap_usd)):
        return False, (
            f"daily loss cap hit: realized loss ${realized_loss:.4f} "
            f">= ${cfg.daily_loss_cap_usd} cap"
        )

    return True, "ok"
