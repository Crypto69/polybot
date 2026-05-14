# YouTube Tutorial Trader — Findings

Source: research subagent analysis on 2026-05-14, with raw data in `research/data/yt_proxy_trades.json`.

## Identity

| Field | Value |
|---|---|
| EOA / signer | `0x95C6603e5dCaEaD9Be26549d8ea2bF23B67Ed1B5` |
| Deposit wallet (full) | `0xca12a788a13a0c46968828a125ccbc09cea2ea73` |
| Display name | `allaboutai` |
| Pseudonym | `Glittering-Headrest` |
| Profile URL | https://polymarket.com/profile/0x95C6603e5dCaEaD9Be26549d8ea2bF23B67Ed1B5 |
| Linkage verified | HTML scrape of profile renders proxy hash + display name |

## Trading stats (over 47.7 hours, May 12 – May 14 2026)

| Metric | Value |
|---|---|
| Trade count | **143** (all BUY, all `btc-updown-5m`) |
| Markets | 5-minute BTC up/down only — no 15-min |
| Total $ volume | $659.85 |
| Avg trade | $4.61 / 5.10 shares |
| Side bias | 76 Down / 67 Up — essentially flat |
| Median entry timing | 31 s remaining (fires once per market at ~33 s) |
| **Win rate** | **88.8 %** (127 wins / 16 losses, all 143 markets resolved) |
| **Realized P&L** | **−$14.54** (cost $659.85, payout $645.31) — **net negative** |

### Entry price distribution

| Price band | % of trades |
|---|---|
| ≥ 0.99 | 0 % |
| ≥ 0.98 | 17 % |
| ≥ 0.97 | 28 % |
| < 0.97 | 72 % |

## Final config (per YouTube screenshots 230, 231)

```python
seconds_before_close:    35       # only fire in last 35s of window
min_t_remaining_sec:     8.0      # avoid races to resolution
order_size_shares:       5
max_open_positions:      1        # changed from 3 → 1 mid-tutorial
max_daily_loss_usd:      10.0
consecutive_loss_kill:   3
poll_interval_sec:       0.25
```

Strategy refinements selected (per screenshot 228):
- ✅ Raise loser_floor 0.50 → 0.85
- ❌ Raise max_entry_price 0.95 → 0.96 (NOT selected — kept at 0.95)
- ✅ Tighten t_remaining 60s → 35s
- ✅ Add min t_remaining buffer ≥ 8s

## Critical finding

**88.8 % win rate is misleading.** The two single-worst losses (entries at $0.97 and $0.98) cost **$9.70 combined — ~67 % of the total deficit**.

**Why:** at $0.97 entry you risk $0.97 to win $0.03. One loss erases ~32 wins at $0.96.

**Implication:** the strategy as configured is structurally dangerous in the $0.95–$0.99 band. The "+$2.09 profit" snapshot the YouTuber showed early in the tutorial was real but cherry-picked from his first few trades; the actual run has bled.

## Comparison to our config

| | YouTube (allaboutai) | Polybot |
|---|---|---|
| Markets | 5-min only | 5-min + 15-min |
| Floor | 0.85 | 0.85 |
| **Cap** | **~0.98 (effective)** | **0.95** (intentionally tighter) |
| t_remaining | ~31 s | 35 s |
| min_t_remaining | 8 s | 8 s |
| Order size | 5 shares | 4 shares |
| Max open positions | 1 | 1 |
| Daily loss cap | $10 | $10 |
| Consecutive-loss kill | 3 | 3 |
| Poll interval | 0.25 s | 0.25 s |

## What our $0.95 cap would change vs his run

- Would have **excluded** his trades at $0.97 and $0.98 (the source of ~67 % of his loss)
- Estimated his counterfactual P&L with cap 0.96: **≈ −$4.84** (vs actual −$14.54)
- Our cap 0.95 would skip even more high-price trades (the 0.95–0.97 band) — likely better than −$4.84
- Still exposed to potential losses at $0.85–$0.95 band

## Source data

- Full trade history: `research/data/yt_proxy_trades.json` (143 rows)
- Positions snapshot: `research/data/yt_proxy_positions.json`
- Summary stats: `research/data/yt_summary.json`
- Pull script: `scripts/research/youtube_trader_pull.py`
- Analysis script: `scripts/research/youtube_trader_analyze.py`
- Full agent report: `research/youtube_tutorial_trader.md`

## Conclusion

The YouTube tutorial's bot is **a real, live bot** — not a mockup — and is **net negative after 2 days and 143 trades**. The 88.8 % win rate masks a structural problem: rare losses at high prices outweigh frequent wins.

**Our defensive choices (0.95 cap, 4-share size) are well-justified.** Don't blindly mirror — keep our tighter cap. Even with that, we should expect break-even-to-small-negative outcomes from this strategy unless we find an additional edge.
