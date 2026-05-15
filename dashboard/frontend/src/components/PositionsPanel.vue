<script setup>
import { useCountdown } from '../composables/useCountdown.js'
import { stamp, dur, price } from '../composables/useFormat.js'

const props = defineProps({ store: Object })
const { remaining } = useCountdown()
</script>

<template>
  <section class="panel">
    <div class="panel-hd">
      <span>Open positions</span>
      <span class="tag">{{ store.positions.length }} unresolved</span>
    </div>
    <div class="panel-bd">
      <div v-if="!store.positions.length" class="empty">Flat — no live positions.</div>
      <table v-else>
        <thead>
          <tr><th>OPENED</th><th>MARKET</th><th>SIDE</th><th class="num">PX</th>
              <th class="num">SZ</th><th class="num">RESOLVES</th><th>MODE</th></tr>
        </thead>
        <tbody>
          <tr v-for="p in store.positions" :key="p.market_slug + p.ts">
            <td class="dim">{{ stamp(p.ts) }}</td>
            <td class="cyan">{{ p.market_slug }}</td>
            <td :class="p.side === 'UP' ? 'up b' : 'down b'">{{ p.side }}</td>
            <td class="num">{{ price(p.price) }}</td>
            <td class="num">{{ p.size }}</td>
            <td class="num" :class="remaining(p.end_ts) === 0 ? 'amber' : 'white'">
              {{ p.end_ts ? (remaining(p.end_ts) === 0 ? 'SETTLING' : dur(remaining(p.end_ts))) : '—' }}
            </td>
            <td :class="p.dry_run === 0 ? 'down' : 'cyan'">{{ p.dry_run === 0 ? 'LIVE' : 'DRY' }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>
