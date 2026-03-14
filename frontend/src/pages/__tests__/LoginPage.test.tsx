import { screen, waitFor, fireEvent } from '@testing-library/react'
import { render, createMockAuthState } from '../../test/test-utils'
import LoginPage from '../LoginPage'

vi.mock('@/contexts/auth-context', () => ({
  useAuth: vi.fn(),
}))

import { useAuth } from '@/contexts/auth-context'

const mockUseAuth = useAuth as ReturnType<typeof vi.fn>

// Capture the navigate mock so we can inspect calls
const mockNavigate = vi.fn()
vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router-dom')>()
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  }
})

beforeEach(() => {
  vi.clearAllMocks()
})

function setupMockAuth(loginImpl?: () => Promise<void>) {
  const loginFn = vi.fn().mockImplementation(loginImpl ?? (() => Promise.resolve()))
  mockUseAuth.mockReturnValue({
    user: null,
    token: null,
    isAuthenticated: false,
    isLoading: false,
    login: loginFn,
    register: vi.fn(),
    logout: vi.fn(),
  })
  return loginFn
}

describe('LoginPage', () => {
  it('renders email and password form fields', () => {
    setupMockAuth()
    render(<LoginPage />, { authState: createMockAuthState('unauthenticated') })
    expect(screen.getByLabelText('Email')).toBeInTheDocument()
    expect(screen.getByLabelText('Password')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Sign in' })).toBeInTheDocument()
  })

  it('calls login with email and password on submit', async () => {
    const loginFn = setupMockAuth()
    render(<LoginPage />, { authState: createMockAuthState('unauthenticated') })

    fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'user@test.com' } })
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'secret123' } })
    fireEvent.click(screen.getByRole('button', { name: 'Sign in' }))

    await waitFor(() => {
      expect(loginFn).toHaveBeenCalledWith('user@test.com', 'secret123')
    })
  })

  it('navigates to / on successful login', async () => {
    setupMockAuth(() => Promise.resolve())
    render(<LoginPage />, { authState: createMockAuthState('unauthenticated') })

    fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'user@test.com' } })
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'secret123' } })
    fireEvent.click(screen.getByRole('button', { name: 'Sign in' }))

    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith('/')
    })
  })

  it('shows error message on failed login', async () => {
    setupMockAuth(() => Promise.reject(new Error('Invalid credentials')))
    render(<LoginPage />, { authState: createMockAuthState('unauthenticated') })

    fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'user@test.com' } })
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'wrongpass' } })
    fireEvent.click(screen.getByRole('button', { name: 'Sign in' }))

    await waitFor(() => {
      expect(screen.getByText('Invalid credentials')).toBeInTheDocument()
    })
    expect(mockNavigate).not.toHaveBeenCalled()
  })

  it('has a link to the register page', () => {
    setupMockAuth()
    render(<LoginPage />, { authState: createMockAuthState('unauthenticated') })
    const registerLink = screen.getByRole('link', { name: 'Create one' })
    expect(registerLink).toBeInTheDocument()
    expect(registerLink).toHaveAttribute('href', '/register')
  })

  it('shows fallback error message when non-Error thrown', async () => {
    setupMockAuth(() => Promise.reject('string error'))
    render(<LoginPage />, { authState: createMockAuthState('unauthenticated') })

    fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'a@b.com' } })
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'pass' } })
    fireEvent.submit(screen.getByRole('button', { name: /sign in/i }))

    await waitFor(() => {
      expect(screen.getByText('Login failed')).toBeInTheDocument()
    })
  })
})
