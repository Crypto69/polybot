import { ref, onMounted, onUnmounted } from 'vue'

// Shared 1s ticker so every countdown in the app stays frame-aligned and
// we never spawn N intervals. Components derive `endTs - nowSec` from it.
const nowSec = ref(Math.floor(Date.now() / 1000))
let refs = 0
let id = null

export function useCountdown() {
  onMounted(() => {
    if (refs++ === 0) {
      id = setInterval(() => { nowSec.value = Math.floor(Date.now() / 1000) }, 1000)
    }
  })
  onUnmounted(() => {
    if (--refs === 0 && id) { clearInterval(id); id = null }
  })

  // seconds remaining until a unix-seconds timestamp (clamped at 0)
  const remaining = (endTs) => {
    if (!endTs) return null
    return Math.max(0, endTs - nowSec.value)
  }

  return { nowSec, remaining }
}
