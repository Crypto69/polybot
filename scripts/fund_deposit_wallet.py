"""Transfer pUSD from our existing EOA to the Polymarket deposit wallet.

Reads PRIVATE_KEY (existing EOA) and DEPOSIT_WALLET (target) from .env.
Transfers `amount` pUSD on Polygon. One on-chain tx.
"""
from __future__ import annotations

import os
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
from eth_account import Account
from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware

from polybot.contracts import ERC20_ABI, PUSD

REPO_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(REPO_ROOT / ".env", override=True)


def main() -> int:
    if len(sys.argv) != 2:
        print(f"Usage: python {sys.argv[0]} <amount_pusd>")
        return 2

    amount = Decimal(sys.argv[1])
    amount_units = int(amount * Decimal(10**6))

    src_pk = os.getenv("PRIVATE_KEY")
    src_addr = os.getenv("WALLET_ADDRESS")
    deposit = os.getenv("DEPOSIT_WALLET")
    if not src_pk or not src_addr or not deposit:
        print("Missing PRIVATE_KEY / WALLET_ADDRESS / DEPOSIT_WALLET in .env")
        return 1

    rpc = os.getenv("POLYGON_RPC_URL", "https://polygon-bor-rpc.publicnode.com")
    w3 = Web3(Web3.HTTPProvider(rpc, request_kwargs={"timeout": 20}))
    w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)

    src = w3.to_checksum_address(src_addr)
    dst = w3.to_checksum_address(deposit)
    pusd = w3.eth.contract(address=w3.to_checksum_address(PUSD), abi=ERC20_ABI)

    src_bal = pusd.functions.balanceOf(src).call()
    dst_bal_before = pusd.functions.balanceOf(dst).call()
    print(f"Source EOA      : {src}")
    print(f"  pUSD before   : {src_bal/1e6:.6f}")
    print(f"Deposit wallet  : {dst}")
    print(f"  pUSD before   : {dst_bal_before/1e6:.6f}")
    print(f"Transferring    : {amount} pUSD ({amount_units} base units)")
    print()

    if src_bal < amount_units:
        print(f"Insufficient pUSD on source: have {src_bal/1e6}, need {amount}")
        return 1

    acct = Account.from_key(src_pk)
    nonce = w3.eth.get_transaction_count(src)
    tx = pusd.functions.transfer(dst, amount_units).build_transaction({
        "from": src,
        "nonce": nonce,
        "chainId": w3.eth.chain_id,
    })
    signed = acct.sign_transaction(tx)
    h = w3.eth.send_raw_transaction(signed.raw_transaction)
    print(f"Sent: {h.hex()}  (waiting for confirmation...)")
    rcpt = w3.eth.wait_for_transaction_receipt(h, timeout=180)
    if rcpt.status != 1:
        print(f"REVERTED at block {rcpt.blockNumber}")
        return 1
    print(f"Confirmed at block {rcpt.blockNumber}")

    src_after = pusd.functions.balanceOf(src).call()
    dst_after = pusd.functions.balanceOf(dst).call()
    print(f"\nNew balances:")
    print(f"  Source pUSD       : {src_after/1e6:.6f}")
    print(f"  Deposit pUSD      : {dst_after/1e6:.6f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
