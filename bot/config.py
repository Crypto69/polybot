"""Bot configuration. Single source of truth for tunable knobs."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(REPO_ROOT / ".env")


@dataclass(frozen=True)
class Config:
    # --- Strategy knobs ---
    max_entry_price: float = 0.95          # YouTube tutorial kept at 0.95 (didn't raise to 0.96)
    low_price_floor: float = 0.85          # raised from 0.55 per YouTube refinement #1
    seconds_before_close: int = 35         # tightened from 240 per YouTube refinement #3 — last 35s only
    min_t_remaining_seconds: int = 8       # YouTube refinement #4: don't fire in final ~7s (avoid losing race to liquidity-takers)
    book_observation_seconds: int = 300    # record full book snapshots in the last N seconds (probe mode)
    min_book_size_shares: float = 5.0      # at least this much liquidity must exist at our price
    spot_confidence_bps: float = 5         # require BTC spot to be > 0.05% off the open in our direction

    # --- Sizing ---
    order_size_shares: float = 4.0         # ~$3.80 collateral at price 0.95, ~$0.20 max upside

    # --- Risk caps ---
    max_open_positions: int = 1            # one position at a time
    daily_loss_cap_usd: float = 10.0       # kill-switch on cumulative session loss
    consecutive_losses_kill: int = 3       # kill-switch after N consecutive losing positions
    min_pusd_floor_usd: float = 0.50       # never let projected balance drop below this

    # --- Operations ---
    poll_interval_sec: float = 0.25        # how often to re-read the book (matches YouTube — 4 ticks/sec)
    market_refresh_sec: int = 30           # how often to re-discover open markets
    dry_run: bool = True                   # default safety: never send tx unless flipped
    db_path: Path = REPO_ROOT / "trades.db"

    # --- Endpoints ---
    gamma_host: str = os.getenv("GAMMA_HOST", "https://gamma-api.polymarket.com")
    clob_host: str = os.getenv("CLOB_HOST", "https://clob.polymarket.com")
    rpc_url: str = os.getenv("POLYGON_RPC_URL", "https://polygon-bor-rpc.publicnode.com")


def load_config(**overrides) -> Config:
    """Construct a Config, with optional overrides for tests / CLI flags."""
    base = Config()
    if not overrides:
        return base
    return Config(**{**base.__dict__, **overrides})
