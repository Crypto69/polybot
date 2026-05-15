# Strategy Analysis — Is the late-window convergence strategy profitable?

**Short answer: no edge.** At realistic retail execution it is **break-even at
best in the $0.85–$0.90 band and loss-making at $0.90 and above — including the
$0.95 level.** The headline "~89% win rate" is real but *mathematically
insufficient* for the prices being paid. This document consolidates every
finding so far; the underlying detail lives in `PLAN.md`,
`youtube_tutorial_trader.md`, `../YouTube strategy.MD`, and the raw pulls in
`data/`.

> Findings as of 2026-05-14, written up 2026-05-15. Two independent on-chain
> data sets back this: ~4,000 trades from "Bonereaper" (the original trader the
> project was modelled on) and 143 fully-resolved trades from the **AllAboutAI**
> YouTube tutorial bot (the channel this project copies). Both are public
> blockchain data; no personal data of ours is involved.

---

## 1. The strategy in one paragraph

Don't predict Bitcoin. Watch Polymarket's 5-min/15-min BTC up/down markets and,
in the last ~35 seconds, buy the side that is *already effectively decided* for
a little under $1.00, expecting it to resolve to $1.00. Edge, if any, comes from
the order book lagging the now-near-deterministic outcome by 1–3%.

## 2. The fee model (verified on-chain)

Live `feeSchedule` on a real 5-min market: `{rate: 0.07, exponent: 1,
takerOnly: true}`. Verified against 10 of Bonereaper's actual trades:

> **Taker fee = `0.07 × (1 − price)` of notional, for BUYs.**

Fee is highest at *low* prices, lowest at *high* prices — the opposite of some
third-party claims. This is small at our cap (0.35% at $0.95) and is **not** the
main problem. The main problem is the win-rate math below.

## 3. The core math: break-even win rate = entry price

A BUY at price *p* pays `(1 − p)` per share if it wins and loses `p` per share
if it loses. Ignoring fees, **you break even only if your win rate ≥ p.** Add
fees and you need slightly more.

| Entry price | Win rate needed to break even (incl. fee) |
|---|---|
| $0.50 | ~66% |
| $0.80 | ~81% |
| $0.85 | ~85% |
| $0.90 | ~91% |
| **$0.95** | **~95%** |
| $0.99 | ~99% |

So a strategy with a flat ~89% win rate **must lose money** anywhere it pays
more than ~$0.89 per share — no matter how good 89% "sounds".

## 4. Empirical proof — the AllAboutAI tutorial bot (143 resolved trades)

The clearest evidence. Their bot ran 47.7 h, 143 trades, all BTC 5-min, ~89%
win rate — and **lost money: −$14.54 on $659.85 of volume (≈ −2.2% of capital).**

### Per-entry-price-bucket P&L (all 143 trades, resolutions verified per-market)

| Bucket | Trades | Win rate | **Net P&L** |
|---|---|---|---|
| 0.50–0.70 | 5 | 80% | **+$5.19** ← only profitable bucket, tiny sample |
| 0.80–0.85 | 13 | 69% | **−$9.59** ← worst |
| 0.85–0.90 | 39 | 87% | **+$0.21** ← only ~break-even band |
| 0.90–0.93 | 19 | 84% | **−$6.87** |
| 0.93–0.95 | 13 | 92% | **−$0.90** |
| 0.95–0.97 | 14 | 93% | **−$2.34** |
| 0.97–0.99 | 40 | 98% | **−$0.25** |
| **TOTAL** | **143** | **88.8%** | **−$14.54** |

### What this says about the $0.95 level specifically

- At $0.95 you need ~95% to break even. The bot's achieved win rate across the
  0.93–0.97 range was only ~92–93%. **Below break-even → it loses at $0.95.**
- The 0.93–0.95 and 0.95–0.97 buckets are both net negative (−$0.90, −$2.34).
- Our isolated $0.85–$0.95 band (72 of their trades): 87.5% win rate, **gross
  −$7.31, net −$9.67 after fees**. That is *exactly the band our earlier config
  traded in.*

### Correction to an earlier headline

An early summary claimed "the $0.97 + $0.98 trades caused 67% of the loss." The
per-bucket data shows that's **misleading**: the 0.97–0.99 bucket actually
netted only −$0.25 (many small wins nearly offset the one big loss). The real
damage is in **0.80–0.85 (−$9.59) and 0.90–0.93 (−$6.87)** — both *inside* the
band we were trading. The strategy isn't "fine except for a couple of
high-price flukes"; it is structurally negative across most of its range.

## 5. The original trader (Bonereaper) doesn't rescue it

Bonereaper (~4,000 trades) puts 67.6% of dollar volume in at ≥$0.99 with large
conviction sizes — a regime we deliberately can't enter (fees + capital +
latency). His ≤$0.95 trades, the only ones comparable to ours, are tiny
$6.79-median probes — *not* his moneymakers. So we never had his actual edge;
we were running a related strategy hoping the cheaper band carried one. The
AllAboutAI data shows it does not.

## 6. Why ours is likely worse than theirs, not better

| Factor | Tutorial bot | Us |
|---|---|---|
| Latency | varies | public RPC + Python on a laptop — we see the chance later |
| Capital | small | smaller |
| Fees | same model | same model |
| Win rate achievable | ~89%, below break-even for its prices | no reason to expect better |

Slower execution means by the time we act, the price has often already moved —
if anything our realised win rate at a given price is **worse** than theirs.

## 7. Decision taken

1. **Narrow the band to $0.85–$0.90 only** (`max_entry_price = 0.90`,
   `low_price_floor = 0.85`). It's the single ~break-even bucket (+$0.21 over 39
   trades). This is **non-destructive data collection**, not an expected-profit
   setup.
2. **Keep hard kill-switches on**: $10 daily loss cap, 3-consecutive-loss kill,
   1 open position max, $0.50 balance floor. These trip long before the
   statistically-expected slow bleed does real damage.
3. **Treat live running as an experiment** to see whether our actual execution
   differs from the tutorial bot's — not as an income strategy.

## 8. Bottom line

> **The strategy as configured has no demonstrated edge.** ~89% win rate is a
> trap: it is below the break-even win rate for every price we pay above
> ~$0.89. **At $0.95 it loses** (observed ~92–93% vs ~95% required). The only
> non-losing bucket in 143 real trades was $0.85–$0.90, and only barely
> (+$0.21). Expect to lose capital slowly; the value here is the data and the
> learning, with kill-switches capping the downside.

### Sources
- `PLAN.md` — original strategy thesis, fee verification, phased plan.
- `youtube_tutorial_trader.md` — AllAboutAI bot identity + −$14.54 result.
- `../YouTube strategy.MD` — full per-bucket breakdown and the 16 losing trades.
- `data/yt_proxy_trades.json`, `data/yt_summary.json` — raw AllAboutAI pulls.
- `data/trades.json`, `bonereaper_trades_raw.json` — raw Bonereaper pulls.
