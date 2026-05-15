<script setup>
import { computed } from 'vue'
import { money } from '../composables/useFormat.js'

const props = defineProps({ store: Object })

const W = 320
const H = 110
const PAD = 6

const pts = computed(() => props.store.equity || [])

const geom = computed(() => {
  const e = pts.value
  if (e.length < 2) return null
  const ys = e.map((d) => d.cum_net)
  let lo = Math.min(0, ...ys)
  let hi = Math.max(0, ...ys)
  if (hi === lo) { hi += 1; lo -= 1 }
  const sx = (i) => PAD + (i / (e.length - 1)) * (W - 2 * PAD)
  const sy = (v) => PAD + (1 - (v - lo) / (hi - lo)) * (H - 2 * PAD)
  const path = e.map((d, i) => `${i ? 'L' : 'M'}${sx(i).toFixed(1)},${sy(d.cum_net).toFixed(1)}`).join(' ')
  return { path, zeroY: sy(0).toFixed(1), last: ys[ys.length - 1] }
})

const stroke = computed(() =>
  geom.value && geom.value.last >= 0 ? 'var(--green)' : 'var(--red)')
</script>

<template>
  <section class="panel">
    <div class="panel-hd">
      <span>Equity · cumulative net</span>
      <span class="tag" :class="geom && geom.last >= 0 ? 'up' : 'down'">
        {{ geom ? money(geom.last, 4) : '—' }}
      </span>
    </div>
    <div class="panel-bd" style="overflow:hidden">
      <svg v-if="geom" class="spark" :viewBox="`0 0 ${W} ${H}`" preserveAspectRatio="none">
        <line class="zero" :x1="0" :x2="W" :y1="geom.zeroY" :y2="geom.zeroY" />
        <path class="pl" :d="geom.path" :style="{ stroke }" />
      </svg>
      <div v-else class="empty">No resolved trades yet — curve builds as markets settle.</div>
    </div>
  </section>
</template>
