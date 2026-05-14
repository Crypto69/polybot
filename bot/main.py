"""Bot main loop. Defaults to --dry-run; never sends transactions unless overridden."""
from __future__ import annotations

import argparse
import signal
import sys
import time
from collections import Counter
from typing import Optional

from decimal import Decimal

from .account import AccountState, fetch_account_state, fetch_pusd_balance
from .auth import _read_env_var
from .book import fetch_book
from .config import Config, load_config
from .journal import (
    get_market_open,
    record_book_tick,
    record_decision,
    record_market_open,
)
from .markets import LiveMarket, discover_open_markets, fetch_resolution
from .risk import allowed_to_trade
from .spot import fetch_spot
from .strategy import Action, decide
from .trader import Trader

_running = True


def _stop(*_):
    global _running
    _running = False
    print("\n[main] shutdown requested")


def _record_open_if_new(cfg: Config, market: LiveMarket, spot_now: float) -> None:
    """If we haven't yet recorded the spot at this market's open, do so now.

    This is best-effort: if we discover a market mid-window, we'll use whatever
    spot we observe at that moment as a proxy for the open. Not perfect but adequate.
    """
    if get_market_open(cfg.db_path, market.slug) is None:
        record_market_open(cfg.db_path, market=market, spot_at_open=spot_now)


def _snapshot_starting_balance() -> Decimal:
    """Read the deposit wallet's pUSD balance on-chain at session start."""
    deposit = _read_env_var("DEPOSIT_WALLET")
    if not deposit:
        return Decimal(0)
    try:
        return fetch_pusd_balance(deposit)
    except Exception as e:
        print(f"[main] WARN: starting balance read failed: {e}", flush=True)
        return Decimal(0)


def run(cfg: Config) -> int:
    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    print(f"[main] dry_run={cfg.dry_run}  max_entry_price={cfg.max_entry_price}  "
          f"seconds_before_close={cfg.seconds_before_close}", flush=True)
    print(f"[main] db: {cfg.db_path}", flush=True)

    trader: Trader | None = None
    session_start_balance = Decimal(0)
    traded_markets: set[str] = set()       # condition_ids submitted on this session
    if not cfg.dry_run:
        trader = Trader(cfg)
        try:
            addr = trader.address()
            print(f"[main] LIVE mode. Trader (signer) address: {addr}", flush=True)
        except Exception as e:
            print(f"[main] FATAL: trader auth failed: {e}", flush=True)
            return 2
        session_start_balance = _snapshot_starting_balance()
        print(f"[main] Session start pUSD balance: {session_start_balance:.6f}", flush=True)
        print(f"[main] Daily loss cap: ${cfg.daily_loss_cap_usd}  "
              f"min_floor: ${cfg.min_pusd_floor_usd}  max_open: {cfg.max_open_positions}",
              flush=True)

    markets: list[LiveMarket] = []
    last_market_refresh = 0.0
    last_stale_cancel = 0.0
    STALE_CANCEL_SEC = 5.0  # how often to check & cancel stale orders
    decision_counts: Counter = Counter()
    consecutive_errors = 0
    last_heartbeat = 0.0
    HEARTBEAT_SEC = 30.0
    kill_switch = False                                  # set on hard failure
    consecutive_losses = 0                               # streak of losing positions
    # Pending resolutions: list of dicts with slug, side, end_ts; checked each tick.
    pending_resolutions: list[dict] = []
    RESOLUTION_GRACE_SEC = 30.0                          # wait N sec past close for gamma to publish

    try:
        while _running:
            now = time.time()

            try:
                if now - last_market_refresh > cfg.market_refresh_sec or not markets:
                    markets = discover_open_markets(cfg, now=now)
                    last_market_refresh = now
            except Exception as e:
                consecutive_errors += 1
                print(f"[err] market discovery failed ({consecutive_errors}): {e}", flush=True)
                time.sleep(min(2 ** consecutive_errors, 30))
                continue

            try:
                spot = fetch_spot()
                spot_mid = spot.mid
                consecutive_errors = 0  # successful round-trip somewhere
            except Exception as e:
                spot_mid = None
                print(f"[warn] spot fetch failed: {e}", flush=True)

            # Live state query (only in live mode; dry-run skips this)
            account_state: AccountState | None = None
            if not cfg.dry_run and trader is not None and not kill_switch:
                try:
                    account_state = fetch_account_state(cfg, trader._ensure_client())
                except Exception as e:
                    print(f"[warn] account state query failed: {e}", flush=True)
                    account_state = AccountState(Decimal(0), 0, set(), set(), error=str(e))

            for m in markets:
                t_left = m.t_remaining(now)
                if t_left <= 0:
                    continue

                # Record the open price for any market — even ones far from close
                if spot_mid is not None:
                    _record_open_if_new(cfg, m, spot_mid)

                # Skip cheap if outside the observation window
                if t_left > cfg.book_observation_seconds:
                    continue

                try:
                    yes_book = fetch_book(cfg, m.yes_token_id)
                    no_book = fetch_book(cfg, m.no_token_id)
                except Exception as e:
                    print(f"[warn] book fetch failed for {m.slug}: {e}", flush=True)
                    continue

                spot_at_open = get_market_open(cfg.db_path, m.slug)

                # PROBE: record this book tick regardless of decision
                try:
                    record_book_tick(
                        cfg.db_path, market=m, yes_book=yes_book, no_book=no_book,
                        max_entry_price=cfg.max_entry_price,
                        spot_mid=spot_mid, spot_at_open=spot_at_open,
                    )
                except Exception as e:
                    print(f"[warn] tick record failed: {e}", flush=True)

                # Decision logic only fires in the action window
                if t_left > cfg.seconds_before_close:
                    consecutive_errors = 0
                    continue

                d = decide(
                    cfg=cfg, market=m,
                    yes_book=yes_book, no_book=no_book,
                    spot_now=spot_mid or 0.0, spot_at_open=spot_at_open,
                    now=now,
                )
                decision_counts[d.action.value] += 1

                record_decision(
                    cfg.db_path, market=m, decision=d,
                    books={"yes": yes_book, "no": no_book},
                    spot_mid=spot_mid, spot_at_open=spot_at_open,
                    dry_run=cfg.dry_run,
                )

                if d.action == Action.BUY:
                    if cfg.dry_run:
                        print(f"[DRY] BUY {d.side.value} @ {d.price} x {d.size} "
                              f"on {m.slug} (t={t_left:.0f}s, {d.reason})", flush=True)
                        continue

                    # LIVE: enforce risk before sending the order
                    assert trader is not None
                    if kill_switch:
                        continue
                    if account_state is None:
                        print(f"[risk] no account state, blocking BUY", flush=True)
                        continue

                    order_collateral = Decimal(str(d.price)) * Decimal(str(d.size))
                    allowed, reason = allowed_to_trade(
                        cfg,
                        state=account_state,
                        market_condition_id=m.condition_id,
                        traded_markets=traded_markets,
                        session_start_balance=session_start_balance,
                        order_collateral_usd=order_collateral,
                    )
                    if not allowed:
                        print(f"[risk] BUY blocked on {m.slug}: {reason}", flush=True)
                        # If we hit the daily cap, arm the kill switch
                        if "daily loss cap" in reason:
                            kill_switch = True
                            print(f"[risk] *** KILL SWITCH ARMED — no further trades this session ***",
                                  flush=True)
                        continue

                    # Mark this market as touched BEFORE submitting — even if the
                    # request fails or times out, we never re-try the same market.
                    traded_markets.add(m.condition_id)
                    result = trader.place_buy(market=m, decision=d)
                    if result.ok:
                        print(f"[LIVE] BUY placed: order_id={result.order_id} "
                              f"status={result.status} {m.slug} "
                              f"{d.side.value} @ {d.price} x {d.size} "
                              f"(collateral ${order_collateral:.4f})", flush=True)
                        # Queue this position for outcome tracking (condition_id is the
                        # canonical key the CLOB resolver uses; slug is just for logging).
                        pending_resolutions.append({
                            "slug": m.slug,
                            "condition_id": m.condition_id,
                            "side": d.side.value,
                            "end_ts": m.end_ts,
                        })
                    else:
                        print(f"[LIVE] BUY FAILED on {m.slug}: {result.error}", flush=True)
                elif d.action == Action.SKIP:
                    # only print rare/interesting skips to avoid log spam
                    if "spot disagrees" in d.reason or "uncertain" in d.reason:
                        print(f"[skip] {m.slug} t={t_left:.0f}s: {d.reason}", flush=True)

            # Process pending resolutions — detect wins/losses, update streak, arm kill switch.
            if pending_resolutions:
                still_pending: list[dict] = []
                for pr in pending_resolutions:
                    if now < pr["end_ts"] + RESOLUTION_GRACE_SEC:
                        still_pending.append(pr)
                        continue
                    try:
                        outcome = fetch_resolution(cfg, pr["condition_id"])
                    except Exception as e:
                        print(f"[warn] resolution fetch failed for {pr['slug']}: {e}", flush=True)
                        still_pending.append(pr)
                        continue
                    if outcome is None:
                        # Not yet published. Keep waiting (capped indirectly by gamma's TTL).
                        still_pending.append(pr)
                        continue
                    if outcome == pr["side"]:
                        consecutive_losses = 0
                        print(f"[outcome] WIN  {pr['slug']}: bought {pr['side']}, "
                              f"resolved {outcome}  (streak reset)", flush=True)
                    else:
                        consecutive_losses += 1
                        print(f"[outcome] LOSS {pr['slug']}: bought {pr['side']}, "
                              f"resolved {outcome}  (streak: {consecutive_losses}"
                              f"/{cfg.consecutive_losses_kill})", flush=True)
                        if consecutive_losses >= cfg.consecutive_losses_kill:
                            kill_switch = True
                            print(f"[risk] *** KILL SWITCH: {consecutive_losses} consecutive "
                                  f"losses — no further trades this session ***", flush=True)
                pending_resolutions = still_pending

            # Stale-order cancel sweep (live mode only)
            if not cfg.dry_run and trader is not None and now - last_stale_cancel > STALE_CANCEL_SEC:
                last_stale_cancel = now
                try:
                    n = trader.cancel_stale(max_age_sec=30.0)
                    if n:
                        print(f"[trader] canceled {n} stale orders", flush=True)
                except Exception as e:
                    print(f"[warn] stale-cancel failed: {e}", flush=True)

            # Heartbeat
            if now - last_heartbeat > HEARTBEAT_SEC:
                last_heartbeat = now
                soonest = min((m.t_remaining(now) for m in markets), default=float("inf"))
                bal_str = ""
                if not cfg.dry_run and account_state and not account_state.error:
                    delta = account_state.pusd_balance - session_start_balance
                    bal_str = (f" pUSD={account_state.pusd_balance:.4f} "
                               f"(Δ{delta:+.4f}) traded={len(traded_markets)} "
                               f"open={account_state.open_order_count} "
                               f"pending={len(pending_resolutions)} "
                               f"loss_streak={consecutive_losses}/{cfg.consecutive_losses_kill}"
                               f"{' KILLED' if kill_switch else ''}")
                print(f"[hb] markets={len(markets)} soonest_close={soonest:.0f}s "
                      f"decisions={dict(decision_counts)} spot={spot_mid}{bal_str}", flush=True)

            # Brief sleep between ticks
            time.sleep(cfg.poll_interval_sec)

    finally:
        print(f"\n[main] decision counts so far: {dict(decision_counts)}")
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Polybot — Polymarket BTC up/down trader.")
    parser.add_argument(
        "--live", action="store_true",
        help="Send real orders. Default is dry-run (decisions logged, no orders).",
    )
    parser.add_argument("--max-entry-price", type=float)
    parser.add_argument("--seconds-before-close", type=int)
    args = parser.parse_args(argv)

    overrides: dict = {"dry_run": not args.live}
    if args.max_entry_price is not None:
        overrides["max_entry_price"] = args.max_entry_price
    if args.seconds_before_close is not None:
        overrides["seconds_before_close"] = args.seconds_before_close

    cfg = load_config(**overrides)
    return run(cfg)


if __name__ == "__main__":
    sys.exit(main())
