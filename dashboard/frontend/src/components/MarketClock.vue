<script setup>
import { computed } from 'vue'
import { useCountdown } from '../composables/useCountdown.js'
import { dur } from '../composables/useFormat.js'

const props = defineProps({ store: Object })
const { remaining } = useCountdown()

// Soonest-resolving first; flag the window we're inside the action band on.
const rows = computed(() =>
  [...props.store.markets].sort((a, b) => a.end_ts - b.end_ts))

const band = (sec) => {
  const w = props.store.config?.seconds_before_close ?? 35
  if (sec === null) return 'dim'
  if (sec <= w) return 'amber b'
  if (sec <= 90) return 'white'
  return 'dim'
}
</script>

<template>
  <section class="panel">
    <div class="panel-hd">
      <span>Market clock</span>
      <span class="tag">action &lt; {{ store.config?.seconds_before_close ?? '–' }}s</span>
    </div>
    <div class="panel-bd">
      <div v-if="!rows.length" class="empty">No open BTC up/down markets.</div>
      <table v-else>
        <thead><tr><th>MARKET</th><th>WIN</th><th class="num">CLOSES IN</th></tr></thead>
        <tbody>
          <tr v-for="m in rows" :key="m.slug">
            <td class="cyan">{{ m.slug }}</td>
            <td class="dim">{{ m.window_minutes }}m</td>
            <td class="num" :class="band(remaining(m.end_ts))">
              {{ remaining(m.end_ts) === 0 ? 'CLOSED' : dur(remaining(m.end_ts)) }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>
