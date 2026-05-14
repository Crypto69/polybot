"""Path B (deposit wallet) live-trading prep.

Idempotent. Safe to re-run. Steps:
  1. Verify deposit wallet has pUSD and on-chain allowance is set.
  2. Derive (or load) L2 API credentials for the MetaMask signer.
  3. Sync the CLOB balance/allowance cache via signature_type=3.
  4. Print readiness summary.

Does NOT place any order.
"""
from __future__ import annotations

import os
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bot.auth import _read_env_var, get_or_derive_api_creds
from bot.config import load_config
from bot.trader import Trader
from polybot.chain import get_web3
from polybot.contracts import (
    CTF_EXCHANGE,
    ERC20_ABI,
    NEG_RISK_CTF_EXCHANGE,
    PUSD,
)
from py_clob_client_v2 import SignatureTypeV2
from py_clob_client_v2.clob_types import AssetType, BalanceAllowanceParams


def main() -> int:
    cfg = load_config()
    deposit = _read_env_var("DEPOSIT_WALLET")
    mm_addr = _read_env_var("MM_WALLET_ADDRESS")
    mm_pk = _read_env_var("MM_PRIVATE_KEY")
    if not (deposit and mm_addr and mm_pk):
        print("Missing one of MM_PRIVATE_KEY / MM_WALLET_ADDRESS / DEPOSIT_WALLET in .env")
        return 1

    print(f"=== Step 1: deposit wallet state ===")
    w3 = get_web3()
    pol = Decimal(w3.eth.get_balance(w3.to_checksum_address(deposit))) / Decimal(10**18)
    pusd_c = w3.eth.contract(address=w3.to_checksum_address(PUSD), abi=ERC20_ABI)
    pusd_bal = Decimal(pusd_c.functions.balanceOf(w3.to_checksum_address(deposit)).call()) / Decimal(10**6)
    ctf_allow = pusd_c.functions.allowance(
        w3.to_checksum_address(deposit), w3.to_checksum_address(CTF_EXCHANGE)
    ).call()
    nrisk_allow = pusd_c.functions.allowance(
        w3.to_checksum_address(deposit), w3.to_checksum_address(NEG_RISK_CTF_EXCHANGE)
    ).call()

    print(f"  Deposit wallet: {deposit}")
    print(f"    POL:          {pol:.6f}  (deposit wallets don't pay gas — relayer does)")
    print(f"    pUSD:         {pusd_bal:.6f}")
    print(f"    CTF allow:    {'MAX_UINT' if ctf_allow > 10**40 else f'{ctf_allow/1e6:.6f}'}")
    print(f"    NegRisk allow:{'MAX_UINT' if nrisk_allow > 10**40 else f'{nrisk_allow/1e6:.6f}'}")

    if pusd_bal == 0:
        print(f"  WARN: 0 pUSD. Run scripts/fund_deposit_wallet.py first.")
    if ctf_allow == 0 and nrisk_allow == 0:
        print(f"  WARN: 0 allowance. Use the Polymarket UI's 'Enable trading' button.")

    print(f"\n=== Step 2: L2 API credentials for MetaMask signer ===")
    chain = int(os.getenv("CHAIN_ID", "137"))
    creds = get_or_derive_api_creds(cfg.clob_host, chain, mm_pk, env_prefix="MM_CLOB")
    print(f"  api_key: {creds.api_key[:8]}...{creds.api_key[-4:]}")

    print(f"\n=== Step 3: CLOB balance/allowance cache (signature_type=3) ===")
    trader = Trader(cfg)
    client = trader._ensure_client()
    params = BalanceAllowanceParams(
        asset_type=AssetType.COLLATERAL,
        signature_type=SignatureTypeV2.POLY_1271,
    )
    try:
        ba = client.get_balance_allowance(params=params)
        print(f"  Pre-sync state:")
        print(f"    balance:    {int(ba.get('balance', 0))/1e6:.6f}")
        for k, v in (ba.get("allowances") or {}).items():
            v_int = int(v)
            print(f"    allow[{k}]: {'MAX_UINT' if v_int > 10**40 else f'{v_int/1e6:.6f}'}")
    except Exception as e:
        print(f"  Pre-sync read failed: {e}")

    try:
        client.update_balance_allowance(params=params)
        print(f"  update_balance_allowance(POLY_1271) succeeded")
        ba2 = client.get_balance_allowance(params=params)
        print(f"  Post-sync state:")
        print(f"    balance:    {int(ba2.get('balance', 0))/1e6:.6f}")
        for k, v in (ba2.get("allowances") or {}).items():
            v_int = int(v)
            print(f"    allow[{k}]: {'MAX_UINT' if v_int > 10**40 else f'{v_int/1e6:.6f}'}")
    except Exception as e:
        print(f"  update_balance_allowance failed: {e}")

    print(f"\n=== Ready ===")
    print(f"  Run live: .venv/bin/python -m bot.main --live")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
