// 统一的日期时间格式化工具。
//
// 后端统一返回带 +00:00 后缀的 UTC ISO 字符串（如 "2026-05-26T10:02:00+00:00"）。
// 这里统一用 new Date(iso) 解析（浏览器会自动换算成用户本地时区）再格式化，
// 避免此前直接拿字符串显示导致 8 小时时区偏移的 bug。
//
// 兼容：若某字段仍是无时区后缀的字符串（旧数据/手工拼接），也按 UTC 处理。

const ISO_RE = /(Z|[+-]\d{2}:?\d{2})$/i

function toDate(iso) {
  if (!iso) return null
  // 无时区标记时按 UTC 补上 "Z"，保证按正确时区解析
  const s = ISO_RE.test(iso) ? iso : `${iso}Z`
  const d = new Date(s)
  return Number.isNaN(d.getTime()) ? null : d
}

const pad = (n) => String(n).padStart(2, '0')

/** 返回 "YYYY-MM-DD HH:mm"（本地时区） */
export function formatDateTime(iso) {
  const d = toDate(iso)
  if (!d) return '—'
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

/** 返回 "YYYY-MM-DD"（本地时区） */
export function formatDate(iso) {
  const d = toDate(iso)
  if (!d) return '—'
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

/** 返回 "YYYY年M月D日 HH:mm"（本地时区），用于展示型场景 */
export function formatDateTimeCn(iso) {
  const d = toDate(iso)
  if (!d) return '—'
  return `${d.getFullYear()}年${d.getMonth() + 1}月${d.getDate()}日 ${pad(d.getHours())}:${pad(d.getMinutes())}`
}
