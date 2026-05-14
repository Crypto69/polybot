"""L1 -> L2 API credential derivation, with persistence to .env.

Polymarket's CLOB uses two-tier auth:
  - L1: your EVM private key (signs individual orders).
  - L2: derived API key/secret/passphrase (REST authentication).

We support two paths, picked at make_client() time based on what's in .env:

  PATH A (legacy EOA — signature_type=0):
    - Uses PRIVATE_KEY + WALLET_ADDRESS as funder.
    - Polymarket's API REJECTS this for new wallets ("maker address not allowed").
    - Kept around for any grandfathered/proxy wallets.

  PATH B (deposit wallet — signature_type=3 / POLY_1271):
    - Uses MM_PRIVATE_KEY (MetaMask EOA) + DEPOSIT_WALLET (Polymarket-deployed) as funder.
    - This is the path Polymarket requires for new accounts.
    - L2 creds derived for the MM EOA (the signer).
"""
from __future__ import annotations

import os
from pathlib import Path

from py_clob_client_v2 import ClobClient, SignatureTypeV2
from py_clob_client_v2.clob_types import ApiCreds

REPO_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = REPO_ROOT / ".env"


def _read_env_var(name: str) -> str | None:
    if val := os.getenv(name):
        return val
    if not ENV_PATH.exists():
        return None
    for line in ENV_PATH.read_text().splitlines():
        line = line.strip()
        if line.startswith(f"{name}="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


def _upsert_env(updates: dict[str, str]) -> None:
    """Insert or REPLACE keys in .env. Used for refreshing CLOB creds when signer changes."""
    if not ENV_PATH.exists():
        ENV_PATH.write_text("")
    lines = ENV_PATH.read_text().splitlines()
    seen = set()
    new_lines = []
    for line in lines:
        if "=" not in line or line.lstrip().startswith("#"):
            new_lines.append(line)
            continue
        key = line.split("=", 1)[0].strip()
        if key in updates:
            new_lines.append(f"{key}={updates[key]}")
            seen.add(key)
        else:
            new_lines.append(line)
    for k, v in updates.items():
        if k not in seen:
            new_lines.append(f"{k}={v}")
    ENV_PATH.write_text("\n".join(new_lines) + "\n")
    os.chmod(ENV_PATH, 0o600)


def _path_b_configured() -> bool:
    """Return True if all three deposit-wallet env vars are present."""
    return all(_read_env_var(k) for k in ("MM_PRIVATE_KEY", "MM_WALLET_ADDRESS", "DEPOSIT_WALLET"))


def get_or_derive_api_creds(host: str, chain_id: int, private_key: str,
                            *, env_prefix: str = "CLOB",
                            signature_type: int = 0,
                            funder: str | None = None) -> ApiCreds:
    """Return cached L2 creds if present, else derive and persist.

    For deposit-wallet flows, pass signature_type=POLY_1271 (=3) and the deposit
    wallet as funder so the SDK derives creds bound to the right (signer, funder)
    pair. EOA flows can omit these.

    env_prefix lets us cache different signers' creds separately (CLOB_ vs MM_CLOB_).
    """
    key_var = f"{env_prefix}_API_KEY"
    secret_var = f"{env_prefix}_API_SECRET"
    pass_var = f"{env_prefix}_API_PASSPHRASE"

    api_key = _read_env_var(key_var)
    api_secret = _read_env_var(secret_var)
    api_passphrase = _read_env_var(pass_var)
    if api_key and api_secret and api_passphrase:
        return ApiCreds(
            api_key=api_key, api_secret=api_secret, api_passphrase=api_passphrase,
        )

    temp_kwargs = {"host": host, "chain_id": chain_id, "key": private_key}
    if funder:
        temp_kwargs["signature_type"] = signature_type
        temp_kwargs["funder"] = funder
    temp = ClobClient(**temp_kwargs)
    creds = temp.create_or_derive_api_key()
    _upsert_env({
        key_var: creds.api_key,
        secret_var: creds.api_secret,
        pass_var: creds.api_passphrase,
    })
    return creds


def make_client(host: str, chain_id: int) -> ClobClient:
    """Build a fully-authenticated ClobClient.

    Picks Path B (deposit wallet, signature_type=3) if MM_* vars are configured,
    otherwise falls back to legacy Path A (EOA, signature_type=0).
    """
    if _path_b_configured():
        signer_pk = _read_env_var("MM_PRIVATE_KEY")
        funder = _read_env_var("DEPOSIT_WALLET")
        creds = get_or_derive_api_creds(
            host, chain_id, signer_pk,
            env_prefix="MM_CLOB",
            signature_type=int(SignatureTypeV2.POLY_1271),
            funder=funder,
        )
        return ClobClient(
            host=host, chain_id=chain_id, key=signer_pk, creds=creds,
            signature_type=SignatureTypeV2.POLY_1271, funder=funder,
        )

    # Path A fallback (rejected by Polymarket for new wallets — kept for grandfathered)
    signer_pk = _read_env_var("PRIVATE_KEY")
    funder = _read_env_var("WALLET_ADDRESS")
    creds = get_or_derive_api_creds(host, chain_id, signer_pk, env_prefix="CLOB")
    return ClobClient(
        host=host, chain_id=chain_id, key=signer_pk, creds=creds,
        signature_type=SignatureTypeV2.EOA, funder=funder,
    )
