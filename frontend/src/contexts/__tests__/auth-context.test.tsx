import { renderHook, act, waitFor } from '@testing-library/react'
import { type ReactNode } from 'react'
import { AuthProvider, useAuth } from '../auth-context'

const TOKEN_KEY = 'ttp-token'

function wrapper({ children }: { children: ReactNode }) {
  return <AuthProvider>{children}</AuthProvider>
}

function makeFetchResponse(body: unknown, ok = true, status = 200) {
  return Promise.resolve({
    ok,
    status,
    json: () => Promise.resolve(body),
  } as Response)
}

beforeEach(() => {
  localStorage.clear()
  vi.spyOn(globalThis, 'fetch').mockReset()
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('AuthProvider', () => {
  it('restores token from localStorage on mount and fetches user', async () => {
    localStorage.setItem(TOKEN_KEY, 'stored-token')
    const mockUser = { user_id: 'u1', email: 'a@b.com', display_name: 'Alice', org_id: 'o1', role: 'member' }
    vi.spyOn(globalThis, 'fetch').mockReturnValue(makeFetchResponse(mockUser))

    const { result } = renderHook(() => useAuth(), { wrapper })

    await waitFor(() => expect(result.current.isLoading).toBe(false))
    expect(result.current.token).toBe('stored-token')
    expect(result.current.user).toEqual(mockUser)
    expect(result.current.isAuthenticated).toBe(true)
  })

  it('logs out when stored token is invalid (401)', async () => {
    localStorage.setItem(TOKEN_KEY, 'bad-token')
    vi.spyOn(globalThis, 'fetch').mockReturnValue(makeFetchResponse({ detail: 'Unauthorized' }, false, 401))

    const { result } = renderHook(() => useAuth(), { wrapper })

    await waitFor(() => expect(result.current.isLoading).toBe(false))
    expect(result.current.token).toBeNull()
    expect(result.current.user).toBeNull()
    expect(localStorage.getItem(TOKEN_KEY)).toBeNull()
  })

  it('starts unauthenticated when no token in localStorage', async () => {
    const { result } = renderHook(() => useAuth(), { wrapper })

    await waitFor(() => expect(result.current.isLoading).toBe(false))
    expect(result.current.token).toBeNull()
    expect(result.current.user).toBeNull()
    expect(result.current.isAuthenticated).toBe(false)
  })

  it('successful login saves token and triggers user fetch', async () => {
    const mockUser = { user_id: 'u1', email: 'a@b.com', display_name: 'Alice', org_id: 'o1', role: 'member' }

    vi.spyOn(globalThis, 'fetch')
      // First call: POST /api/auth/login
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ access_token: 'new-token' }),
      } as Response)
      // Second call: GET /api/auth/me (triggered by token state change)
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockUser),
      } as Response)

    const { result } = renderHook(() => useAuth(), { wrapper })
    await waitFor(() => expect(result.current.isLoading).toBe(false))

    await act(async () => {
      await result.current.login('a@b.com', 'password123')
    })

    await waitFor(() => expect(result.current.isLoading).toBe(false))
    expect(localStorage.getItem(TOKEN_KEY)).toBe('new-token')
    expect(result.current.token).toBe('new-token')
  })

  it('failed login throws an error', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: false,
      json: () => Promise.resolve({ detail: 'Invalid credentials' }),
    } as Response)

    const { result } = renderHook(() => useAuth(), { wrapper })
    await waitFor(() => expect(result.current.isLoading).toBe(false))

    await expect(
      act(async () => {
        await result.current.login('a@b.com', 'wrong')
      })
    ).rejects.toThrow('Invalid credentials')
  })

  it('successful register saves token', async () => {
    const mockUser = { user_id: 'u2', email: 'b@c.com', display_name: 'Bob', org_id: 'o2', role: 'admin' }

    vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ access_token: 'reg-token' }),
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockUser),
      } as Response)

    const { result } = renderHook(() => useAuth(), { wrapper })
    await waitFor(() => expect(result.current.isLoading).toBe(false))

    await act(async () => {
      await result.current.register({
        email: 'b@c.com',
        password: 'pass1234',
        display_name: 'Bob',
        org_name: 'Bob Corp',
        org_slug: 'bob-corp',
      })
    })

    expect(localStorage.getItem(TOKEN_KEY)).toBe('reg-token')
    expect(result.current.token).toBe('reg-token')
  })

  it('logout clears token and user', async () => {
    localStorage.setItem(TOKEN_KEY, 'valid-token')
    const mockUser = { user_id: 'u1', email: 'a@b.com', display_name: 'Alice', org_id: 'o1', role: 'member' }
    vi.spyOn(globalThis, 'fetch').mockReturnValue(makeFetchResponse(mockUser))

    const { result } = renderHook(() => useAuth(), { wrapper })
    await waitFor(() => expect(result.current.isLoading).toBe(false))
    expect(result.current.user).toEqual(mockUser)

    act(() => {
      result.current.logout()
    })

    expect(result.current.token).toBeNull()
    expect(result.current.user).toBeNull()
    expect(localStorage.getItem(TOKEN_KEY)).toBeNull()
  })

  it('failed login with no detail falls back to default message', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: false,
      json: () => Promise.resolve({}),
    } as Response)

    const { result } = renderHook(() => useAuth(), { wrapper })
    await waitFor(() => expect(result.current.isLoading).toBe(false))

    await expect(
      act(async () => {
        await result.current.login('a@b.com', 'wrong')
      })
    ).rejects.toThrow('Login failed')
  })

  it('failed register throws an error', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: false,
      json: () => Promise.resolve({ detail: 'Email already exists' }),
    } as Response)

    const { result } = renderHook(() => useAuth(), { wrapper })
    await waitFor(() => expect(result.current.isLoading).toBe(false))

    await expect(
      act(async () => {
        await result.current.register({
          email: 'existing@b.com',
          password: 'pass1234',
          display_name: 'Existing',
          org_name: 'Org',
          org_slug: 'org',
        })
      })
    ).rejects.toThrow('Email already exists')
  })

  it('failed register with json error falls back to default message', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: false,
      json: () => Promise.reject(new Error('Parse error')),
    } as unknown as Response)

    const { result } = renderHook(() => useAuth(), { wrapper })
    await waitFor(() => expect(result.current.isLoading).toBe(false))

    await expect(
      act(async () => {
        await result.current.register({
          email: 'a@b.com',
          password: 'pass1234',
          display_name: 'A',
          org_name: 'Org',
          org_slug: 'org',
        })
      })
    ).rejects.toThrow('Registration failed')
  })
})

describe('useAuth outside provider', () => {
  it('throws when used outside AuthProvider', () => {
    // Suppress the expected React error boundary console output
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
    expect(() => renderHook(() => useAuth())).toThrow('useAuth must be used within an AuthProvider')
    consoleSpy.mockRestore()
  })
})
