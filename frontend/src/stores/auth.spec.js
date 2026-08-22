import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useAuthStore } from './auth'

// mock 掉 api 模块，避免真实网络
vi.mock('../api/auth', () => ({
  login: vi.fn(() => Promise.resolve({ data: { access_token: 'fake-token' } })),
  getCurrentUser: vi.fn(() => Promise.resolve({ data: { id: 1, username: 'doctor', full_name: '张医生', role: 'doctor' } })),
}))

describe('stores/auth', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
  })

  it('登录后保存 token 并加载用户信息', async () => {
    const store = useAuthStore()
    await store.login('doctor', 'doctor123')
    expect(store.token).toBe('fake-token')
    expect(localStorage.getItem('access_token')).toBe('fake-token')
    expect(store.user.full_name).toBe('张医生')
  })

  it('退出登录会清除 token 和用户', () => {
    localStorage.setItem('access_token', 'x')
    const store = useAuthStore()
    store.user = { id: 1, role: 'doctor' }
    store.logout()
    expect(store.token).toBe('')
    expect(store.user).toBeNull()
    expect(localStorage.getItem('access_token')).toBeNull()
  })

  it('无 token 时 fetchUser 直接返回', async () => {
    const store = useAuthStore()
    await store.fetchUser()
    expect(store.user).toBeNull()
  })
})
