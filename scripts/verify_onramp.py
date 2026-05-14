"""Verify which token the Polymarket CollateralOnramp accepts and inspect pUSD."""
from __future__ import annotations

import os
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

RPC = os.getenv("POLYGON_RPC_URL", "https://polygon-bor-rpc.publicnode.com")

PUSD = "0xC011a7E12a19f7B1f670d46F03B03f3342E82DFB"
ONRAMP = "0x93070a847efEf7F70739046A929D47a521F5B8ee"
OFFRAMP = "0x2957922Eb93258b93368531d39fAcCA3B4dC5854"
USDC_NATIVE = "0x3c499c542cef5e3811e1192ce70d8cc03d5c3359"
USDC_E = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"

# Common ERC-20/getter selectors
SEL = {
    "name()":           "0x06fdde03",
    "symbol()":         "0x95d89b41",
    "decimals()":       "0x313ce567",
    "totalSupply()":    "0x18160ddd",
    # Possible onramp/wrapper getters
    "underlying()":     "0x6f307dc3",
    "asset()":          "0x38d52e0f",
    "token()":          "0xfc0c546a",
    "usdc()":           "0x3e413bee",  # keccak("usdc()")[:4]
    "collateral()":     "0xd8dfeb45",
    "inputToken()":     "0x42b5e0d2",
    "collateralToken()":"0x97c455c4",
}


def call(to: str, data: str) -> str | None:
    r = requests.post(
        RPC,
        json={"jsonrpc": "2.0", "id": 1, "method": "eth_call",
              "params": [{"to": to, "data": data}, "latest"]},
        timeout=15,
    )
    body = r.json()
    if "error" in body:
        return None
    res = body.get("result")
    return res if res and res != "0x" else None


def get_code_size(addr: str) -> int:
    r = requests.post(
        RPC,
        json={"jsonrpc": "2.0", "id": 1, "method": "eth_getCode",
              "params": [addr, "latest"]},
        timeout=15,
    ).json()
    return (len(r["result"]) - 2) // 2  # bytes


def decode_string(hexres: str) -> str | None:
    if not hexres:
        return None
    raw = bytes.fromhex(hexres[2:])
    if len(raw) < 64:
        return raw.rstrip(b"\x00").decode("utf8", errors="replace")
    # Standard ABI string: offset(32) + len(32) + data
    try:
        strlen = int.from_bytes(raw[32:64], "big")
        return raw[64:64 + strlen].decode("utf8", errors="replace")
    except Exception:
        return None


def decode_address(hexres: str) -> str | None:
    if not hexres or len(hexres) < 66:
        return None
    return "0x" + hexres[-40:]


def inspect_token(label: str, addr: str) -> None:
    print(f"\n--- {label} ({addr}) ---")
    print(f"  code size: {get_code_size(addr)} bytes")
    for sig, sel in [("name()", SEL["name()"]), ("symbol()", SEL["symbol()"]),
                     ("decimals()", SEL["decimals()"])]:
        res = call(addr, sel)
        if res is None:
            print(f"  {sig}: <no response>")
        elif sig == "decimals()":
            print(f"  {sig}: {int(res, 16)}")
        else:
            print(f"  {sig}: {decode_string(res)!r}")


def probe_onramp(label: str, addr: str) -> None:
    print(f"\n--- {label} ({addr}) ---")
    print(f"  code size: {get_code_size(addr)} bytes")
    for sig, sel in SEL.items():
        if sig in ("name()", "symbol()", "decimals()", "totalSupply()"):
            continue
        res = call(addr, sel)
        if res:
            decoded_addr = decode_address(res)
            print(f"  {sig:20s} -> {res}  (addr? {decoded_addr})")


def main() -> None:
    print(f"RPC: {RPC}")
    inspect_token("pUSD",       PUSD)
    inspect_token("USDC native", USDC_NATIVE)
    inspect_token("USDC.e",     USDC_E)
    probe_onramp("CollateralOnramp",  ONRAMP)
    probe_onramp("CollateralOfframp", OFFRAMP)


if __name__ == "__main__":
    main()
