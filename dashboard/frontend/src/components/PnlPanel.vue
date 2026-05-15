<script setup>
import { ref, computed } from 'vue'
import { money, pct, signClass } from '../composables/useFormat.js'

const props = defineProps({ store: Object })

const views = ['live', 'all', 'dry']
const view = ref('live')

const p = computed(() => props.store.stats?.[view.value] || {})

// Auto-fall back to ALL if there's no live activity yet.
const heroNet = computed(() => p.value.net ?? 0)
</script>

<template>
  <section class="panel">
    <div class="panel-hd">
      <span>P&amp;L · realised</span>
      <span class="tag">
        <a v-for="v in views" :key="v"
           href="#" @click.prevent="view = v"
           :class="view === v ? 'amber b' : 'dim'"
           style="margin-left:10px; text-decoration:none;">{{ v.toUpperCase() }}</a>
      </span>
    </div>

    <div class="pnl-hero">
      <span class="dim" style="font-size:10px; letter-spacing:.14em;">NET (AFTER FEES)</span>
      <span class="big" :class="signClass(heroNet)">{{ money(heroNet, 4) }}</span>
    </div>

    <div class="pnl-grid">
      <div class="pnl-cell">
        <div class="lbl">Gross</div>
        <div class="val" :class="signClass(p.gross)">{{ money(p.gross, 4) }}</div>
      </div>
      <div class="pnl-cell">
        <div class="lbl">Fees</div>
        <div class="val down">-${{ (p.fees ?? 0).toFixed(4) }}</div>
      </div>
      <div class="pnl-cell">
        <div class="lbl">Win rate</div>
        <div class="val" :class="p.win_rate >= 0.5 ? 'up' : 'down'">
          {{ pct(p.win_rate) }}
          <span class="dim" style="font-size:11px">({{ p.wins ?? 0 }}/{{ p.resolved ?? 0 }})</span>
        </div>
      </div>
      <div class="pnl-cell">
        <div class="lbl">Per-trade</div>
        <div class="val" :class="signClass(p.per_trade)">{{ money(p.per_trade, 4) }}</div>
      </div>
      <div class="pnl-cell">
        <div class="lbl">BUY signals</div>
        <div class="val white">{{ p.buys ?? 0 }}</div>
      </div>
      <div class="pnl-cell">
        <div class="lbl">Open / pending</div>
        <div class="val cyan">{{ p.unresolved ?? 0 }}</div>
      </div>
    </div>
  </section>
</template>
