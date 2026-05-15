# YouTube Tutorial Trader — Findings

Source: research subagent analysis on 2026-05-14, with raw data in `docs/research/data/yt_proxy_trades.json`.

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

- Full trade history: `docs/research/data/yt_proxy_trades.json` (143 rows)
- Positions snapshot: `docs/research/data/yt_proxy_positions.json`
- Summary stats: `docs/research/data/yt_summary.json`
- Pull script: `scripts/research/youtube_trader_pull.py`
- Analysis script: `scripts/research/youtube_trader_analyze.py`
- Full agent report: `research/youtube_tutorial_trader.md`

## Detailed win/loss distribution by entry-price band

Empirical re-analysis of all 143 trades, after fetching every market resolution from the CLOB API (`clob.polymarket.com/markets/<conditionId>`).

### By price bucket

| Bucket | Trades | Wins | Losses | WR | Spend | Payout | **PnL** |
|---|---|---|---|---|---|---|---|
| 0.50–0.70 | 5 | 4 | 1 | 80.0% | $21.05 | $26.24 | **+$5.19** ← only profitable bucket |
| 0.80–0.85 | 13 | 9 | 4 | 69.2% | $57.20 | $47.61 | **−$9.59** ← biggest loser |
| 0.85–0.90 | 39 | 34 | 5 | 87.2% | $170.65 | $170.86 | +$0.21 |
| 0.90–0.93 | 19 | 16 | 3 | 84.2% | $87.20 | $80.33 | **−$6.87** |
| 0.93–0.95 | 13 | 12 | 1 | 92.3% | $60.95 | $60.05 | −$0.90 |
| 0.95–0.97 | 14 | 13 | 1 | 92.9% | $67.55 | $65.21 | −$2.34 |
| 0.97–0.99 | 40 | 39 | 1 | 97.5% | $195.25 | $195.00 | −$0.25 |
| **TOTAL** | **143** | **127** | **16** | **88.8%** | **$659.85** | **$645.31** | **−$14.54** |

### Our band ($0.85 ≤ price ≤ $0.95) in isolation

| Metric | Value |
|---|---|
| Trades | 72 |
| Wins | 63  (87.5%) |
| Losses | 9 |
| Spend | $323.55 |
| Payout | $316.24 |
| Gross PnL | **−$7.31** (−2.26% on capital) |
| Est fees | $2.36 |
| **Net PnL** | **−$9.67** |

### All 16 losing trades, by entry price (descending)

| Entry | Size | Spend | Side bought | Side won |
|---|---|---|---|---|
| 0.98 | 5.000 | $4.90 | Down | Up |
| 0.97 | 5.052 | $4.90 | Up | Down |
| 0.94 | 5.000 | $4.70 | Up | Down |
| 0.92 | 5.000 | $4.60 | Down | Up |
| 0.91 | 5.000 | $4.55 | Up | Down |
| 0.91 | 5.275 | $4.80 | Up | Down |
| 0.89 | 5.000 | $4.45 | Down | Up |
| 0.88 | 5.000 | $4.40 | Down | Up |
| 0.87 | 5.000 | $4.35 | Up | Down |
| 0.86 | 5.058 | $4.35 | Up | Down |
| 0.86 | 5.058 | $4.35 | Up | Down |
| 0.84 | 5.119 | $4.30 | Up | Down |
| 0.84 | 5.119 | $4.30 | Up | Down |
| 0.82 | 5.854 | $4.80 | Down | Up |
| 0.81 | 5.494 | $4.45 | Up | Down |
| 0.67 | 6.418 | $4.30 | Up | Down |

## Critical insight (corrects the earlier headline)

The original subagent summary said "$0.97 + $0.98 trades caused 67 % of the deficit." That's **misleading**. Per-bucket aggregate PnL shows:

- The 0.97–0.99 bucket actually **netted only −$0.25** (39 small wins almost offset the one big loss)
- The **biggest losing buckets are 0.80–0.85 (−$9.59) and 0.90–0.93 (−$6.87)** — both inside our $0.85–$0.95 trading band
- Only the 0.50–0.70 bucket was profitable, and only had 5 trades — too small to draw conclusions

## Why high-WR-but-net-negative is mathematically expected

At entry price *p*, a trade pays out (1 − *p*) per share if it wins and loses *p* per share if it loses. **Break-even win rate = *p*.**

| Entry | Break-even WR | YouTube actual WR (our band) |
|---|---|---|
| $0.85 | 85% | ~87% |
| $0.90 | 90% | ~84% (−$6.87 net) |
| $0.93 | 93% | ~92% (−$0.90 net) |
| $0.95 | 95% | ~93% (combined 0.93–0.95) |

The YouTube trader's actual win rate **doesn't beat the implied probability** in most buckets, even before fees. **Mathematically, this strategy at this trader's execution quality is structurally unprofitable in the $0.85–$0.95 band.**

## Implication for our live run

Our config (floor 0.85, cap 0.95, 4-share size) puts us **exactly in the losing band**. Expected outcome over 72 trades: **−$9.67** (per the YouTube trader's empirical results, scaled). Our risk caps (3-loss kill, $10 daily cap) would trip well before that, but we should expect to lose capital.

## Conclusion

The YouTube tutorial's bot is **a real, live bot** — not a mockup — and is **net negative after 2 days and 143 trades**. The 88.8 % headline win rate masks a structural problem: in our trading band, the achieved win rate sits below the break-even threshold required by the entry price.

**Three viable responses:**
1. **Stop the live bot** and accept the strategy is structurally bad at our latency/execution.
2. **Test a tiny sample** (3–5 trades) to verify whether our local execution differs meaningfully from the YouTube trader's. Capped at ~$11.40 worst case by existing kill switches.
3. **Re-tune for an actual edge**: either move into the 0.50–0.70 band (more variance, but the only positive bucket — sample size of 5 is unconvincing), find a better predictor than naive BTC spot, or switch to maker-side market making to capture rebates instead of paying taker fees.
