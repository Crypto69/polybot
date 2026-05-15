# YouTube Tutorial Trader — Research Report

## Identity

| Field | Value |
|---|---|
| EOA / signer | `0x95C6603e5dCaEaD9Be26549d8ea2bF23B67Ed1B5` |
| Deposit / proxy wallet | `0xca12a788a13a0c46968828a125ccbc09cea2ea73` (full address recovered) |
| Polymarket name | **allaboutai** |
| Polymarket pseudonym | **Glittering-Headrest** |
| Bio | (empty) |

Both addresses link to the same profile per `data-api.polymarket.com`. The proxy is also confirmed via the HTML at `polymarket.com/profile/0x95C6...d1B5`, which renders the deposit-wallet hash and the `allaboutai / Glittering-Headrest` display strings. The EOA itself shows zero trades / zero positions / zero value — all activity occurs through the Polymarket-relay proxy, as expected.

## Trading footprint

Source: `https://data-api.polymarket.com/trades?user=0xca12...ea73` paginated to exhaustion (`docs/research/data/yt_proxy_trades.json`, 143 rows).

| Metric | Value |
|---|---|
| Trades | **143** (all `BUY`; no manual sells) |
| Time range | 2026-05-12 12:29 UTC → 2026-05-14 12:09 UTC (47.7 h) |
| $ volume | **$659.85** |
| Avg trade | $4.61 / 5.10 shares |
| Markets | **143/143 BTC up/down 5-min** (zero 15-min, zero non-BTC) |
| Side bias | Down 76 / Up 67 (≈53 / 47) — essentially flat |

## Realized P&L (resolved trades only)

Win/loss derived from `clob.polymarket.com/markets/<conditionId>` `tokens[].winner` flag. All 143 markets had resolved.

| Metric | Value |
|---|---|
| Wins | **127** |
| Losses | **16** |
| Win rate | **88.8 %** (127 / 143) |
| Cost paid | $659.85 |
| Payout | $645.31 |
| **Realized P&L** | **−$14.54** |

The 16 losses cost **−$72.50** in payouts foregone; the 127 wins generated only +$57.96 net (mean win price 0.913, so ~$0.087 profit per share, $0.44/trade × 127 ≈ $56 of gross edge). Result: **net loser by ~$14.50 over 2 days despite ~89 % hit rate.**

## Entry parameters (theirs vs ours)

| Parameter | Their (observed) | Ours (config) |
|---|---|---|
| Markets | BTC 5-min only | BTC 5-min + 15-min |
| Order size | ~5 shares (139/143 between 5–6, 4 between 6–8) | 4 shares |
| Price floor | 0.567 min, **0.85+ on 87 %** of trades | 0.85 |
| Price cap | **never ≥ 0.99**; 0.98 max; 17 % at ≥ 0.98 | 0.96 |
| t_remaining at fill (median) | **31 s** (range 4–33 s) | 35 s |
| Side | Pure BUY, both sides | Pure BUY, both sides |

Their cap (0.98) is meaningfully higher than ours (0.96) — and the data shows that's where the bleed comes from.

## Patterns worth noting

1. **Pure 5-minute bot.** 100 % of fills are `btc-updown-5m-*` slugs. No 15-min, no other markets. Tighter scope than ours.
2. **Fills cluster at 30 s remaining.** Median 31 s, max 33 s — strongly implies a single hard-coded `t_remaining` near 33 s (their bot likely fires once per slot at that mark). 17 fills came in <15 s left, almost certainly retries.
3. **Cap is too high.** 28 % of entries are ≥ 0.97 and 17 % are ≥ 0.98. At 0.98 a single loss costs 49× a win's profit, so even ~89 % accuracy can't break even. Median *win* price is 0.93; median *loss* price is 0.875 — they actually lose **more often at "safe" prices** than at extreme prices, because high-price markets really are predictive.
4. **Down-bias is real but tiny.** 76 Down vs 67 Up over 47 h reflects market regime (BTC drifting), not strategy preference.
5. **Worst single losses were at 0.97–0.98** ($4.90 each) — exactly the trades a 0.96 cap would have skipped. Those two trades alone cost $9.70 of the $14.54 deficit. With our 0.96 cap, the bot would have been roughly break-even over the same window.
6. **Order sizing is uniform 5 shares.** No martingale, no Kelly, no scaling. Four-share orders (ours) are even smaller.

## Honest assessment: is this trader profitable?

**No — not over the observed 2-day window.** The bot has placed 143 trades for $660 of volume and is down **−$14.54 (≈ −2.2 % of staked capital)**. The profile picture in the YouTuber's screenshots ($32.32 balance, $30 deposit, +$2.09 early profit) was a snapshot from very early on — the published P&L of "+$2" was real for that moment, but the run since has been net-negative.

That said, this is a tiny sample (47 h, $660 volume) and the loss is small enough that a modest cap reduction (0.98 → 0.95) would plausibly flip the result positive. The strategy isn't broken; it's just under-priced on tail-risk. **Their bot is not the proof of profitability the YouTube video implies — at minimum the creator was cherry-picking the early-profit screenshot.** Our tighter cap (0.96 vs their 0.98) and slightly later entry (35 s vs 31 s) are reasonable defensive choices given this evidence.

---

*Sources: `data-api.polymarket.com/trades` & `/positions` & `/value` (proxy wallet, 143 trades pulled 2026-05-14). Win/loss verified per-market via `clob.polymarket.com/markets/<conditionId>`. Raw data and scripts under `/Volumes/ExternalHD/code/polybot/docs/research/data/yt_proxy_*.json` and `/Volumes/ExternalHD/code/polybot/scripts/research/youtube_trader_{pull,analyze}.py`.*
