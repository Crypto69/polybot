<script setup>
import { computed } from 'vue'
import { useClock } from '../composables/useClock.js'
import { price } from '../composables/useFormat.js'

const props = defineProps({ store: Object, connected: Boolean, wsStatus: String })
const { now, utc, uptime } = useClock()

// Mode is a runtime flag (CLI --live), not in config — infer from the
// freshest decision row the journal has produced.
const mode = computed(() => {
  const d = props.store.decisions
  if (!d.length) return 'unknown'
  return d[d.length - 1].dry_run === 0 ? 'LIVE' : 'DRY'
})

// Bot liveness: the journal is its heartbeat. The live loop's write cadence is
// irregular — it only records book_ticks for markets inside the 300s
// observation window and does heavy blocking I/O per tick (spot, account
// state, books, an 8s positions API). Measured on a healthy live bot: ~18s
// avg gap between journal rows, p95 ~34s, max ~36s, and never >60s. So a tight
// threshold makes the badge flap STOPPED↔LIVE on every normal gap. 90s sits
// ~2.5x above the observed ceiling: no false "stopped" while healthy, still
// detects a truly stopped bot within ~1.5 min.
const BOT_STALE_SEC = 90
const lastSeen = computed(() => {
  const tick = props.store.latestTick?.ts || 0
  const ds = props.store.decisions
  const dec = ds.length ? ds[ds.length - 1].ts : 0
  return Math.max(tick, dec)
})
const botLive = computed(() =>
  lastSeen.value > 0 && now.value / 1000 - lastSeen.value < BOT_STALE_SEC)

// Trading pair / windows currently open.
const pair = computed(() => {
  const mins = [...new Set((props.store.markets || []).map((m) => m.window_minutes))]
    .sort((a, b) => a - b)
  return mins.length ? `BTC ${mins.map((m) => m + 'M').join('·')}` : 'BTC UP/DOWN'
})
const spot = computed(() => props.store.latestTick?.spot_mid ?? null)
</script>

<template>
  <header class="statusbar">
    <span class="brand">POLYBOT<span class="cursor" /></span>
    <span class="badge" :class="mode === 'LIVE' ? 'live' : 'dry'">{{ mode }}</span>
    <span class="pair">{{ pair }}</span>

    <span class="spacer" />

    <span class="stat" :class="botLive ? 'ok' : 'bad'">
      <span class="dot" :class="botLive ? 'on' : 'off'" />
      BOT {{ botLive ? 'LIVE' : 'STOPPED' }}
    </span>
    <span class="stat" :class="connected ? 'ok' : 'bad'">
      <span class="dot" :class="connected ? 'on' : 'off'" />
      API {{ connected ? 'LIVE' : wsStatus.toUpperCase() }}
    </span>

    <span class="sep" />

    <div class="kv"><span class="k">BTC</span><span class="v cyan">{{ price(spot) }}</span></div>
    <div class="kv"><span class="k">UTC</span><span class="v">{{ utc() }}</span></div>
    <div class="kv"><span class="k">SESSION</span><span class="v">{{ uptime() }}</span></div>
  </header>
</template>
