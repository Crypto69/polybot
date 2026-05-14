"""SQLite journal for every decision, order, and outcome.

Schema is denormalized on purpose — easy to query in dry-run analysis without joins.
"""
from __future__ import annotations

import json
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

SCHEMA = """
CREATE TABLE IF NOT EXISTS decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    market_slug TEXT NOT NULL,
    condition_id TEXT NOT NULL,
    t_remaining REAL NOT NULL,
    action TEXT NOT NULL,
    side TEXT,
    price REAL,
    size REAL,
    reason TEXT NOT NULL,
    yes_best_ask REAL,
    yes_best_bid REAL,
    no_best_ask REAL,
    no_best_bid REAL,
    spot_mid REAL,
    spot_at_open REAL,
    dry_run INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_decisions_market ON decisions(market_slug);
CREATE INDEX IF NOT EXISTS idx_decisions_ts ON decisions(ts);

CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    market_slug TEXT NOT NULL,
    condition_id TEXT NOT NULL,
    side TEXT NOT NULL,
    price REAL NOT NULL,
    size REAL NOT NULL,
    fill_price REAL,
    fill_size REAL,
    fee_paid REAL,
    order_id TEXT,
    status TEXT NOT NULL,
    error TEXT,
    dry_run INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_orders_market ON orders(market_slug);

CREATE TABLE IF NOT EXISTS outcomes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    market_slug TEXT NOT NULL UNIQUE,
    condition_id TEXT NOT NULL,
    resolved_winner TEXT,
    resolved_ts REAL,
    spot_at_open REAL,
    spot_at_close REAL
);

CREATE TABLE IF NOT EXISTS market_opens (
    market_slug TEXT PRIMARY KEY,
    spot_at_open REAL NOT NULL,
    recorded_ts REAL NOT NULL
);

-- Per-tick snapshots of the late window for trajectory analysis. Independent
-- of decisions — we record even when SKIP fires.
CREATE TABLE IF NOT EXISTS book_ticks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    market_slug TEXT NOT NULL,
    t_remaining REAL NOT NULL,
    yes_best_ask REAL,
    yes_best_bid REAL,
    no_best_ask REAL,
    no_best_bid REAL,
    yes_buyable_at_cap REAL,
    no_buyable_at_cap REAL,
    spot_mid REAL,
    spot_at_open REAL
);
CREATE INDEX IF NOT EXISTS idx_ticks_market_ts ON book_ticks(market_slug, ts);
"""


@contextmanager
def connect(db_path: Path):
    conn = sqlite3.connect(db_path)
    try:
        conn.row_factory = sqlite3.Row
        conn.executescript(SCHEMA)
        yield conn
        conn.commit()
    finally:
        conn.close()


def record_decision(
    db_path: Path, *, market, decision, books: dict, spot_mid: Optional[float],
    spot_at_open: Optional[float], dry_run: bool,
) -> None:
    yes_book = books.get("yes")
    no_book = books.get("no")
    with connect(db_path) as c:
        c.execute(
            "INSERT INTO decisions (ts, market_slug, condition_id, t_remaining, action, "
            "side, price, size, reason, yes_best_ask, yes_best_bid, no_best_ask, "
            "no_best_bid, spot_mid, spot_at_open, dry_run) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                time.time(), market.slug, market.condition_id,
                market.t_remaining(), decision.action.value,
                decision.side.value if decision.side else None,
                decision.price, decision.size, decision.reason,
                yes_book.best_ask.price if yes_book and yes_book.best_ask else None,
                yes_book.best_bid.price if yes_book and yes_book.best_bid else None,
                no_book.best_ask.price if no_book and no_book.best_ask else None,
                no_book.best_bid.price if no_book and no_book.best_bid else None,
                spot_mid, spot_at_open, 1 if dry_run else 0,
            ),
        )


def record_market_open(db_path: Path, *, market, spot_at_open: float) -> None:
    with connect(db_path) as c:
        c.execute(
            "INSERT OR IGNORE INTO market_opens (market_slug, spot_at_open, recorded_ts) "
            "VALUES (?,?,?)",
            (market.slug, spot_at_open, time.time()),
        )


def get_market_open(db_path: Path, market_slug: str) -> Optional[float]:
    with connect(db_path) as c:
        row = c.execute(
            "SELECT spot_at_open FROM market_opens WHERE market_slug = ?",
            (market_slug,),
        ).fetchone()
        return row["spot_at_open"] if row else None


def record_book_tick(
    db_path: Path, *, market, yes_book, no_book, max_entry_price: float,
    spot_mid: Optional[float], spot_at_open: Optional[float],
) -> None:
    yes_best_ask = yes_book.best_ask.price if yes_book and yes_book.best_ask else None
    yes_best_bid = yes_book.best_bid.price if yes_book and yes_book.best_bid else None
    no_best_ask = no_book.best_ask.price if no_book and no_book.best_ask else None
    no_best_bid = no_book.best_bid.price if no_book and no_book.best_bid else None
    yes_buyable = yes_book.buyable_at(max_entry_price) if yes_book else None
    no_buyable = no_book.buyable_at(max_entry_price) if no_book else None
    with connect(db_path) as c:
        c.execute(
            "INSERT INTO book_ticks (ts, market_slug, t_remaining, yes_best_ask, "
            "yes_best_bid, no_best_ask, no_best_bid, yes_buyable_at_cap, "
            "no_buyable_at_cap, spot_mid, spot_at_open) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                time.time(), market.slug, market.t_remaining(),
                yes_best_ask, yes_best_bid, no_best_ask, no_best_bid,
                yes_buyable, no_buyable, spot_mid, spot_at_open,
            ),
        )
