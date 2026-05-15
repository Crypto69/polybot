<script setup>
import { computed } from 'vue'

const props = defineProps({ store: Object })
const c = computed(() => props.store.config || {})

const f3 = (v) => (v === undefined || v === null ? '—' : Number(v).toFixed(3))
</script>

<template>
  <section class="panel">
    <div class="panel-hd"><span>Strategy</span><span class="tag">late-window</span></div>
    <div class="panel-bd kvlist">
      <div class="kvr">
        <span class="kk">Loser Floor</span>
        <span class="vv white">&gt; {{ f3(c.low_price_floor) }}</span>
      </div>
      <div class="kvr">
        <span class="kk">Max Entry</span>
        <span class="vv white">&le; {{ f3(c.max_entry_price) }}</span>
      </div>
      <div class="kvr">
        <span class="kk">Window</span>
        <span class="vv white">{{ c.min_t_remaining_seconds }}-{{ c.seconds_before_close }}s</span>
      </div>
      <div class="kvr">
        <span class="kk">Size</span>
        <span class="vv white">{{ c.order_size_shares }} sh</span>
      </div>
      <div class="kvr">
        <span class="kk">Spot Conf</span>
        <span class="vv white">{{ c.spot_confidence_bps }} bps</span>
      </div>
      <div class="kvsep" />
      <div class="kvr">
        <span class="kk">Max Open</span>
        <span class="vv white">{{ c.max_open_positions }}</span>
      </div>
      <div class="kvr">
        <span class="kk">Loss Cap / Day</span>
        <span class="vv down">${{ Number(c.daily_loss_cap_usd ?? 0).toFixed(2) }}</span>
      </div>
    </div>
  </section>
</template>
