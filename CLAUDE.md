# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Trading bot for Polymarket's recurring BTC up/down markets (5-min and 15-min windows). Strategy is "late-window convergence" — see `docs/research/PLAN.md` for the empirical basis (derived from analyzing a profitable trader's 4,000+ on-chain trades). The bot does **not** predict BTC direction; it waits until one outcome is already mathematically near-decided, then buys it at a discount to $1.00 with an independent BTC spot reading as a cross-check.

## Commands

Install deps and run (a `.venv` is checked into the repo's ignore list, not the repo itself):

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Dry-run loop (DEFAULT — never sends real orders)
python -m bot.main

# Live (requires .env configured for one of the two auth paths)
python -m bot.main --live

# Knob overrides
python -m bot.main --max-entry-price 0.92 --seconds-before-close 180
```

Operational scripts (each is standalone — `python scripts/<name>.py`):

- `scripts/prepare_live_b.py` — idempotent readiness check for the deposit-wallet (Path B) live setup. Verifies pUSD balance, on-chain allowances, derives/caches L2 creds. Run before flipping `--live`.
- `scripts/prepare_live.py` — same idea for the legacy EOA (Path A) setup.
- `scripts/check_balance.py` — read pUSD/USDC.e/POL balances for configured wallets.
- `scripts/backtest.py` — sweep strategy parameters against recorded `book_ticks` to pick `seconds_before_close`, `max_entry_price`, `spot_confidence_bps` before risking capital.
- `scripts/analyze_dry_run.py`, `scripts/analyze_book_ticks.py` — post-hoc analysis of the SQLite journal.
- `scripts/fund_deposit_wallet.py`, `scripts/wrap_usdce.py`, `scripts/verify_onramp.py`, `scripts/generate_wallet.py` — one-shot setup helpers.

There is no test suite or linter wired up. The journal in `trades.db` (created on first run) **is** the test feedback loop — run dry-run for an hour, then `scripts/backtest.py` to evaluate hypothetical fills.

Real-time dashboard (optional, read-only — safe to run alongside a live bot):

```bash
.venv/bin/pip install -r dashboard/requirements.txt          # one-time
cd dashboard/frontend && npm install && npm run build && cd - # one-time
python dashboard/server.py                                    # → http://127.0.0.1:8787
```

See `dashboard/README.md` for dev mode (Vite hot-reload) and details.

## Architecture

Two top-level packages with distinct responsibilities — do not merge them:

- **`bot/`** — the trading loop and its inputs. All higher-level logic.
- **`polybot/`** — minimal web3/Polygon helpers (RPC, account, contract addresses, ABI fragments). Imported by `bot/` and by `scripts/`. Kept separate so scripts can use chain primitives without dragging in the trading loop.

`dashboard/` is a **separate process**, not part of the trading code — see "Dashboard" below. It may *import read-only helpers* from `bot/` (config, `markets.fetch_resolution`, `account.fetch_pusd_balance`) but the dependency is strictly one-directional: `bot/` must never import `dashboard/`.

### `bot/` module relationships

```
main.py ──► markets.py    (discover_open_markets — probes gamma API by slug pattern)
        ──► book.py       (fetch_book — CLOB order book snapshot via HTTP)
        ──► spot.py       (fetch_spot — Binance + Coinbase midpoint)
        ──► strategy.py   (decide — pure function, no I/O)
        ──► risk.py       (allowed_to_trade — independent of strategy; gates live BUYs)
        ──► account.py    (fetch_account_state — on-chain pUSD + open orders/positions)
        ──► trader.py     (place_buy / cancel — live order placement only)
        ──► journal.py    (SQLite — every decision, tick, order, market open)
        ──► auth.py       (L1→L2 credential derivation; picks Path A or B from .env)
        ──► config.py     (frozen dataclass; single source of truth for knobs)
```

`strategy.decide()` is the only file expressing the trading idea. It's a pure function: given market state, books, spot, and config, return BUY or SKIP with a reason. **All knobs live in `config.py`** — don't introduce flags elsewhere; thread them through `Config`.

### Dry-run vs live separation

`cfg.dry_run` defaults to `True`. The loop in `main.py` keeps these paths cleanly split:

- **Dry-run** never instantiates `Trader`, never queries `AccountState`, never calls `risk.allowed_to_trade`. It records every decision to `decisions` with `dry_run=1` and every observation to `book_ticks` regardless of decision.
- **Live** instantiates `Trader` once (lazy SDK client), polls `AccountState` each tick, and gates every BUY through `risk.allowed_to_trade` (cooldown, position dedup, balance floor, daily loss cap). Stale-order cancel sweep runs every 5 s.

Because `book_ticks` is recorded in both modes, the backtester can replay the same ticks under different parameter values without ever needing live data.

### Dashboard (dashboard/) — read-only monitor

A FastAPI + Vue 3 process that tails `trades.db` and streams it to a terminal-style UI over WebSocket. **Hard invariants — do not break them:**

- **Strictly read-only and decoupled.** It opens SQLite with `mode=ro`, never writes the journal, never holds a write lock, and never imports the trading loop (`bot.main`/`trader`/`risk`). It must remain safe to run while the bot trades live. Any change that adds a write path or a `bot/` runtime dependency is wrong.
- **P&L is single-sourced with `scripts/analyze_dry_run.py`.** `server.py`'s `_trade_pnl()` uses the identical accounting (win `(1-price)*size`, loss `-price*size`, fee `0.07*(1-price)^1 * size*price`). If the fee model in `docs/research/PLAN.md` / `markets.fee_for_buy` changes, update **all three** together or they will disagree.
- **Backend deps stay in `dashboard/requirements.txt`**, never the bot's `requirements.txt` — the trading loop's runtime footprint must not grow for a monitor.
- Frontend build artifacts (`dashboard/frontend/node_modules/`, `dist/`) are gitignored; `server.py` serves `dist/` if present, else use Vite dev mode. It binds `127.0.0.1` only and trusts any local client — never expose it.

The dashboard derives realised P&L by enriching BUY `decisions` with market resolutions (`markets.fetch_resolution`); it does **not** rely on the `orders`/`outcomes` tables (orders frequently error without filling). Decision-level P&L = strategy edge; the Orders panel separately shows actual placement status.

### Two auth paths (auth.py)

Polymarket's CLOB uses two-tier auth: L1 (EVM key signs orders) → L2 (derived REST API key/secret/passphrase, cached in `.env`).

- **Path A — legacy EOA, signature_type=0** (`PRIVATE_KEY` + `WALLET_ADDRESS`). Rejected by Polymarket for new wallets ("maker address not allowed"). Kept for grandfathered accounts.
- **Path B — deposit wallet, signature_type=3 / POLY_1271** (`MM_PRIVATE_KEY` + `MM_WALLET_ADDRESS` + `DEPOSIT_WALLET`). Required for new accounts. Signer is the MetaMask EOA; funder is a Polymarket-deployed ERC-1967 proxy that holds the pUSD.

`make_client()` picks Path B if all three `MM_*`/`DEPOSIT_WALLET` vars are present, else falls back to Path A. L2 creds for each signer are cached under separate env prefixes (`CLOB_*` vs `MM_CLOB_*`) so switching paths doesn't clobber the other's creds.

If you change which signer is in use, also clear the corresponding `*_API_KEY/SECRET/PASSPHRASE` — derived creds are tied to a specific signer address.

### Market settlement currency

Polymarket settles in **pUSD** (`polymarket.md` and `polymarketUSD.md` are mirrored upstream docs). Users fund the wallet with **USDC.e** and wrap to pUSD via the `COLLATERAL_ONRAMP` contract — that's what `wrap_usdce.py` and `verify_onramp.py` are for. All trading balance checks (`account.fetch_pusd_balance`) read pUSD directly from the contract, not USDC.e.

### Strategy knobs that move together

These three are coupled — when calibrating from `book_ticks`, sweep them as a grid (see `scripts/backtest.py`):

- `max_entry_price` (default 0.90, narrowed from 0.95) — hard ceiling per share; **also** the price used for the `buyable_at_cap` liquidity check in `book.py`. Targets the 0.85–0.90 bucket only (the ~break-even band per the YouTube trader's data).
- `seconds_before_close` (default 35, tightened from 240 per "YouTube refinement #3") — the action window. Outside it, the loop records ticks but never decides BUY.
- `book_observation_seconds` (default 300) — separate, wider window for *recording* book snapshots into `book_ticks`. The journal captures the full last 5 min even though entries only fire in the last 35 s, so the backtester can replay surrounding context.
- `spot_confidence_bps` (default 5) — minimum BTC move from window open required before the spot signal is trusted as a directional confirmation.

`docs/research/PLAN.md` documents the empirical fee model: **taker fee = `fee_rate * (1 - price) ^ exponent`**, fee_rate=0.07, exponent=1. Fee is highest at low prices (the opposite of what some third-party docs claim). This is why entering at $0.99 is unprofitable for our scale: the fee eats the gross edge.
