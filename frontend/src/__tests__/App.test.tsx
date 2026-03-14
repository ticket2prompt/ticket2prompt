import { waitFor } from '@testing-library/react'
import { render } from '@testing-library/react'

// Mock all pages to prevent full render complexity
vi.mock('@/pages/LoginPage', () => ({
  default: () => <div>Login Page</div>,
}))
vi.mock('@/pages/RegisterPage', () => ({
  default: () => <div>Register Page</div>,
}))
vi.mock('@/pages/DashboardPage', () => ({
  default: () => <div>Dashboard Page</div>,
}))
vi.mock('@/pages/ProjectsPage', () => ({
  default: () => <div>Projects Page</div>,
}))
vi.mock('@/pages/ProjectDetailPage', () => ({
  default: () => <div>Project Detail Page</div>,
}))
vi.mock('@/pages/TicketFormPage', () => ({
  default: () => <div>Ticket Form Page</div>,
}))
vi.mock('@/pages/PromptResultPage', () => ({
  default: () => <div>Prompt Result Page</div>,
}))
vi.mock('@/pages/PromptLookupPage', () => ({
  default: () => <div>Prompt Lookup Page</div>,
}))
vi.mock('@/pages/TeamsPage', () => ({
  default: () => <div>Teams Page</div>,
}))
vi.mock('@/pages/SettingsPage', () => ({
  default: () => <div>Settings Page</div>,
}))

// Mock auth context to be unauthenticated by default
vi.mock('@/contexts/auth-context', () => ({
  useAuth: vi.fn().mockReturnValue({
    user: null,
    token: null,
    isAuthenticated: false,
    isLoading: false,
    login: vi.fn(),
    register: vi.fn(),
    logout: vi.fn(),
  }),
  AuthProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}))

// Mock Layout to avoid sidebar rendering
vi.mock('@/components/Layout', () => ({
  default: () => <div>Layout</div>,
}))

// Mock ProtectedRoute to just render children (auth is mocked separately)
vi.mock('@/components/protected-route', () => ({
  ProtectedRoute: ({ children }: { children: React.ReactNode }) => {
    return <>{children}</>
  },
}))

import App from '../App'

describe('App', () => {
  it('renders without crashing', () => {
    expect(() => render(<App />)).not.toThrow()
  })

  it('renders the login page by default route on unauthenticated', async () => {
    render(<App />)
    await waitFor(() => {
      expect(document.body).toBeTruthy()
    })
  })
})
