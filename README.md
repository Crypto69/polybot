# Polybot — A Beginner's Manual

This is a step-by-step manual for someone who has **never done this before**.
Every step says **what to do**, the **exact command to type**, and **why you're
doing it**. You don't need any other document — everything is explained here.
The full command reference is in [Section 14](#14-how-to-run-everything-command-reference).

Read Section 1 before you spend any money.

---

## 1. Read this first (what you're getting into)

**What the bot does, in one sentence:** it watches Polymarket's short
"will Bitcoin be up or down?" markets and, in the last ~35 seconds, buys the
side that has *already basically won* for a little less than $1.00, hoping to
collect the full $1.00 when the market closes.

**The honest warning:** this is **not** a money-making machine. Our own analysis
of a real trader running this exact strategy showed it roughly *breaks even at
best and loses money in most price ranges* once fees are included. The bot is
set up as a careful **experiment with strict safety limits**, not an investment.
Only use money you are 100% willing to lose. A realistic worst case for the
default settings is losing your whole trading balance.

**Two safety nets are built in and on by default:**
- It stops for the day after losing about $10 total.
- It stops after 3 losing trades in a row.
- It only ever has 1 trade open at a time.

**The golden rule:** the bot starts in **practice mode** ("dry-run") and sends
**no real orders** unless you explicitly add `--live`. Do the practice run
first. Don't skip to live.

---

## 2. Words you'll see (plain-English glossary)

- **Wallet** — an account that holds crypto. It has a public **address**
  (like an account number, safe to share) and a **private key** (like the
  password + signature; whoever has it controls all the money — never share it).
- **Polygon** — the blockchain network Polymarket runs on. Think of it as the
  bank network all this happens on.
- **POL** — the coin that pays the tiny "transaction fee" (called **gas**) every
  time you move money on Polygon. No POL = you can't move anything.
- **USDC.e** — a dollar-pegged coin ($1 = 1 USDC.e). This is the money you'll
  put in from the outside world.
- **pUSD** — Polymarket's *own* internal dollar coin. Bets are settled in pUSD,
  **not** USDC.e. So you have to *convert* (the code calls it "wrap") USDC.e
  into pUSD before the bot can trade.
- **Bridge wallet (EOA)** — a plain wallet you create. Polymarket won't let a
  plain wallet place bets directly, so this one is **only used to receive money
  and pass it along**.
- **Deposit wallet** — a special wallet Polymarket creates for you
  automatically when you sign up with MetaMask. **This is the one that actually
  places bets.** It is controlled (signed) by your MetaMask key.
- **Dry-run / practice mode** — the bot watches real markets and writes down
  what it *would* do, but sends no real orders. Free and safe.
- **Live mode** — the bot sends real orders with real money.

**Why are there two wallets (bridge + deposit)?** Polymarket blocks brand-new
plain wallets from betting ("maker address not allowed"). New accounts must bet
through a Polymarket-created "deposit wallet." But that deposit wallet can't
easily pull money in from the outside, so you use a normal **bridge wallet** to
receive your funds, convert them, and forward them to the deposit wallet. Two
wallets, two jobs.

---

## 3. Get your computer ready

You need **Python 3.11 or newer** and **git** installed. Then:

```bash
git clone https://github.com/Crypto69/polybot.git
cd polybot
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**Why:** `git clone` downloads the bot's code. The `.venv` ("virtual
environment") is a private sandbox so the bot's libraries don't fight with other
Python programs on your machine. `pip install` downloads the libraries the bot
needs (to talk to Polymarket and the blockchain).

---

## 4. Create the bridge wallet

```bash
python scripts/generate_wallet.py
```

**What this does:** creates a brand-new wallet and saves its private key and
address into a hidden settings file called `.env`. That file is locked down
(only you can read it) and is set to **never** be uploaded to GitHub.

**Why:** the bot needs a wallet to receive your money on Polygon. This is the
*bridge* wallet from Section 2 — it just receives and forwards funds; it does
not place bets.

Now open `.env` in a text editor and add one line so the bot knows how to talk
to the Polygon network:

```
POLYGON_RPC_URL=https://polygon-bor-rpc.publicnode.com
```

**Why:** an "RPC URL" is just the internet address the bot uses to read and
write to the Polygon blockchain. The free public one above is fine to start.

> **Secret safety:** the private key in `.env` controls real money. Never paste
> it into a chat, a screenshot, a document, or anywhere online. Anyone who sees
> it can take the funds. The setup deliberately keeps it out of GitHub.

---

## 5. Put money into the bridge wallet

You need to send two things to your bridge wallet's **address** (the
`WALLET_ADDRESS` line in `.env`), on the **Polygon network**:

1. A small amount of **POL** (about 1–2 is plenty) — this pays the gas fees.
2. The **USDC.e** you want to trade with (start tiny, e.g. $5–$10).

You get these from a crypto exchange or another wallet. Make sure you choose the
**Polygon** network and the **USDC.e** token specifically (not regular USDC).

Check it arrived:

```bash
python scripts/check_balance.py
```

**Why:** the bot can't do anything with an empty wallet. POL pays the fees for
the moves in Section 7; USDC.e is the actual trading money. The check command
just shows you the balances so you can confirm before continuing.

---

## 6. Create your Polymarket account and "deposit wallet"

1. Install the **MetaMask** browser extension and create a wallet in it if you
   don't have one.
2. Go to **polymarket.com**, sign up / log in, and connect with **MetaMask**.
   When you do this as a new user, Polymarket **automatically creates a deposit
   wallet for you** behind the scenes. This is the wallet that will place bets.
3. In the Polymarket site, find and click the **"Enable trading"** button (it
   usually appears when you connect the wallet or enable deposits). **Do not
   skip this.**

**Why "Enable trading" matters:** clicking it gives Polymarket's betting
contracts permission to use the pUSD in your deposit wallet. If you skip it, the
bot will look funded but **every order will fail** with a permission error. We
double-check this in Section 9.

Now collect three pieces of information:
- Your **MetaMask private key** — in MetaMask: the three dots → Account details
  → Show private key.
- Your **MetaMask address** — shown at the top of MetaMask.
- Your **deposit wallet address** — shown on Polymarket's deposit screen (it is
  a *different* address from your MetaMask one).

Open `.env` and add these three lines:

```
MM_PRIVATE_KEY=<your MetaMask private key>
MM_WALLET_ADDRESS=<your MetaMask address>
DEPOSIT_WALLET=<your Polymarket deposit wallet address>
```

**Why:** these tell the bot to use the proper Polymarket betting path: your
MetaMask key *signs* the orders, and the deposit wallet *holds the money and
places the bets*. The moment all three of these are present, the bot
automatically switches to this correct path.

> Again: the MetaMask private key is real money control. Keep it only in `.env`,
> never anywhere else.

---

## 7. Move the money so the bot can actually bet with it

Right now your money is USDC.e in the bridge wallet. The bot bets with **pUSD in
the deposit wallet**. Two commands fix that:

```bash
# Step 1: convert USDC.e into pUSD (in the bridge wallet)
python scripts/wrap_usdce.py all

# Step 2: send that pUSD to the Polymarket deposit wallet
python scripts/fund_deposit_wallet.py 5
```

**Why Step 1 ("wrap"):** Polymarket only settles bets in its own pUSD coin, so
your USDC.e has to be converted first. The command handles the conversion for
you (it asks the Polymarket converter contract to swap USDC.e → pUSD).

**Why Step 2 ("fund"):** the conversion happened in the *bridge* wallet, but
betting happens from the *deposit* wallet. This sends the pUSD over. Use the
amount you want available for trading (e.g. `5` for 5 pUSD).

(If a conversion ever looks wrong, `python scripts/verify_onramp.py` just
inspects the contracts and reports — it doesn't move anything.)

---

## 8. Practice run (no real money — do this!)

```bash
python -m bot.main
```

**What happens:** the bot connects to Polymarket, watches real markets, and
writes down every decision it *would* make — but **places no real orders**.
Press `Ctrl-C` to stop it.

**Why:** this proves your setup works and lets you see the bot "think" with zero
risk. Let it run for at least an hour. Everything it sees is saved to a local
file (`trades.db`).

Then look at how it did:

```bash
python scripts/analyze_dry_run.py
```

**Why:** this compares what the bot *would have* bet against how the markets
actually ended, so you get a feel for the strategy before any money is on the
line. There's no separate test suite — this practice loop *is* the test.

---

## 9. Final safety check before going live

```bash
python scripts/prepare_live_b.py
```

**What it checks (and why each matters):**
- Your **deposit wallet has pUSD** — otherwise there's nothing to bet with.
- The **"Enable trading" permission is set** (it shows `MAX_UINT`). If it shows
  `0`, go back to Section 6 step 3 and click "Enable trading" — orders will fail
  without it.
- It creates the **API login keys** the bot needs to place orders and saves
  them into `.env` automatically.

This command is safe to run as many times as you want and **places no orders**.

---

## 10. Go live (real money)

Only after the practice run and the safety check look good:

```bash
python -m bot.main --live
```

**Why the `--live` flag:** it's the deliberate "I really mean it" switch.
Without it the bot is always in safe practice mode. With it, real orders go out.

When it starts you'll see a banner like:

```
[main] dry_run=False  max_entry_price=0.90  seconds_before_close=35
[main] LIVE mode. Trader (signer) address: 0x...
[main] Session start pUSD balance: <your balance>
[main] Daily loss cap: $10.0  min_floor: $0.5  max_open: 1
```

**What to watch:** every 30 seconds it prints a "heartbeat" line showing your
balance change, open orders, and the losing-streak counter. The safety limits
($10 daily loss, 3 losses in a row, 1 open trade) will stop it automatically if
things go badly.

**To stop it at any time:** press `Ctrl-C`.

---

## 11. If something goes wrong (common messages explained)

- **"maker address not allowed"** — you're using the plain bridge wallet to bet.
  Make sure all three `MM_*`/`DEPOSIT_WALLET` lines are in `.env` (Section 6).
- **Orders fail even though you have money** — you skipped "Enable trading."
  Go back to Section 6 step 3. Confirm with `scripts/prepare_live_b.py`
  (the allowance should say `MAX_UINT`, not `0`).
- **"insufficient POL" / can't move funds** — your bridge wallet ran out of gas
  money. Send it a little more POL (Section 5).
- **The bot keeps placing many trades fast** — stop it immediately with
  `Ctrl-C`. This was a real bug we fixed; if you see it on an old copy of the
  code, update to the latest version before continuing.
- **Network errors in the log** — usually temporary; the bot retries on its own.
  If it never recovers, stop it and check your internet / try a different
  `POLYGON_RPC_URL`.

---

## 12. The `.env` cheat sheet

This is the one file holding all your secrets. It should **never** leave your
computer or go into GitHub. Lines you'll have by the end:

| Line | Where it came from | What it's for |
|---|---|---|
| `PRIVATE_KEY` | Section 4 (generated) | Bridge wallet — receives & forwards money |
| `WALLET_ADDRESS` | Section 4 (generated) | Bridge wallet's address |
| `CHAIN_ID` | Section 4 (`137`) | Tells the bot it's on Polygon mainnet |
| `CLOB_HOST`, `GAMMA_HOST` | Section 4 (defaults) | Polymarket's web addresses |
| `POLYGON_RPC_URL` | Section 4 (you added) | How the bot reaches Polygon |
| `MM_PRIVATE_KEY` | Section 6 (from MetaMask) | Signs your bets — **most sensitive** |
| `MM_WALLET_ADDRESS` | Section 6 (from MetaMask) | Your signing address |
| `DEPOSIT_WALLET` | Section 6 (from Polymarket) | The wallet that holds pUSD & bets |
| `MM_CLOB_API_*` | Section 9 (auto-created) | Login keys the bot uses for orders |

If any "private key" or "secret" value ever gets exposed, assume the money is at
risk: move funds out and create a fresh wallet.

---

## 13. The whole thing in one breath

Install Python → clone repo → make virtual env → `generate_wallet.py` → send
POL + USDC.e to the bridge wallet → sign up to Polymarket with MetaMask
(this makes your deposit wallet) → click **Enable trading** → put your MetaMask
+ deposit-wallet details in `.env` → `wrap_usdce.py` → `fund_deposit_wallet.py`
→ practice with `python -m bot.main` → check with `analyze_dry_run.py` and
`prepare_live_b.py` → go live with `python -m bot.main --live`. The built-in
limits cap how much you can lose while you learn.

---

## 14. How to run everything (command reference)

Every command in one place. Always run with the virtual environment active:
`source .venv/bin/activate` (from the repo folder).

### One-time setup

| What | Command | Notes |
|---|---|---|
| Install dependencies | `pip install -r requirements.txt` | After `python -m venv .venv && source .venv/bin/activate` |
| Create the bridge wallet | `python scripts/generate_wallet.py` | Writes `.env` (mode 600). Won't overwrite an existing key |
| Check wallet balances | `python scripts/check_balance.py` | Shows POL / USDC.e / pUSD for the bridge wallet |
| Convert USDC.e → pUSD | `python scripts/wrap_usdce.py all` | Or a number, e.g. `python scripts/wrap_usdce.py 5` |
| Send pUSD to deposit wallet | `python scripts/fund_deposit_wallet.py 5` | Amount in pUSD |
| Inspect the converter (read-only) | `python scripts/verify_onramp.py` | Diagnostic only; moves nothing |
| Final live-readiness check | `python scripts/prepare_live_b.py` | Verifies pUSD + permissions, creates API keys. Places no orders |

### Running the bot

| Mode | Command | Effect |
|---|---|---|
| **Practice (default, safe)** | `python -m bot.main` | Watches real markets, places **no** orders |
| **Live (real money)** | `python -m bot.main --live` | Sends real orders. Safety limits active |
| Override the price cap | `python -m bot.main --live --max-entry-price 0.92` | Highest price per share it will pay |
| Override the timing window | `python -m bot.main --live --seconds-before-close 180` | How many seconds before close it may act |
| Stop the bot | press `Ctrl-C` | Clean shutdown either mode |

### Looking at results

| What | Command |
|---|---|
| Practice/live decisions vs real outcomes | `python scripts/analyze_dry_run.py` |
| Order-book snapshot coverage | `python scripts/analyze_book_ticks.py` |
| Sweep strategy settings against recorded data | `python scripts/backtest.py` |
| Raw recent orders (SQLite) | `sqlite3 trades.db "SELECT * FROM orders ORDER BY ts DESC LIMIT 20;"` |

### Default safety limits (in `bot/config.py`)

These are on automatically in live mode — the bot stops itself when any trips:

- **Daily loss cap:** ~$10 total loss for the session.
- **Losing streak:** 3 losing trades in a row.
- **Max open:** only 1 position at a time.
- **Balance floor:** won't trade if it would drop the balance below ~$0.50.

### Typical first-time order of commands

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python scripts/generate_wallet.py          # then add POLYGON_RPC_URL to .env
# ... send POL + USDC.e to the bridge wallet, sign up on Polymarket, Enable trading,
#     add MM_* / DEPOSIT_WALLET lines to .env ...
python scripts/check_balance.py
python scripts/wrap_usdce.py all
python scripts/fund_deposit_wallet.py 5
python -m bot.main                         # practice for ~1 hour, Ctrl-C
python scripts/analyze_dry_run.py
python scripts/prepare_live_b.py
python -m bot.main --live                  # only when the above looks good
```

> A more technical version of this guide also lives at
> [`docs/SETUP.md`](docs/SETUP.md). Architecture notes are in
> [`CLAUDE.md`](CLAUDE.md); the strategy evidence is in
> [`docs/research/PLAN.md`](docs/research/PLAN.md) and
> [`docs/YouTube strategy.MD`](docs/YouTube%20strategy.MD).
