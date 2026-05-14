"""One-time setup before live trading. Idempotent — safe to re-run.

Steps:
  1. Verify wallet has POL (gas) and pUSD (collateral).
  2. Derive (or load) L2 API credentials, persist to .env.
  3. Update the CLOB exchange allowance via the SDK (so it can move pUSD on our behalf).
  4. Print a final readiness summary.

Does NOT place any order. Does NOT wrap USDC.e — use scripts/wrap_usdce.py for that first.
"""
from __future__ import annotations

import os
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bot.auth import get_or_derive_api_creds
from bot.config import load_config
from bot.trader import Trader
from polybot.chain import get_address, get_web3
from polybot.contracts import ERC20_ABI, PUSD


def check_balances(addr: str) -> tuple[Decimal, Decimal]:
    w3 = get_web3()
    pol = Decimal(w3.eth.get_balance(addr)) / Decimal(10**18)
    pusd_c = w3.eth.contract(address=w3.to_checksum_address(PUSD), abi=ERC20_ABI)
    raw = pusd_c.functions.balanceOf(addr).call()
    pusd = Decimal(raw) / Decimal(10**6)
    return pol, pusd


def main() -> int:
    cfg = load_config()
    addr = get_address()

    print(f"=== Step 1: balance check ===")
    pol, pusd = check_balances(addr)
    print(f"  Wallet : {addr}")
    print(f"  POL    : {pol:.6f}     (gas)")
    print(f"  pUSD   : {pusd:.6f}    (collateral)")
    if pol <= 0:
        print("  FATAL: no POL for gas. Send POL on Polygon to this wallet.")
        return 1
    if pusd <= 0:
        print("  WARN: no pUSD. Run scripts/wrap_usdce.py <amount> first.")
        # Continue anyway — we can still set up auth and allowance

    print(f"\n=== Step 2: L2 API credentials ===")
    pk = os.getenv("PRIVATE_KEY")
    chain = int(os.getenv("CHAIN_ID", "137"))
    creds = get_or_derive_api_creds(cfg.clob_host, chain, pk)
    print(f"  api_key: {creds.api_key[:8]}...{creds.api_key[-4:]}")
    print(f"  (api_secret + passphrase persisted to .env)")

    print(f"\n=== Step 3: Exchange allowance (on-chain approve from EOA) ===")
    from py_clob_client_v2.clob_types import AssetType, BalanceAllowanceParams
    from polybot.contracts import CTF_EXCHANGE, NEG_RISK_CTF_EXCHANGE, ERC20_ABI
    from eth_account import Account

    trader = Trader(cfg)
    client = trader._ensure_client()
    params = BalanceAllowanceParams(asset_type=AssetType.COLLATERAL)

    # Read current state via the API for visibility
    try:
        ba = client.get_balance_allowance(params=params)
        print(f"  Current pUSD balance/allowance (per SDK):")
        print(f"    balance: {int(ba.get('balance', 0))/1e6:.6f}")
        for exch_addr, allow in (ba.get("allowances") or {}).items():
            print(f"    allowance[{exch_addr}]: {int(allow)/1e6:.6f}")
    except Exception as e:
        print(f"  (read failed, continuing): {e}")

    # On-chain approve: pUSD.approve(<exchange>, large_amount)
    # We approve a generous amount (not max_uint, slightly safer): 1000 pUSD
    APPROVE_AMOUNT = 1000 * 10**6  # 1000 pUSD with 6 decimals
    EXCHANGES_TO_APPROVE = [
        ("CTF Exchange",          CTF_EXCHANGE),
        ("Neg Risk CTF Exchange", NEG_RISK_CTF_EXCHANGE),
    ]

    w3 = get_web3()
    pusd_c = w3.eth.contract(address=w3.to_checksum_address(PUSD), abi=ERC20_ABI)
    pk = os.getenv("PRIVATE_KEY")
    acct = Account.from_key(pk)
    nonce = w3.eth.get_transaction_count(addr)

    for label, exch in EXCHANGES_TO_APPROVE:
        exch_cs = w3.to_checksum_address(exch)
        current = pusd_c.functions.allowance(addr, exch_cs).call()
        print(f"\n  {label} ({exch_cs}):")
        print(f"    current allowance: {current/1e6:.6f} pUSD")
        if current >= APPROVE_AMOUNT:
            print(f"    already sufficient, skipping")
            continue
        print(f"    approving {APPROVE_AMOUNT/1e6:.0f} pUSD ...")
        tx = pusd_c.functions.approve(exch_cs, APPROVE_AMOUNT).build_transaction({
            "from": addr,
            "nonce": nonce,
            "chainId": w3.eth.chain_id,
        })
        signed = acct.sign_transaction(tx)
        h = w3.eth.send_raw_transaction(signed.raw_transaction)
        rcpt = w3.eth.wait_for_transaction_receipt(h, timeout=180)
        if rcpt.status != 1:
            print(f"    REVERTED: {h.hex()}")
            return 1
        print(f"    tx: {h.hex()}  block {rcpt.blockNumber}  ✓")
        nonce += 1

    # Re-read via SDK to confirm
    try:
        ba2 = client.get_balance_allowance(params=params)
        print(f"\n  Final pUSD allowances (per SDK):")
        for exch_addr, allow in (ba2.get("allowances") or {}).items():
            print(f"    {exch_addr}: {int(allow)/1e6:.6f}")
    except Exception as e:
        print(f"  Final read failed: {e}")

    print(f"\n=== Ready ===")
    print(f"  Run the bot live with: .venv/bin/python -m bot.main --live")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
