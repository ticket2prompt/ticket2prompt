import { screen, waitFor, fireEvent } from '@testing-library/react'
import { render, createMockAuthState } from '../../test/test-utils'
import RegisterPage from '../RegisterPage'

vi.mock('@/contexts/auth-context', () => ({
  useAuth: vi.fn(),
}))

import { useAuth } from '@/contexts/auth-context'

const mockUseAuth = useAuth as ReturnType<typeof vi.fn>

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

function setupMockAuth(registerImpl?: () => Promise<void>) {
  const registerFn = vi.fn().mockImplementation(registerImpl ?? (() => Promise.resolve()))
  mockUseAuth.mockReturnValue({
    user: null,
    token: null,
    isAuthenticated: false,
    isLoading: false,
    login: vi.fn(),
    register: registerFn,
    logout: vi.fn(),
  })
  return registerFn
}

function fillForm(overrides: Partial<{
  display_name: string
  email: string
  password: string
  org_name: string
  org_slug: string
}> = {}) {
  const values = {
    display_name: 'Jane Smith',
    email: 'jane@example.com',
    password: 'password123',
    org_name: 'Acme Inc',
    org_slug: 'acme-inc',
    ...overrides,
  }
  fireEvent.change(screen.getByLabelText('Name'), { target: { value: values.display_name } })
  fireEvent.change(screen.getByLabelText('Email'), { target: { value: values.email } })
  fireEvent.change(screen.getByLabelText('Password'), { target: { value: values.password } })
  fireEvent.change(screen.getByLabelText('Organization name'), { target: { value: values.org_name } })
  // Only set org_slug if not relying on auto-generation
  if (overrides.org_slug !== undefined) {
    fireEvent.change(screen.getByLabelText('Organization slug'), { target: { value: values.org_slug } })
  }
}

describe('RegisterPage', () => {
  it('renders all form fields', () => {
    setupMockAuth()
    render(<RegisterPage />, { authState: createMockAuthState('unauthenticated') })
    expect(screen.getByLabelText('Name')).toBeInTheDocument()
    expect(screen.getByLabelText('Email')).toBeInTheDocument()
    expect(screen.getByLabelText('Password')).toBeInTheDocument()
    expect(screen.getByLabelText('Organization name')).toBeInTheDocument()
    expect(screen.getByLabelText('Organization slug')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Create account' })).toBeInTheDocument()
  })

  it('calls register with all form data on submit', async () => {
    const registerFn = setupMockAuth()
    render(<RegisterPage />, { authState: createMockAuthState('unauthenticated') })

    fillForm({ org_slug: 'acme-inc' })
    fireEvent.click(screen.getByRole('button', { name: 'Create account' }))

    await waitFor(() => {
      expect(registerFn).toHaveBeenCalledWith({
        display_name: 'Jane Smith',
        email: 'jane@example.com',
        password: 'password123',
        org_name: 'Acme Inc',
        org_slug: 'acme-inc',
      })
    })
  })

  it('auto-generates org_slug from org_name', async () => {
    setupMockAuth()
    render(<RegisterPage />, { authState: createMockAuthState('unauthenticated') })

    fireEvent.change(screen.getByLabelText('Organization name'), { target: { value: 'My Cool Company' } })

    const slugInput = screen.getByLabelText('Organization slug') as HTMLInputElement
    expect(slugInput.value).toBe('my-cool-company')
  })

  it('shows error message on failed registration', async () => {
    setupMockAuth(() => Promise.reject(new Error('Email already in use')))
    render(<RegisterPage />, { authState: createMockAuthState('unauthenticated') })

    fillForm({ org_slug: 'acme-inc' })
    fireEvent.click(screen.getByRole('button', { name: 'Create account' }))

    await waitFor(() => {
      expect(screen.getByText('Email already in use')).toBeInTheDocument()
    })
    expect(mockNavigate).not.toHaveBeenCalled()
  })

  it('navigates to / on successful registration', async () => {
    setupMockAuth(() => Promise.resolve())
    render(<RegisterPage />, { authState: createMockAuthState('unauthenticated') })

    fillForm({ org_slug: 'acme-inc' })
    fireEvent.click(screen.getByRole('button', { name: 'Create account' }))

    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith('/')
    })
  })

  it('has a link to the login page', () => {
    setupMockAuth()
    render(<RegisterPage />, { authState: createMockAuthState('unauthenticated') })
    const loginLink = screen.getByRole('link', { name: 'Sign in' })
    expect(loginLink).toBeInTheDocument()
    expect(loginLink).toHaveAttribute('href', '/login')
  })

  it('org_slug field onChange updates form', () => {
    setupMockAuth()
    render(<RegisterPage />, { authState: createMockAuthState('unauthenticated') })

    const orgSlugInput = screen.getByPlaceholderText('acme-inc')
    fireEvent.change(orgSlugInput, { target: { value: 'my-org' } })

    expect((orgSlugInput as HTMLInputElement).value).toBe('my-org')
  })

  it('shows fallback error when non-Error thrown during registration', async () => {
    setupMockAuth(() => Promise.reject('string error'))
    render(<RegisterPage />, { authState: createMockAuthState('unauthenticated') })

    fillForm({ org_slug: 'test-org' })
    fireEvent.click(screen.getByRole('button', { name: 'Create account' }))

    await waitFor(() => {
      expect(screen.getByText('Registration failed')).toBeInTheDocument()
    })
  })
})
