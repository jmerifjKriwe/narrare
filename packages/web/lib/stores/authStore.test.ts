import { describe, it, expect, vi, beforeEach } from 'vitest'
import { useAuthStore } from './authStore'
import { authApi, setAccessToken, clearAccessToken } from '@/lib/api/client'
import { createUser, createTokenResponse } from '@/mocks/data'

// Mock the API client module
vi.mock('@/lib/api/client', () => ({
  setAccessToken: vi.fn(),
  clearAccessToken: vi.fn(),
  authApi: {
    login: vi.fn(),
    register: vi.fn(),
    me: vi.fn(),
  },
  // Export a no-op axios instance (not used directly in store tests)
  default: {},
}))

// Mock window.location for logout redirect
const mockLocation = { href: '' }
Object.defineProperty(window, 'location', {
  value: mockLocation,
  writable: true,
})

describe('useAuthStore', () => {
  beforeEach(() => {
    // Reset store state before each test
    useAuthStore.setState({
      user: null,
      isLoading: false,
      isAuthenticated: false,
    })
    vi.clearAllMocks()
    mockLocation.href = ''
  })

  describe('initial state', () => {
    it('should start unauthenticated', () => {
      const state = useAuthStore.getState()
      expect(state.isAuthenticated).toBe(false)
    })

    it('should have no user initially', () => {
      const state = useAuthStore.getState()
      expect(state.user).toBeNull()
    })

    it('should not be loading initially', () => {
      const state = useAuthStore.getState()
      expect(state.isLoading).toBe(false)
    })
  })

  describe('login', () => {
    it('should set user and authenticated state on successful login', async () => {
      const tokens = createTokenResponse()
      const user = createUser()

      vi.mocked(authApi.login).mockResolvedValue(tokens)
      vi.mocked(authApi.me).mockResolvedValue(user)

      await useAuthStore.getState().login('test@example.com', 'password123')

      const state = useAuthStore.getState()
      expect(state.isAuthenticated).toBe(true)
      expect(state.user).toEqual(user)
      expect(state.isLoading).toBe(false)
    })

    it('should call setAccessToken with the access token', async () => {
      const tokens = createTokenResponse()
      const user = createUser()

      vi.mocked(authApi.login).mockResolvedValue(tokens)
      vi.mocked(authApi.me).mockResolvedValue(user)

      await useAuthStore.getState().login('test@example.com', 'password123')

      expect(setAccessToken).toHaveBeenCalledWith(tokens.access_token)
    })

    it('should set loading to true during login', async () => {
      let resolveLogin: (value: unknown) => void
      const loginPromise = new Promise((resolve) => {
        resolveLogin = resolve
      })

      vi.mocked(authApi.login).mockReturnValue(loginPromise as never)

      const loginAction = useAuthStore.getState().login('test@example.com', 'password123')

      // Loading should be true while the request is in-flight
      expect(useAuthStore.getState().isLoading).toBe(true)

      resolveLogin!(createTokenResponse())
      vi.mocked(authApi.me).mockResolvedValue(createUser())

      await loginAction
    })

    it('should reset loading and re-throw on login failure', async () => {
      vi.mocked(authApi.login).mockRejectedValue(new Error('Invalid credentials'))

      await expect(
        useAuthStore.getState().login('bad@example.com', 'wrong')
      ).rejects.toThrow('Invalid credentials')

      const state = useAuthStore.getState()
      expect(state.isLoading).toBe(false)
      expect(state.isAuthenticated).toBe(false)
      expect(state.user).toBeNull()
    })
  })

  describe('register', () => {
    it('should set user and authenticated state on successful registration', async () => {
      const tokens = createTokenResponse()
      const user = createUser({ email: 'new@example.com' })

      vi.mocked(authApi.register).mockResolvedValue(tokens)
      vi.mocked(authApi.me).mockResolvedValue(user)

      await useAuthStore.getState().register('new@example.com', 'password123', 'New User')

      const state = useAuthStore.getState()
      expect(state.isAuthenticated).toBe(true)
      expect(state.user).toEqual(user)
      expect(state.isLoading).toBe(false)
    })

    it('should call authApi.register with correct arguments', async () => {
      const tokens = createTokenResponse()
      vi.mocked(authApi.register).mockResolvedValue(tokens)
      vi.mocked(authApi.me).mockResolvedValue(createUser())

      await useAuthStore.getState().register('new@example.com', 'pass', 'Display')

      expect(authApi.register).toHaveBeenCalledWith('new@example.com', 'pass', 'Display')
    })

    it('should reset loading and re-throw on registration failure', async () => {
      vi.mocked(authApi.register).mockRejectedValue(new Error('Email taken'))

      await expect(
        useAuthStore.getState().register('taken@example.com', 'pass')
      ).rejects.toThrow('Email taken')

      const state = useAuthStore.getState()
      expect(state.isLoading).toBe(false)
      expect(state.isAuthenticated).toBe(false)
    })
  })

  describe('logout', () => {
    it('should clear user and authenticated state', () => {
      // Set up authenticated state first
      useAuthStore.setState({
        user: createUser(),
        isAuthenticated: true,
      })

      useAuthStore.getState().logout()

      const state = useAuthStore.getState()
      expect(state.user).toBeNull()
      expect(state.isAuthenticated).toBe(false)
    })

    it('should call clearAccessToken', () => {
      useAuthStore.getState().logout()

      expect(clearAccessToken).toHaveBeenCalled()
    })

    it('should redirect to /login', () => {
      useAuthStore.getState().logout()

      expect(window.location.href).toBe('/login')
    })
  })

  describe('loadUser', () => {
    it('should load user and set authenticated on success', async () => {
      const user = createUser()
      vi.mocked(authApi.me).mockResolvedValue(user)

      await useAuthStore.getState().loadUser()

      const state = useAuthStore.getState()
      expect(state.user).toEqual(user)
      expect(state.isAuthenticated).toBe(true)
      expect(state.isLoading).toBe(false)
    })

    it('should clear user and set unauthenticated on failure', async () => {
      useAuthStore.setState({ user: createUser(), isAuthenticated: true })
      vi.mocked(authApi.me).mockRejectedValue(new Error('Unauthorized'))

      await useAuthStore.getState().loadUser()

      const state = useAuthStore.getState()
      expect(state.user).toBeNull()
      expect(state.isAuthenticated).toBe(false)
      expect(state.isLoading).toBe(false)
    })
  })
})
