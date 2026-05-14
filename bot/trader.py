"""Live order placement via py-clob-client-v2.

Wraps the SDK with our types and journals every interaction.
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from py_clob_client_v2 import OrderType
from py_clob_client_v2.clob_types import (
    OpenOrderParams,
    OrderArgsV2,
    OrderPayload,
    PartialCreateOrderOptions,
)

from .auth import make_client
from .config import Config
from .journal import connect
from .markets import LiveMarket
from .strategy import Decision, Side


# Status values from the SDK's create_and_post_order response.
# Verified empirically: "matched" (filled) and "live" (resting on book) are the
# only success states. Anything else means our order did NOT make it to the book
# and we should treat it as a failure for risk-tracking purposes.
SUCCESS_ORDER_STATUSES = {"matched", "live", "delayed"}


@dataclass(frozen=True)
class PlaceResult:
    ok: bool
    order_id: Optional[str]
    status: Optional[str]
    error: Optional[str]
    raw: Optional[dict]


class Trader:
    """Stateful wrapper. Lazy-initialises the SDK client on first use."""

    def __init__(self, cfg: Config):
        self.cfg = cfg
        self._client = None  # lazy

    def _ensure_client(self):
        if self._client is not None:
            return self._client
        chain_id = int(os.getenv("CHAIN_ID", "137"))
        self._client = make_client(self.cfg.clob_host, chain_id)
        return self._client

    def address(self) -> str:
        return self._ensure_client().get_address()

    # --- Read paths (also useful for live monitoring) ---

    def open_orders(self, market_condition_id: Optional[str] = None) -> list:
        c = self._ensure_client()
        params = OpenOrderParams(market=market_condition_id) if market_condition_id else None
        return c.get_open_orders(params=params)

    def balance_allowance(self):
        c = self._ensure_client()
        return c.get_balance_allowance()

    # --- Write paths ---

    def place_buy(
        self,
        *,
        market: LiveMarket,
        decision: Decision,
        order_type: OrderType = OrderType.GTC,
    ) -> PlaceResult:
        """Place a single GTC limit BUY following the decision. Journals the result."""
        if decision.side is None or decision.price is None or decision.size is None:
            return PlaceResult(False, None, None, "decision missing side/price/size", None)

        token_id = market.yes_token_id if decision.side == Side.UP else market.no_token_id

        args = OrderArgsV2(
            token_id=token_id,
            price=float(decision.price),
            size=float(decision.size),
            side="BUY",
        )
        opts = PartialCreateOrderOptions(
            tick_size=str(market.tick_size),  # SDK wants string
            neg_risk=market.neg_risk,
        )

        client = self._ensure_client()
        try:
            resp = client.create_and_post_order(args, options=opts, order_type=order_type)
        except Exception as e:
            self._journal_order(
                market=market, decision=decision, status="ERROR",
                order_id=None, error=str(e),
            )
            return PlaceResult(False, None, None, str(e), None)

        # py-clob-client returns a dict with orderID, status, makingAmount, etc.
        order_id = resp.get("orderID") if isinstance(resp, dict) else None
        status = resp.get("status") if isinstance(resp, dict) else None
        # Treat unknown statuses as failure — never optimistically count them as success.
        is_success = bool(status) and status.lower() in SUCCESS_ORDER_STATUSES
        self._journal_order(
            market=market, decision=decision, status=status or "UNKNOWN",
            order_id=order_id,
            error=None if is_success else f"unexpected status: {status!r}",
            raw=resp,
        )
        return PlaceResult(
            ok=is_success,
            order_id=order_id,
            status=status,
            error=None if is_success else f"unexpected status: {status!r}",
            raw=resp if isinstance(resp, dict) else None,
        )

    def cancel(self, order_id: str) -> tuple[bool, Optional[str]]:
        """Return (ok, error_message)."""
        c = self._ensure_client()
        try:
            c.cancel_order(OrderPayload(orderID=order_id))
            return True, None
        except Exception as e:
            err = str(e)
            print(f"[trader] cancel({order_id}) failed: {err}", flush=True)
            return False, err

    def cancel_stale(self, max_age_sec: float = 30.0) -> int:
        """Cancel any of our open orders older than max_age_sec. Returns count."""
        c = self._ensure_client()
        try:
            orders = c.get_open_orders()
        except Exception as e:
            print(f"[trader] get_open_orders failed: {e}", flush=True)
            return 0
        now = time.time()
        canceled = 0
        for o in orders or []:
            if not isinstance(o, dict):
                continue
            order_id = o.get("id") or o.get("orderID")
            if not order_id:
                continue
            # created_at field name varies — try multiple, parse defensively
            ts_raw = o.get("created_at") or o.get("createdAt") or o.get("timestamp")
            try:
                ts = float(ts_raw) if ts_raw else 0
                # Detect millis vs seconds heuristically
                if ts > 10**12:
                    ts = ts / 1000.0
            except (TypeError, ValueError):
                ts = 0
            if ts == 0 or now - ts < max_age_sec:
                continue
            ok, _ = self.cancel(order_id)
            if ok:
                canceled += 1
        return canceled

    # --- Journalling ---

    def _journal_order(
        self, *, market: LiveMarket, decision: Decision, status: str,
        order_id: Optional[str], error: Optional[str], raw: Optional[dict] = None,
    ) -> None:
        with connect(self.cfg.db_path) as conn:
            conn.execute(
                "INSERT INTO orders (ts, market_slug, condition_id, side, price, size, "
                "fill_price, fill_size, fee_paid, order_id, status, error, dry_run) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,0)",
                (
                    time.time(), market.slug, market.condition_id,
                    decision.side.value if decision.side else "",
                    decision.price, decision.size,
                    None, None, None,
                    order_id, status, error,
                ),
            )
