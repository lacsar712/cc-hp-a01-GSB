export async function api(path, options = {}) {
  const token = localStorage.getItem('herb_token') || ''
  const res = await fetch(path, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(data.detail || '请求失败')
  return data
}

const pad = (n) => String(n).padStart(2, '0')

export function dateStr(d) {
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

export function todayStr() {
  return dateStr(new Date())
}

export function offsetDateStr(days) {
  const d = new Date()
  d.setDate(d.getDate() + days)
  return dateStr(d)
}

// 失效日早于今天算已失效，到期当日仍可用；3 天内到期算临近
export function auxStatus(row) {
  const today = todayStr()
  if (row.expires_on < today) return 'expired'
  if (row.expires_on <= offsetDateStr(3)) return 'soon'
  return 'ok'
}
