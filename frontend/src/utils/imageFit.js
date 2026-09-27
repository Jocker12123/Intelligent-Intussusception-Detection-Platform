/**
 * 病灶框 → 叠加层样式
 * =====================
 *
 * 算法（检测模块 A）返回的病灶框 `roi_box = [x1, y1, x2, y2]` 是**原图像素坐标**，
 * 与浏览器里显示的尺寸无关。这里把它换算成相对于图片元素的百分比，
 * 从而不依赖任何尺寸测量，缩放到任意大小都对齐。
 *
 * 前提：被叠加的 <img> 元素必须"尺寸 = 渲染出来的图片尺寸"
 * （即 max-width/max-height + width:auto/height:auto，不要用 object-fit: contain 拉伸元素盒），
 * 否则百分比会对不上。
 */

/** 校验病灶框是否是 4 个可用数字。 */
export function isValidBox(box) {
  if (!Array.isArray(box) || box.length !== 4) return false
  return box.every((v) => Number.isFinite(Number(v)))
}

function clampPercent(value) {
  if (value < 0) return 0
  if (value > 100) return 100
  return value
}

/**
 * 把病灶框换算成绝对定位样式（left/top/width/height 百分比）。
 *
 * @param {number[]} box           [x1, y1, x2, y2] 原图像素坐标
 * @param {number} naturalWidth    原图实际宽度（img.naturalWidth）
 * @param {number} naturalHeight   原图实际高度（img.naturalHeight）
 * @returns {object|null} 可直接绑定到 :style 的对象；参数不可用时返回 null
 */
export function boxToPercentStyle(box, naturalWidth, naturalHeight) {
  if (!isValidBox(box)) return null
  const w = Number(naturalWidth)
  const h = Number(naturalHeight)
  if (!Number.isFinite(w) || !Number.isFinite(h) || w <= 0 || h <= 0) return null

  const [rawX1, rawY1, rawX2, rawY2] = box.map(Number)
  const left = Math.min(rawX1, rawX2)
  const top = Math.min(rawY1, rawY2)
  const width = Math.abs(rawX2 - rawX1)
  const height = Math.abs(rawY2 - rawY1)
  if (width <= 0 || height <= 0) return null

  return {
    left: `${clampPercent((left / w) * 100)}%`,
    top: `${clampPercent((top / h) * 100)}%`,
    width: `${clampPercent((width / w) * 100)}%`,
    height: `${clampPercent((height / h) * 100)}%`,
  }
}
