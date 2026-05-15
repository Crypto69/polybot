<script setup>
import { ref, watch, nextTick, computed } from 'vue'
import { clock, price } from '../composables/useFormat.js'

const props = defineProps({ store: Object })

const box = ref(null)
const stick = ref(true) // auto-scroll unless the user scrolled up to inspect

const rows = computed(() => props.store.decisions)

const onScroll = () => {
  const el = box.value
  if (!el) return
  stick.value = el.scrollHeight - el.scrollTop - el.clientHeight < 40
}

watch(() => rows.value.length, async () => {
  if (!stick.value) return
  await nextTick()
  if (box.value) box.value.scrollTop = box.value.scrollHeight
})
</script>

<template>
  <section class="panel">
    <div class="panel-hd">
      <span>Decision feed</span>
      <span class="tag">{{ rows.length }} buffered · {{ stick ? 'follow' : 'paused' }}</span>
    </div>
    <div ref="box" class="panel-bd feed" @scroll="onScroll">
      <div v-if="!rows.length" class="empty">Waiting for the bot to emit decisions…</div>
      <div v-for="d in rows" :key="d.id"
           class="ln" :class="d.action === 'BUY' ? 'buy' : 'skip'">
        <span class="t">{{ clock(d.ts) }}</span>
        <span class="act">{{ d.action }}</span>
        <span class="sl">{{ d.market_slug }}</span>
        <span :class="d.side === 'UP' ? 'up' : d.side === 'DOWN' ? 'down' : 'dim'"
              style="flex:0 0 42px">{{ d.side || '·' }}</span>
        <span class="dim" style="flex:0 0 96px">
          y{{ price(d.yes_best_ask) }}/n{{ price(d.no_best_ask) }}
        </span>
        <span class="rs">{{ d.reason }}</span>
      </div>
    </div>
  </section>
</template>
