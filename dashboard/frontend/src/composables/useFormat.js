// Pure formatting helpers. No reactivity — safe to call from templates.

export function money(v, digits = 2) {
  if (v === null || v === undefined || Number.isNaN(v)) return '—'
  const n = Number(v)
  const sign = n > 0 ? '+' : n < 0 ? '-' : ' '
  return `${sign}$${Math.abs(n).toFixed(digits)}`
}

export function num(v, digits = 2) {
  if (v === null || v === undefined || Number.isNaN(v)) return '—'
  return Number(v).toFixed(digits)
}

export function pct(v, digits = 1) {
  if (v === null || v === undefined || Number.isNaN(v)) return '—'
  return `${(Number(v) * 100).toFixed(digits)}%`
}

export function price(v) {
  if (v === null || v === undefined || Number.isNaN(v)) return '·'
  return Number(v).toFixed(3)
}

// unix seconds -> HH:MM:SS (UTC, terminal style)
export function clock(tsSec) {
  if (!tsSec) return '--:--:--'
  return new Date(tsSec * 1000).toISOString().slice(11, 19)
}

// unix seconds -> MM-DD HH:MM:SS
export function stamp(tsSec) {
  if (!tsSec) return '----------'
  return new Date(tsSec * 1000).toISOString().slice(5, 19).replace('T', ' ')
}

// seconds -> M:SS countdown
export function dur(sec) {
  if (sec === null || sec === undefined || Number.isNaN(sec)) return '--:--'
  const s = Math.max(0, Math.floor(sec))
  const m = Math.floor(s / 60)
  return `${m}:${String(s % 60).padStart(2, '0')}`
}

// 0xca12…EA73 — terminal-style address truncation
export function addr(a) {
  if (!a || a.length < 12) return a || '—'
  return `${a.slice(0, 6)}…${a.slice(-4)}`
}

// sign class for color coding
export function signClass(v) {
  if (v === null || v === undefined || Number.isNaN(v)) return 'flat'
  return Number(v) > 0 ? 'up' : Number(v) < 0 ? 'down' : 'flat'
}
