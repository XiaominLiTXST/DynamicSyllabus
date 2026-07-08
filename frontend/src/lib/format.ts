// Parse an ISO date (YYYY-MM-DD) as a *local* date to avoid timezone off-by-one.
export function parseISO(iso: string): Date {
  const [y, m, d] = iso.split('-').map(Number)
  return new Date(y, m - 1, d)
}

export function fmtDate(iso: string): string {
  return parseISO(iso).toLocaleDateString(undefined, {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
  })
}

export function fmtDateTime(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })
}

// ISO date of the Monday that starts the week containing `iso`.
export function weekStart(iso: string): string {
  const d = parseISO(iso)
  const offset = (d.getDay() + 6) % 7 // Mon=0 ... Sun=6
  d.setDate(d.getDate() - offset)
  return d.toISOString().slice(0, 10)
}

export function todayISO(): string {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(
    d.getDate(),
  ).padStart(2, '0')}`
}

// Group meetings (or any dated items) into weeks, preserving order.
export function groupByWeek<T extends { date: string }>(items: T[]): [string, T[]][] {
  const map = new Map<string, T[]>()
  for (const it of items) {
    const k = weekStart(it.date)
    if (!map.has(k)) map.set(k, [])
    map.get(k)!.push(it)
  }
  return [...map.entries()].sort((a, b) => a[0].localeCompare(b[0]))
}
