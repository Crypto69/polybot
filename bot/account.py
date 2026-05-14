"""Live account state queries — ground truth from chain + Polymarket APIs.

Never trust the local DB for risk decisions. Always query the source of truth.

Verified against the SDK on 2026-05-14:
  - get_open_orders() returns list[dict] with field "market" = condition_id (hex 0x...).
  - data-api positions returns list[dict] with field "conditionId".
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

import requests
from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware

from .auth import _read_env_var
from .config import Config


@dataclass(frozen=True)
class AccountState:
    """Snapshot of the deposit wallet at a point in time."""
    pusd_balance: Decimal              # on-chain ground truth
    open_order_count: int              # via SDK
    open_order_markets: set[str]       # condition_ids of markets we have open orders on
    position_markets: set[str]         # condition_ids of markets we hold tokens on
    error: Optional[str] = None        # if any query failed; treat as "block trades"


_PUSD_ADDR = "0xC011a7E12a19f7B1f670d46F03B03f3342E82DFB"
_BAL_OF = "0x70a08231"  # balanceOf(address)
_w3_singleton: Optional[Web3] = None


def _w3() -> Web3:
    global _w3_singleton
    if _w3_singleton is None:
        rpc = os.getenv("POLYGON_RPC_URL", "https://polygon-bor-rpc.publicnode.com")
        w3 = Web3(Web3.HTTPProvider(rpc, request_kwargs={"timeout": 10}))
        w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
        _w3_singleton = w3
    return _w3_singleton


def fetch_pusd_balance(address: str) -> Decimal:
    """On-chain pUSD balance. The ground truth."""
    w3 = _w3()
    data = _BAL_OF + "0" * 24 + address[2:].lower()
    raw = w3.eth.call({"to": w3.to_checksum_address(_PUSD_ADDR), "data": data})
    return Decimal(int.from_bytes(raw, "big")) / Decimal(10**6)


def fetch_account_state(cfg: Config, client) -> AccountState:
    """Pull balance, open orders, and positions for the deposit wallet."""
    deposit = _read_env_var("DEPOSIT_WALLET")
    if not deposit:
        return AccountState(Decimal(0), 0, set(), set(), error="DEPOSIT_WALLET missing")

    try:
        bal = fetch_pusd_balance(deposit)
    except Exception as e:
        return AccountState(Decimal(0), 0, set(), set(), error=f"pUSD balance read failed: {e}")

    # Open orders via SDK (verified field name = "market")
    try:
        orders = client.get_open_orders() or []
    except Exception as e:
        return AccountState(bal, 0, set(), set(), error=f"get_open_orders failed: {e}")
    open_order_markets: set[str] = set()
    for o in orders:
        if isinstance(o, dict):
            cid = o.get("market") or o.get("condition_id") or o.get("conditionId")
            if cid:
                open_order_markets.add(cid)

    # Positions via data-api — fail closed (treat outage as "block trades")
    try:
        r = requests.get(
            "https://data-api.polymarket.com/positions",
            params={"user": deposit, "limit": 200},
            timeout=8,
        )
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        return AccountState(
            bal, len(orders), open_order_markets, set(),
            error=f"positions read failed (failing closed): {e}",
        )
    position_markets: set[str] = set()
    if isinstance(data, list):
        for p in data:
            cid = p.get("conditionId")
            if cid:
                position_markets.add(cid)

    return AccountState(
        pusd_balance=bal,
        open_order_count=len(orders),
        open_order_markets=open_order_markets,
        position_markets=position_markets,
    )
