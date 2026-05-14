"""Wrap USDC.e -> pUSD via the Polymarket CollateralOnramp.

Usage:
    python scripts/wrap_usdce.py <amount>     # amount in USDC.e (e.g. "5" or "5.25")
    python scripts/wrap_usdce.py all          # wrap entire USDC.e balance
"""
from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from polybot.chain import get_account, get_address, get_web3
from polybot.contracts import (
    COLLATERAL_ONRAMP,
    ERC20_ABI,
    ONRAMP_ABI,
    PUSD,
    USDC_E,
)

USDCE_DECIMALS = 6


def parse_amount(arg: str, balance_units: int) -> int:
    if arg.lower() == "all":
        return balance_units
    try:
        return int(Decimal(arg) * (10**USDCE_DECIMALS))
    except Exception as e:
        raise SystemExit(f"Invalid amount {arg!r}: {e}")


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2

    w3 = get_web3()
    acct = get_account()
    addr = get_address()
    onramp = w3.to_checksum_address(COLLATERAL_ONRAMP)
    usdce_c = w3.eth.contract(address=w3.to_checksum_address(USDC_E), abi=ERC20_ABI)
    pusd_c = w3.eth.contract(address=w3.to_checksum_address(PUSD), abi=ERC20_ABI)
    onramp_c = w3.eth.contract(address=onramp, abi=ONRAMP_ABI)

    balance = usdce_c.functions.balanceOf(addr).call()
    amount_units = parse_amount(sys.argv[1], balance)

    if amount_units == 0:
        print("Nothing to wrap (amount is 0).")
        return 1
    if amount_units > balance:
        print(f"Insufficient USDC.e: have {balance/10**6:.6f}, need {amount_units/10**6:.6f}")
        return 1

    pol_balance = w3.eth.get_balance(addr)
    if pol_balance == 0:
        print("Wallet has 0 POL — cannot pay gas. Fund with POL first.")
        return 1

    print(f"Wallet     : {addr}")
    print(f"USDC.e bal : {balance/10**6:.6f}")
    print(f"Wrapping   : {amount_units/10**6:.6f} USDC.e -> pUSD")
    print(f"Recipient  : {addr}")
    print()

    nonce = w3.eth.get_transaction_count(addr)

    # 1. Approve onramp to spend USDC.e (only if current allowance is insufficient)
    current_allowance = usdce_c.functions.allowance(addr, onramp).call()
    if current_allowance < amount_units:
        print(f"[1/2] Approving CollateralOnramp to spend USDC.e ...")
        approve_tx = usdce_c.functions.approve(onramp, amount_units).build_transaction({
            "from": addr,
            "nonce": nonce,
            "chainId": w3.eth.chain_id,
        })
        signed = acct.sign_transaction(approve_tx)
        h = w3.eth.send_raw_transaction(signed.raw_transaction)
        rcpt = w3.eth.wait_for_transaction_receipt(h, timeout=180)
        if rcpt.status != 1:
            print(f"Approve reverted: {h.hex()}")
            return 1
        print(f"      tx: {h.hex()}  block {rcpt.blockNumber}")
        nonce += 1
    else:
        print(f"[1/2] Allowance already sufficient ({current_allowance/10**6:.6f}); skipping approve.")

    # 2. Wrap USDC.e -> pUSD
    print(f"[2/2] Calling Onramp.wrap(USDC.e, wallet, amount) ...")
    wrap_tx = onramp_c.functions.wrap(
        w3.to_checksum_address(USDC_E), addr, amount_units
    ).build_transaction({
        "from": addr,
        "nonce": nonce,
        "chainId": w3.eth.chain_id,
    })
    signed = acct.sign_transaction(wrap_tx)
    h = w3.eth.send_raw_transaction(signed.raw_transaction)
    rcpt = w3.eth.wait_for_transaction_receipt(h, timeout=180)
    if rcpt.status != 1:
        print(f"Wrap reverted: {h.hex()}")
        return 1
    print(f"      tx: {h.hex()}  block {rcpt.blockNumber}")

    new_pusd = pusd_c.functions.balanceOf(addr).call()
    new_usdce = usdce_c.functions.balanceOf(addr).call()
    print()
    print(f"Done. New balances:")
    print(f"  USDC.e: {new_usdce/10**6:.6f}")
    print(f"  pUSD  : {new_pusd/10**6:.6f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
