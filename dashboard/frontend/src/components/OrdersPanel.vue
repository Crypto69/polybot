<script setup>
import { stamp, price } from '../composables/useFormat.js'

const props = defineProps({ store: Object })

const ok = (s) => ['matched', 'live', 'delayed'].includes((s || '').toLowerCase())
</script>

<template>
  <section class="panel">
    <div class="panel-hd">
      <span>Orders · live placements</span>
      <span class="tag">{{ store.orders.length }}</span>
    </div>
    <div class="panel-bd">
      <div v-if="!store.orders.length" class="empty">No orders submitted.</div>
      <table v-else>
        <thead>
          <tr><th>TS</th><th>MARKET</th><th>SIDE</th><th class="num">PX</th>
              <th class="num">SZ</th><th>STATUS</th><th>NOTE</th></tr>
        </thead>
        <tbody>
          <tr v-for="o in store.orders" :key="o.id">
            <td class="dim">{{ stamp(o.ts) }}</td>
            <td class="cyan">{{ o.market_slug }}</td>
            <td :class="o.side === 'UP' ? 'up b' : 'down b'">{{ o.side }}</td>
            <td class="num">{{ price(o.price) }}</td>
            <td class="num">{{ o.size }}</td>
            <td :class="ok(o.status) ? 'up b' : 'down b'">{{ (o.status || '—').toUpperCase() }}</td>
            <td class="dim" :title="o.error || ''">{{ o.error ? o.error.slice(0, 36) : '' }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>
