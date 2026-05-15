import { reactive, computed } from 'vue'
import { useWebSocket } from './useWebSocket.js'
import { useTradeAlert } from './useTradeAlert.js'

// Single source of truth for the whole dashboard. Module-level singleton so
// every panel reads the same reactive object and the socket opens exactly once.

const MAX_DECISIONS = 400

const store = reactive({
  config: {},
  stats: {},
  equity: [],
  decisions: [],   // chronological
  orders: [],      // newest first
  positions: [],   // newest first, unresolved BUYs
  markets: [],
  wallet: {},
  latestTick: null,
  serverTs: null,
  dbPath: '',
})

const { trigger: fireAlert } = useTradeAlert()

let started = false
let wsHandle = null

function trimDecisions() {
  if (store.decisions.length > MAX_DECISIONS) {
    store.decisions.splice(0, store.decisions.length - MAX_DECISIONS)
  }
}

function upsertPosition(d) {
  // A fresh live BUY: surface it immediately as an open position.
  if (d.action !== 'BUY') return
  const idx = store.positions.findIndex((p) => p.market_slug === d.market_slug)
  let end_ts = null
  try {
    const p = d.market_slug.split('-')
    end_ts = parseInt(p[3], 10) + parseInt(p[2].replace('m', ''), 10) * 60
  } catch { /* leave null */ }
  const row = {
    ts: d.ts, market_slug: d.market_slug, condition_id: d.condition_id,
    side: d.side, price: d.price, size: d.size, dry_run: d.dry_run, end_ts,
  }
  if (idx >= 0) store.positions.splice(idx, 1)
  store.positions.unshift(row)
}

function handle(msg) {
  const { type, data } = msg
  if (type === 'snapshot') {
    store.config = data.config || {}
    store.stats = data.stats || {}
    store.equity = data.equity || []
    store.decisions = data.decisions || []
    store.orders = data.orders || []
    store.positions = data.positions || []
    store.markets = data.markets || []
    store.wallet = data.wallet || {}
    store.latestTick = data.latest_tick || null
    store.serverTs = data.server_ts
    store.dbPath = data.db_path || ''
    trimDecisions()
  } else if (type === 'decision') {
    store.decisions.push(data)
    trimDecisions()
    if (data.action === 'BUY') {
      upsertPosition(data)
      // A live BUY is a placed trade — fire the terminal blink.
      if (data.dry_run === 0) fireAlert(data)
    }
  } else if (type === 'order') {
    store.orders.unshift(data)
    if (store.orders.length > 50) store.orders.pop()
    fireAlert({ ...data, action: 'ORDER' })
  } else if (type === 'tick') {
    store.latestTick = data
  } else if (type === 'stats') {
    store.stats = data.stats || store.stats
    store.equity = data.equity || store.equity
  } else if (type === 'markets') {
    store.markets = data || []
  } else if (type === 'wallet') {
    store.wallet = data || {}
  }
}

export function useStore() {
  if (!started) {
    started = true
    wsHandle = useWebSocket('/ws', handle)
  }
  const connected = computed(() => wsHandle.status.value === 'open')
  return { store, wsStatus: wsHandle.status, connected }
}
