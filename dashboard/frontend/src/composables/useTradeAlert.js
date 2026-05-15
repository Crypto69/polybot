import { ref } from 'vue'

// Drives the 5-second terminal blink fired when a real trade is placed.
// Module-level singleton so any source (new BUY decision or order) can
// trigger the same overlay, and any component can observe it.
const ALERT_MS = 5000

const active = ref(false)
const lastTrade = ref(null)
let timer = null

function beep() {
  // Short terminal blip. Best-effort — silently no-op if WebAudio is blocked.
  try {
    const Ctx = window.AudioContext || window.webkitAudioContext
    if (!Ctx) return
    const ctx = new Ctx()
    const osc = ctx.createOscillator()
    const gain = ctx.createGain()
    osc.type = 'square'
    osc.frequency.value = 880
    gain.gain.value = 0.04
    osc.connect(gain).connect(ctx.destination)
    osc.start()
    osc.stop(ctx.currentTime + 0.18)
    osc.onended = () => ctx.close()
  } catch { /* ignore */ }
}

export function useTradeAlert() {
  const trigger = (trade) => {
    lastTrade.value = trade || null
    active.value = true
    beep()
    if (timer) clearTimeout(timer)
    timer = setTimeout(() => { active.value = false }, ALERT_MS)
  }
  return { active, lastTrade, trigger }
}
