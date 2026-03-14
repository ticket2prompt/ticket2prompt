import axios from 'axios'
import { api, setAuthToken, clearAuthToken } from '../client'

const TOKEN_KEY = 'ttp-token'

beforeEach(() => {
  localStorage.clear()
  // Reset location
  Object.defineProperty(window, 'location', {
    value: { href: 'http://localhost/' },
    writable: true,
    configurable: true,
  })
})

afterEach(() => {
  localStorage.clear()
})

describe('API Client - request interceptor', () => {
  it('attaches Bearer token from localStorage when present', async () => {
    localStorage.setItem(TOKEN_KEY, 'test-bearer-token')

    let capturedHeaders: Record<string, string> = {}

    // Override adapter to capture the request config
    const originalAdapter = api.defaults.adapter
    api.defaults.adapter = async (config) => {
      capturedHeaders = config.headers as Record<string, string>
      return {
        data: {},
        status: 200,
        statusText: 'OK',
        headers: {},
        config,
        request: {},
      }
    }

    await api.get('/api/test')

    api.defaults.adapter = originalAdapter

    expect(capturedHeaders['Authorization']).toBe('Bearer test-bearer-token')
  })

  it('does not attach Authorization header when no token', async () => {
    let capturedHeaders: Record<string, string> = {}

    const originalAdapter = api.defaults.adapter
    api.defaults.adapter = async (config) => {
      capturedHeaders = config.headers as Record<string, string>
      return {
        data: {},
        status: 200,
        statusText: 'OK',
        headers: {},
        config,
        request: {},
      }
    }

    await api.get('/api/test')

    api.defaults.adapter = originalAdapter

    expect(capturedHeaders['Authorization']).toBeUndefined()
  })
})

describe('API Client - response interceptor', () => {
  it('clears token and redirects to /login on 401 response', async () => {
    localStorage.setItem(TOKEN_KEY, 'expired-token')

    const originalAdapter = api.defaults.adapter
    api.defaults.adapter = async (config) => {
      // Simulate a 401 response by throwing an AxiosError
      const error = new axios.AxiosError(
        'Unauthorized',
        '401',
        config,
        {},
        {
          data: { detail: 'Unauthorized' },
          status: 401,
          statusText: 'Unauthorized',
          headers: {},
          config,
          request: {},
        },
      )
      return Promise.reject(error)
    }

    await expect(api.get('/api/protected')).rejects.toThrow()

    api.defaults.adapter = originalAdapter

    expect(localStorage.getItem(TOKEN_KEY)).toBeNull()
    expect(window.location.href).toBe('/login')
  })

  it('does not clear token on non-401 errors', async () => {
    localStorage.setItem(TOKEN_KEY, 'valid-token')

    const originalAdapter = api.defaults.adapter
    api.defaults.adapter = async (config) => {
      const error = new axios.AxiosError(
        'Internal Server Error',
        '500',
        config,
        {},
        {
          data: { detail: 'Server error' },
          status: 500,
          statusText: 'Internal Server Error',
          headers: {},
          config,
          request: {},
        },
      )
      return Promise.reject(error)
    }

    await expect(api.get('/api/something')).rejects.toThrow()

    api.defaults.adapter = originalAdapter

    expect(localStorage.getItem(TOKEN_KEY)).toBe('valid-token')
    expect(window.location.href).toBe('http://localhost/')
  })
})

describe('setAuthToken / clearAuthToken', () => {
  it('setAuthToken persists token to localStorage', () => {
    setAuthToken('my-new-token')
    expect(localStorage.getItem(TOKEN_KEY)).toBe('my-new-token')
  })

  it('clearAuthToken removes token from localStorage', () => {
    localStorage.setItem(TOKEN_KEY, 'to-be-cleared')
    clearAuthToken()
    expect(localStorage.getItem(TOKEN_KEY)).toBeNull()
  })
})
