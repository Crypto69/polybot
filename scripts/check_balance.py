"""Check wallet balances on Polygon: POL (gas), USDC.e (collateral input), pUSD (settlement)."""
from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from polybot.chain import get_address, get_web3
from polybot.contracts import ERC20_ABI, PUSD, USDC_E


def erc20_balance(w3, token_addr: str, holder: str) -> tuple[Decimal, str, int]:
    c = w3.eth.contract(address=w3.to_checksum_address(token_addr), abi=ERC20_ABI)
    raw = c.functions.balanceOf(holder).call()
    decimals = c.functions.decimals().call()
    symbol = c.functions.symbol().call()
    return Decimal(raw) / Decimal(10**decimals), symbol, decimals


def main() -> int:
    w3 = get_web3()
    addr = get_address()

    pol = Decimal(w3.eth.get_balance(addr)) / Decimal(10**18)
    usdce, _, usdce_dec = erc20_balance(w3, USDC_E, addr)
    pusd, _, pusd_dec = erc20_balance(w3, PUSD, addr)

    print(f"Address : {addr}")
    print(f"RPC     : {w3.provider.endpoint_uri}")
    print()
    print(f"POL     : {pol:.6f}                        gas")
    print(f"USDC.e  : {usdce:.{usdce_dec}f}                       fund-with (wrap to pUSD)")
    print(f"pUSD    : {pusd:.{pusd_dec}f}                       trading collateral")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
