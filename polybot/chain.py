"""Shared web3/account helpers — load wallet from .env, build a Polygon client."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from eth_account import Account
from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware

REPO_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(REPO_ROOT / ".env")


def get_web3() -> Web3:
    rpc = os.getenv("POLYGON_RPC_URL", "https://polygon-bor-rpc.publicnode.com")
    w3 = Web3(Web3.HTTPProvider(rpc, request_kwargs={"timeout": 20}))
    # Polygon is PoA — extraData field is too long for default middleware
    w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
    return w3


def get_account() -> Account:
    pk = os.getenv("PRIVATE_KEY")
    if not pk:
        raise RuntimeError("PRIVATE_KEY missing from .env")
    return Account.from_key(pk)


def get_address() -> str:
    addr = os.getenv("WALLET_ADDRESS")
    if not addr:
        raise RuntimeError("WALLET_ADDRESS missing from .env")
    return Web3.to_checksum_address(addr)
