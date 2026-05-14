# Polybot Plan — Replicate Bonereaper (calibrated for $0.95 cap)

## 1. Verified strategy (from 4,000 of his trades, 2026-05-14)

**What he does:** late-window convergence scaling on Polymarket BTC up/down markets (5-min and 15-min windows). He is **not** predicting direction. He waits until one side is the obvious winner — typically the last 30–90 seconds — and buys it for $0.97–$0.99, expecting the market to resolve to $1.00.

**Hard data:**
- 100% BUY orders → he never exits, just holds to resolution.
- 67.6% of his **dollar volume** goes in at prices ≥ $0.99.
- 74.1% of dollar volume at prices ≥ $0.95.
- Bimodal trade sizing: small (~$14) probes at mid prices, large (~$1,370) conviction trades at $0.99+.
- Splits roughly evenly between 15-min and 5-min BTC up/down markets.
- ~25k trades/day at peak (his throughput, not ours).

**Why it works (hypothesis):** he reads BTC spot from a CEX and trades the lag between the actual outcome already being decided and Polymarket's order book catching up. At the last minute the resolution is essentially deterministic but the book hasn't fully closed, leaving 1–3% of edge. Pay $0.99 → receive $1.00 on the winner, lose $0.99 if you're wrong. He rarely is.

## 1a. Critical calibration: we cap entries at $0.95

Bonereaper's $0.99+ trades aren't viable for us — Polymarket's dynamic taker fees scale with proximity to a 50/50 contract resolving in your favor, and at $0.99 the fee can swallow the entire 1% gross edge. **We cap entries at $0.95.**

Implication: we are **not** copying his trades — we're running a *related* strategy with our own discipline.

| | Bonereaper full | Bonereaper ≤ $0.95 | Us |
|---|---|---|---|
| Trade count | 4000 | 3896 (97.4%) | match |
| $ volume | $194,434 | $50,430 (26%) | proportional |
| Avg trade $ | $48 | $13 | proportional |

His ≤$0.95 trades are tiny probes ($6.79 median). They are **not** his moneymakers. So the bot can't blindly mirror his price-and-time pattern — we need our own independent edge:

> **Decision rule (replacement):** open a BUY at price *p* on side *S* only when (a) *p* ≤ $0.95, (b) we have ≤ 60 seconds to resolution, AND (c) our own BTC spot reading (Binance/Coinbase) implies side *S* will resolve YES with > some threshold confidence (start at 97%, calibrate from shadow data).

This is what the strategy *should* be — the cap forces us to use our own signal rather than ride Bonereaper's wake.

## 2. Why this might (or might not) work for us

| | Bonereaper | Us | Implication |
|---|---|---|---|
| Trades/day | ~25,000 | 100–500 | OK — strategy works at low volume too |
| Latency | sub-second, dedicated infra | public RPC, Python on a laptop | **Risk:** by the time we see the chance, the price has moved |
| Capital | ~$9k working | $25 USDC.e | Sizing must be proportional |
| Fees | dynamic taker fee | same | Fees can be 1–3% on a $0.99 contract; **could eat the entire edge** |
| Per-trade gross edge | ~37 bps | same if executed well | Net edge is what matters |

**Realistic outcome:** at our scale and latency, the most likely result is break-even to small loss, with occasional good days. Treat this as a learning project with a small starting bankroll, not an income strategy.

## 3. Resolved unknowns (verified empirically 2026-05-14)

### Fee model (good news)
Live `feeSchedule` on a current 5-min market: `{exponent: 1, rate: 0.07, takerOnly: true, rebateRate: 0.2}`.

Verified on 10 of Bonereaper's actual on-chain trades — formula matches exactly:

> **Taker fee = `0.07 × (1 - price)` of notional** for BUYs

The fee is highest at LOW prices (cheap punts on big upside) and lowest at HIGH prices, which is the **opposite** of the third-party agent's claim. Concretely:

| Entry price | Fee % notional | Win-rate to break even |
|---|---|---|
| 0.50 | 3.50% | 65.91% |
| 0.70 | 2.10% | 70.65% |
| 0.80 | 1.40% | 80.91% |
| 0.90 | 0.70% | 90.57% |
| **0.95** | **0.35%** | **95.32%** |
| 0.99 | 0.07% | 99.05% |

At our $0.95 cap, fees consume only 0.35% of notional. The strategy is viable iff we can find edges where actual win-rate > implied probability + ~1%.

### Resolution oracle
**Chainlink BTC/USD Data Stream** — `https://data.chain.link/streams/btc-usd`.
Market resolves "Up" if the Chainlink BTC/USD price at the window END timestamp ≥ price at START timestamp. Aggregated price across many CEXes, updated sub-second. Our prediction signal should mirror this feed; for a small test trade, Binance/Coinbase spot is a 99.99%-correlated cheap proxy.

## 4. Phased implementation plan

### Phase 0 — Shadow / paper trader (no risk, ~1 day of build)
**Goal:** Run the full perception+decision loop without sending orders. Log "I would have bought X shares of Y at Z, currently 47s before resolution". Compare logged decisions against actual market resolutions.

Build:
- `polybot/markets.py` — discover open BTC up/down markets via gamma API; cache token IDs, tick size, neg_risk, fee schedule.
- `polybot/orderbook.py` — pull live order book snapshots (and ideally the WSS stream) from `clob.polymarket.com`.
- `polybot/btc_price.py` — async websocket to Binance/Coinbase BTC/USD spot.
- `polybot/strategy.py` — late-window convergence rule:
  - For each open market, every second in the last 120 seconds:
    - Compute "would-resolve-to" side from current BTC vs window-open BTC.
    - If best-ask on that side ≤ entry price cap, log a "would buy at X" event.
- `polybot/shadow.py` — orchestrator. Writes decisions + market resolutions to SQLite.
- Backfill: for the first 24h, also re-pull market resolutions and tag each shadow trade as win/loss.

Exit criterion to advance to Phase 1: shadow win-rate consistent with edge surviving fees (i.e. break-even or better after a realistic fee model).

### Phase 1 — Tiny live trader (~$5/trade, ~$25 daily exposure cap)
Build:
- `polybot/trader.py` — wraps py-clob-client-v2; submits a GTC limit BUY at the strategy's entry price; auto-cancels if not filled within N seconds.
- `polybot/risk.py` — hard caps: max $5 per trade, max 5 concurrent positions, max $25 daily realized loss → kill-switch.
- `polybot/journal.py` — logs every order, fill, resolution, pnl. Same SQLite schema as shadow.

Run for 1–3 days. Compare actual fill rate, average fill price, and PnL to the shadow predictions.

Exit criterion to advance to Phase 2: positive net PnL after fees over a meaningful sample (≥100 fills).

### Phase 2 — Scale & optimize (only if Phase 1 is positive)
- Paid Polygon RPC (Alchemy / QuickNode) for latency.
- Persistent WSS connection to CLOB (instead of HTTP polls).
- Dynamic position sizing: bigger when book spread is wider, smaller when tighter.
- Consider becoming a maker (post limit orders deeper in the book) to capture the maker rebate instead of paying taker fee.
- Push capital up gradually with strict drawdown rules.

## 5. Risk management — non-negotiable

- **Hard daily loss cap** ($5 in Phase 1, scale with bankroll). Bot stops trading on cap hit, requires manual restart.
- **Per-trade size cap.** No single trade > 20% of bankroll.
- **Resolution risk:** every position is binary 0 or 1. We can lose the entire stake on every trade. Size accordingly.
- **Counterparty risk:** Polymarket / pUSD smart contract risk. Don't keep more than you'd be willing to lose in the wallet.
- **Operational risk:** internet drops mid-trade, RPC fails to confirm cancel. The trader code must handle these gracefully.

## 6. What's outside scope (for now)

- Direction prediction (we are explicitly **not** trying to predict BTC).
- 1-minute markets (different liquidity profile, untested in our research).
- Markets other than BTC up/down (ETH, etc. exist; defer until BTC works).
- Maker-side market making (Phase 2 at earliest).

## 7. Immediate next steps (in order)

1. **Wrap $25 USDC.e → pUSD** (script already exists: `scripts/wrap_usdce.py`). On-chain proof this is required: Bonereaper's wallet currently holds 193,665 pUSD and 0 USDC.e; his trades show pUSD (not USDC.e) sent to the CTF Exchange; the py-clob-client-v2 SDK has no auto-wrap helper. The Polymarket UI hides this step by auto-wrapping; we sent funds direct via Phantom so we wrap manually.
2. **Resolve unknowns from §3**: live-fetch one open BTC up/down market, dump its full metadata + fee schedule, and trace one historical resolution to confirm the oracle.
3. **Build Phase 0 shadow trader** with the §1a decision rule (price cap + spot-confirmed direction + late-window timing).
4. **Run shadow for 24h.** Decision-point review before any live capital.
