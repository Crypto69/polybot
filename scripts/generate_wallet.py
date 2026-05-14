"""Generate a new EVM wallet and append it to .env.

Refuses to overwrite an existing PRIVATE_KEY entry — delete it manually first
if you really want a new wallet.
"""
from __future__ import annotations

import os
import stat
import sys
from pathlib import Path

from eth_account import Account

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"


def main() -> int:
    if ENV_PATH.exists() and "PRIVATE_KEY=" in ENV_PATH.read_text():
        print(
            "Refusing to overwrite: .env already contains PRIVATE_KEY. "
            "Delete it first if you really want a new wallet.",
            file=sys.stderr,
        )
        return 1

    Account.enable_unaudited_hdwallet_features()
    acct = Account.create()

    contents = "\n".join(
        [
            "# Polymarket trading wallet — Polygon mainnet (chain 137)",
            "# Generated locally; never commit this file.",
            f"PRIVATE_KEY={acct.key.hex()}",
            f"WALLET_ADDRESS={acct.address}",
            "CHAIN_ID=137",
            "CLOB_HOST=https://clob.polymarket.com",
            "GAMMA_HOST=https://gamma-api.polymarket.com",
            "",
        ]
    )

    ENV_PATH.write_text(contents)
    os.chmod(ENV_PATH, stat.S_IRUSR | stat.S_IWUSR)  # 0600
    print("Wallet generated and written to .env (mode 600).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
