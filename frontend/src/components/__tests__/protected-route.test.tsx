import { screen } from '@testing-library/react'
import { render, createMockAuthState } from '../../test/test-utils'
import { ProtectedRoute } from '../protected-route'

vi.mock('@/contexts/auth-context', () => ({
  useAuth: vi.fn(),
}))

import { useAuth } from '@/contexts/auth-context'

const mockUseAuth = useAuth as ReturnType<typeof vi.fn>

beforeEach(() => {
  vi.clearAllMocks()
})

describe('ProtectedRoute', () => {
  it('shows skeleton while loading', () => {
    mockUseAuth.mockReturnValue({
      user: null,
      token: null,
      isAuthenticated: false,
      isLoading: true,
      login: vi.fn(),
      register: vi.fn(),
      logout: vi.fn(),
    })

    render(
      <ProtectedRoute>
        <div>Protected content</div>
      </ProtectedRoute>,
      { authState: createMockAuthState('loading') }
    )

    // Should not show the children while loading
    expect(screen.queryByText('Protected content')).not.toBeInTheDocument()
    // Should show a loading container
    expect(document.querySelector('.flex.h-screen')).toBeInTheDocument()
  })

  it('redirects to /login when not authenticated', () => {
    mockUseAuth.mockReturnValue({
      user: null,
      token: null,
      isAuthenticated: false,
      isLoading: false,
      login: vi.fn(),
      register: vi.fn(),
      logout: vi.fn(),
    })

    render(
      <ProtectedRoute>
        <div>Protected content</div>
      </ProtectedRoute>,
      {
        authState: createMockAuthState('unauthenticated'),
        initialEntries: ['/dashboard'],
      }
    )

    // Children should not be rendered
    expect(screen.queryByText('Protected content')).not.toBeInTheDocument()
  })

  it('renders children when authenticated', () => {
    mockUseAuth.mockReturnValue({
      user: { user_id: 'u1', email: 'test@example.com', display_name: 'Test', org_id: 'o1', role: 'member' },
      token: 'token',
      isAuthenticated: true,
      isLoading: false,
      login: vi.fn(),
      register: vi.fn(),
      logout: vi.fn(),
    })

    render(
      <ProtectedRoute>
        <div>Protected content</div>
      </ProtectedRoute>,
      { authState: createMockAuthState('authenticated') }
    )

    expect(screen.getByText('Protected content')).toBeInTheDocument()
  })
})
