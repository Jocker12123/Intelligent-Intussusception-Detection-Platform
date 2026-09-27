import { describe, it, expect } from 'vitest'
import { isValidBox, boxToPercentStyle } from '../utils/imageFit'

describe('utils/imageFit', () => {
  it('把原图坐标换算成百分比', () => {
    // 1000x500 的图，框在正中偏左上
    expect(boxToPercentStyle([100, 50, 300, 250], 1000, 500)).toEqual({
      left: '10%',
      top: '10%',
      width: '20%',
      height: '40%',
    })
  })

  it('坐标顺序颠倒也能得到正的宽高', () => {
    expect(boxToPercentStyle([300, 250, 100, 50], 1000, 500)).toEqual({
      left: '10%',
      top: '10%',
      width: '20%',
      height: '40%',
    })
  })

  it('超出原图范围的框会被裁到 0~100%', () => {
    const style = boxToPercentStyle([-100, -50, 1200, 800], 1000, 500)
    expect(style.left).toBe('0%')
    expect(style.top).toBe('0%')
    expect(style.width).toBe('100%')
    expect(style.height).toBe('100%')
  })

  it('参数非法时返回 null（前端不画框）', () => {
    expect(boxToPercentStyle(null, 100, 100)).toBeNull()
    expect(boxToPercentStyle([1, 2, 3], 100, 100)).toBeNull()
    expect(boxToPercentStyle([1, 2, 3, 4], 0, 100)).toBeNull()
    expect(boxToPercentStyle([1, 2, 3, 4], undefined, undefined)).toBeNull()
    expect(boxToPercentStyle([1, 2, 3, 'x'], 100, 100)).toBeNull()
    expect(boxToPercentStyle([5, 5, 5, 5], 100, 100)).toBeNull()   // 宽高为 0
  })

  it('isValidBox 只接受 4 个数字', () => {
    expect(isValidBox([1, 2, 3, 4])).toBe(true)
    expect(isValidBox(['1', '2', '3', '4'])).toBe(true)
    expect(isValidBox([1, 2, 3, 4, 5])).toBe(false)
    expect(isValidBox('1,2,3,4')).toBe(false)
    expect(isValidBox(undefined)).toBe(false)
  })
})
