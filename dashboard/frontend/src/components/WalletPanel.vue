<script setup>
import { computed } from 'vue'
import { addr } from '../composables/useFormat.js'

const props = defineProps({ store: Object })
const w = computed(() => props.store.wallet || {})

const usd = (v) => (v === null || v === undefined ? '—' : `$${Number(v).toFixed(2)}`)
</script>

<template>
  <section class="panel">
    <div class="panel-hd">
      <span>Wallet / Equity</span>
      <span class="tag">{{ w.path ? 'PATH ' + w.path : '—' }}</span>
    </div>
    <div class="panel-bd kvlist">
      <div class="kvr">
        <span class="kk">Deposit</span>
        <span class="vv mono" :title="w.deposit">{{ addr(w.deposit) }}</span>
      </div>
      <div class="kvr">
        <span class="kk">EOA</span>
        <span class="vv mono" :title="w.eoa">{{ addr(w.eoa) }}</span>
      </div>
      <div class="kvsep" />
      <div class="kvr">
        <span class="kk">pUSD Cash</span>
        <span class="vv" :class="w.error ? 'down' : 'white'">
          {{ w.error ? 'RPC ERR' : usd(w.pusd_cash) }}
        </span>
      </div>
      <div class="kvr">
        <span class="kk">Open Value</span>
        <span class="vv" :class="w.open_value ? 'amber' : 'dim'">{{ usd(w.open_value) }}</span>
      </div>
      <div class="kvsep" />
      <div class="kvr total">
        <span class="kk">Total Equity</span>
        <span class="vv">{{ usd(w.total_equity) }}</span>
      </div>
    </div>
  </section>
</template>
