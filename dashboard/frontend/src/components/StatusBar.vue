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

// Bot liveness: the journal is its heartbeat. Fresh row in the last 12s ⇒ the
// trading loop is running. Goes stale the moment the bot stops.
const lastSeen = computed(() => {
  const tick = props.store.latestTick?.ts || 0
  const ds = props.store.decisions
  const dec = ds.length ? ds[ds.length - 1].ts : 0
  return Math.max(tick, dec)
})
const botLive = computed(() =>
  lastSeen.value > 0 && now.value / 1000 - lastSeen.value < 12)

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
