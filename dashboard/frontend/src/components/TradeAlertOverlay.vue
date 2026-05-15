<script setup>
import { computed } from 'vue'
import { useTradeAlert } from '../composables/useTradeAlert.js'
import { price } from '../composables/useFormat.js'

// 5-second terminal blink fired by useStore on a placed live trade.
const { active, lastTrade } = useTradeAlert()

const line = computed(() => {
  const t = lastTrade.value
  if (!t) return ''
  const kind = t.action === 'ORDER' ? 'ORDER' : 'SIGNAL'
  return `${kind} · ${t.side || '?'} @ ${price(t.price)} × ${t.size ?? '?'}`
})
const slug = computed(() => lastTrade.value?.market_slug || '')
</script>

<template>
  <Teleport to="body">
    <div v-if="active" class="alert-overlay" />
    <div v-if="active" class="alert-banner">
      <div class="big">▲ TRADE PLACED ▲</div>
      <div class="sub">{{ line }}</div>
      <div class="sub dim">{{ slug }}</div>
    </div>
  </Teleport>
</template>
