import { screen, waitFor, fireEvent } from '@testing-library/react'
import { render, createMockAuthState } from '../../test/test-utils'
import SettingsPage from '../SettingsPage'
import { authApi } from '../../api/auth'

vi.mock('../../api/auth', () => ({
  authApi: {
    createApiKey: vi.fn(),
  },
}))

vi.mock('@/contexts/auth-context', () => ({
  useAuth: vi.fn(),
}))

import { useAuth } from '@/contexts/auth-context'

const mockUseAuth = useAuth as ReturnType<typeof vi.fn>
const mockAuthApi = authApi as unknown as { createApiKey: ReturnType<typeof vi.fn> }

const baseUser = {
  user_id: 'test-user-id',
  email: 'test@example.com',
  display_name: 'Test User',
  org_id: 'test-org-id',
  role: 'admin',
}

const mockLogout = vi.fn()

beforeEach(() => {
  vi.clearAllMocks()
  mockUseAuth.mockReturnValue({
    user: baseUser,
    token: 'mock-token',
    isAuthenticated: true,
    isLoading: false,
    login: vi.fn(),
    register: vi.fn(),
    logout: mockLogout,
  })
})

describe('SettingsPage', () => {
  it('displays user email', () => {
    render(<SettingsPage />, { authState: createMockAuthState('authenticated') })
    expect(screen.getByDisplayValue('test@example.com')).toBeInTheDocument()
  })

  it('displays user display name', () => {
    render(<SettingsPage />, { authState: createMockAuthState('authenticated') })
    expect(screen.getByDisplayValue('Test User')).toBeInTheDocument()
  })

  it('displays user role', () => {
    render(<SettingsPage />, { authState: createMockAuthState('authenticated') })
    expect(screen.getByDisplayValue('admin')).toBeInTheDocument()
  })

  it('creates API key and displays it', async () => {
    mockAuthApi.createApiKey.mockResolvedValue({
      key_id: 'key-123',
      name: 'My CI Key',
      prefix: 'sk-abc123fullkey',
      created_at: '2024-01-01T00:00:00Z',
    })

    render(<SettingsPage />, { authState: createMockAuthState('authenticated') })

    const keyInput = screen.getByPlaceholderText('Key name (e.g. CI/CD)')
    fireEvent.change(keyInput, { target: { value: 'My CI Key' } })

    const generateBtn = screen.getByRole('button', { name: /generate/i })
    fireEvent.click(generateBtn)

    await waitFor(() => {
      expect(mockAuthApi.createApiKey).toHaveBeenCalledWith({ name: 'My CI Key' })
    })

    await waitFor(() => {
      expect(screen.getByText('sk-abc123fullkey')).toBeInTheDocument()
    })
  })

  it('shows "shown once" message after key creation', async () => {
    mockAuthApi.createApiKey.mockResolvedValue({
      key_id: 'key-123',
      name: 'Test Key',
      prefix: 'sk-testprefix',
      created_at: '2024-01-01T00:00:00Z',
    })

    render(<SettingsPage />, { authState: createMockAuthState('authenticated') })

    const keyInput = screen.getByPlaceholderText('Key name (e.g. CI/CD)')
    fireEvent.change(keyInput, { target: { value: 'Test Key' } })

    fireEvent.click(screen.getByRole('button', { name: /generate/i }))

    await waitFor(() => {
      expect(screen.getByText(/shown once/i)).toBeInTheDocument()
    })
  })

  it('logout button calls logout function', () => {
    render(<SettingsPage />, { authState: createMockAuthState('authenticated') })

    const logoutBtn = screen.getByRole('button', { name: /log out/i })
    fireEvent.click(logoutBtn)

    expect(mockLogout).toHaveBeenCalled()
  })

  it('shows API Keys section heading', () => {
    render(<SettingsPage />, { authState: createMockAuthState('authenticated') })
    expect(screen.getByText('API Keys')).toBeInTheDocument()
  })

  it('shows Profile section heading', () => {
    render(<SettingsPage />, { authState: createMockAuthState('authenticated') })
    expect(screen.getByText('Profile')).toBeInTheDocument()
  })

  it('renders with null user (shows empty strings in fields)', () => {
    mockUseAuth.mockReturnValue({
      user: null,
      token: null,
      isAuthenticated: false,
      isLoading: false,
      login: vi.fn(),
      register: vi.fn(),
      logout: mockLogout,
    })
    render(<SettingsPage />, { authState: createMockAuthState('unauthenticated') })
    // Fields should render with empty values
    const inputs = document.querySelectorAll('input[disabled]')
    inputs.forEach(input => {
      expect((input as HTMLInputElement).value).toBe('')
    })
  })
})
