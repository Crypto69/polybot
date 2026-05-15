import { ref } from 'vue'

// Resilient WebSocket: auto-reconnect with capped exponential backoff,
// reactive connection status, and a heartbeat so a half-open socket is
// detected fast (low-latency requirement — we can't sit on a dead pipe).
export function useWebSocket(path, onMessage) {
  const status = ref('connecting') // connecting | open | closed
  const lastMsgAt = ref(0)

  let ws = null
  let retry = 0
  let hbTimer = null
  let stopped = false

  const url = () => {
    const proto = location.protocol === 'https:' ? 'wss' : 'ws'
    return `${proto}://${location.host}${path}`
  }

  const heartbeat = () => {
    clearInterval(hbTimer)
    hbTimer = setInterval(() => {
      // No traffic for 15s on a poll-driven feed means the pipe is dead.
      if (status.value === 'open' && Date.now() - lastMsgAt.value > 15000) {
        try { ws.close() } catch { /* ignore */ }
      }
    }, 5000)
  }

  const connect = () => {
    if (stopped) return
    status.value = 'connecting'
    ws = new WebSocket(url())

    ws.onopen = () => {
      status.value = 'open'
      retry = 0
      lastMsgAt.value = Date.now()
      heartbeat()
    }
    ws.onmessage = (ev) => {
      lastMsgAt.value = Date.now()
      try { onMessage(JSON.parse(ev.data)) } catch { /* ignore bad frame */ }
    }
    ws.onclose = () => {
      status.value = 'closed'
      clearInterval(hbTimer)
      if (stopped) return
      retry += 1
      const wait = Math.min(1000 * 2 ** retry, 10000) // cap at 10s
      setTimeout(connect, wait)
    }
    ws.onerror = () => { try { ws.close() } catch { /* ignore */ } }
  }

  connect()

  const close = () => {
    stopped = true
    clearInterval(hbTimer)
    try { ws && ws.close() } catch { /* ignore */ }
  }

  return { status, lastMsgAt, close }
}
