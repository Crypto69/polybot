<script setup>
import { computed } from 'vue'
import { clock, price, num } from '../composables/useFormat.js'

const props = defineProps({ store: Object })

const dc = computed(() => props.store.stats?.decision_counts || {})
const tick = computed(() => props.store.latestTick || {})
const cfg = computed(() => props.store.config || {})
</script>

<template>
  <footer class="footer">
    <div class="kv"><span class="k">BUY</span><span class="v amber">{{ dc.BUY || 0 }}</span></div>
    <div class="kv"><span class="k">SKIP</span><span class="v dim">{{ dc.SKIP || 0 }}</span></div>
    <div class="kv"><span class="k">Resolved</span>
      <span class="v">{{ store.stats?.resolved_markets || 0 }}/{{ store.stats?.tracked_markets || 0 }}</span>
    </div>
    <div class="kv"><span class="k">Last tick</span><span class="v cyan">{{ clock(tick.ts) }}</span></div>
    <div class="kv"><span class="k">t_rem</span><span class="v">{{ num(tick.t_remaining, 1) }}s</span></div>
    <div class="kv"><span class="k">Spot</span><span class="v cyan">{{ price(tick.spot_mid) }}</span></div>
    <div class="kv"><span class="k">@open</span><span class="v dim">{{ price(tick.spot_at_open) }}</span></div>
    <span class="spacer" />
    <div class="kv"><span class="k">cap</span><span class="v">{{ cfg.max_entry_price }}</span></div>
    <div class="kv"><span class="k">floor</span><span class="v">{{ cfg.low_price_floor }}</span></div>
    <div class="kv"><span class="k">size</span><span class="v">{{ cfg.order_size_shares }}</span></div>
    <div class="kv"><span class="k">db</span><span class="v dim">{{ store.dbPath.split('/').pop() }}</span></div>
  </footer>
</template>
