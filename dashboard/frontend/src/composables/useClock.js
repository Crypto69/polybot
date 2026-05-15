import { ref, onMounted, onUnmounted } from 'vue'

// Ticking wall clock (UTC) + session uptime. One interval per consumer;
// cheap enough and keeps each component self-contained.
export function useClock() {
  const now = ref(Date.now())
  const startedAt = Date.now()
  let id

  const tick = () => { now.value = Date.now() }

  onMounted(() => { id = setInterval(tick, 1000) })
  onUnmounted(() => clearInterval(id))

  const utc = () => new Date(now.value).toISOString().slice(11, 19)
  const uptime = () => {
    const s = Math.floor((now.value - startedAt) / 1000)
    const h = String(Math.floor(s / 3600)).padStart(2, '0')
    const m = String(Math.floor((s % 3600) / 60)).padStart(2, '0')
    const sec = String(s % 60).padStart(2, '0')
    return `${h}:${m}:${sec}`
  }

  return { now, utc, uptime }
}
