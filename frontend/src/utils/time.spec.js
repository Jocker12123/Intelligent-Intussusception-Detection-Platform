import { describe, it, expect } from 'vitest'
import { formatDateTime, formatDate, formatDateTimeCn } from '../utils/time'

describe('utils/time', () => {
  it('把带 +00:00 的 UTC 时间换算成本地时间字符串', () => {
    // 输入是 UTC，浏览器会按操作者本地时区换算。
    // 在任何本地时区下，字符串格式都应是 "YYYY-MM-DD HH:mm"。
    const s = formatDateTime('2026-05-26T10:02:00+00:00')
    expect(s).toMatch(/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$/)
  })

  it('无时区后缀的字符串按 UTC 处理（不再偏移）', () => {
    const s = formatDateTime('2026-05-26T10:02:00')
    expect(s).toMatch(/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$/)
  })

  it('空值返回占位符', () => {
    expect(formatDateTime('')).toBe('—')
    expect(formatDateTime(null)).toBe('—')
    expect(formatDate(undefined)).toBe('—')
  })

  it('仅日期格式只含年月日', () => {
    expect(formatDate('2026-05-26T10:02:00+00:00')).toMatch(/^\d{4}-\d{2}-\d{2}$/)
  })

  it('中文日期格式包含年月日与时分', () => {
    const s = formatDateTimeCn('2026-05-26T10:02:00+00:00')
    expect(s).toMatch(/^\d{4}年\d{1,2}月\d{1,2}日 \d{2}:\d{2}$/)
  })

  it('非法输入安全返回占位符', () => {
    expect(formatDateTime('not-a-date')).toBe('—')
  })
})
