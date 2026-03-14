import { screen } from '@testing-library/react'
import { render } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import Layout from '../Layout'
import { ThemeProvider } from '../theme-provider'

vi.mock('@/contexts/auth-context', () => ({
  useAuth: vi.fn().mockReturnValue({
    user: { user_id: 'u1', email: 'test@example.com', display_name: 'Test', org_id: 'o1', role: 'member' },
    token: 'token',
    isAuthenticated: true,
    isLoading: false,
    login: vi.fn(),
    register: vi.fn(),
    logout: vi.fn(),
  }),
}))

function renderLayout() {
  return render(
    <ThemeProvider>
      <MemoryRouter initialEntries={['/']}>
        <Routes>
          <Route element={<Layout />}>
            <Route path="/" element={<div>Page Content</div>} />
          </Route>
        </Routes>
      </MemoryRouter>
    </ThemeProvider>
  )
}

describe('Layout', () => {
  it('renders without crashing', () => {
    expect(() => renderLayout()).not.toThrow()
  })

  it('renders the outlet content', () => {
    renderLayout()
    expect(screen.getByText('Page Content')).toBeInTheDocument()
  })

  it('renders the navigation sidebar', () => {
    renderLayout()
    expect(screen.getByText('ticket-to-prompt')).toBeInTheDocument()
  })
})
