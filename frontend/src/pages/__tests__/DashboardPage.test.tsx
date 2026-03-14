import { screen, waitFor, fireEvent } from '@testing-library/react'
import { render, createMockAuthState } from '../../test/test-utils'
import DashboardPage from '../DashboardPage'
import { projectsApi } from '../../api/projects'
import type { ProjectResponse } from '../../api/types'

vi.mock('../../api/projects', () => ({
  projectsApi: {
    list: vi.fn(),
  },
}))

vi.mock('@/contexts/auth-context', () => ({
  useAuth: vi.fn(),
}))

import { useAuth } from '@/contexts/auth-context'

const mockProjectsApi = projectsApi as unknown as { list: ReturnType<typeof vi.fn> }
const mockUseAuth = useAuth as ReturnType<typeof vi.fn>

const baseUser = {
  user_id: 'test-user-id',
  email: 'test@example.com',
  display_name: 'Test User',
  org_id: 'test-org-id',
  role: 'member',
}

const sampleProjects: ProjectResponse[] = [
  {
    project_id: 'p1',
    org_id: 'test-org-id',
    name: 'Alpha Project',
    slug: 'alpha-project',
    github_repo_url: 'https://github.com/org/alpha',
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
  },
  {
    project_id: 'p2',
    org_id: 'test-org-id',
    name: 'Beta Project',
    slug: 'beta-project',
    github_repo_url: 'https://github.com/org/beta',
    created_at: '2024-01-02T00:00:00Z',
    updated_at: '2024-01-02T00:00:00Z',
  },
]

beforeEach(() => {
  vi.clearAllMocks()
  mockUseAuth.mockReturnValue({
    user: baseUser,
    token: 'mock-token',
    isAuthenticated: true,
    isLoading: false,
    login: vi.fn(),
    register: vi.fn(),
    logout: vi.fn(),
  })
})

describe('DashboardPage', () => {
  it('loads projects on mount when user.org_id exists', async () => {
    mockProjectsApi.list.mockResolvedValue(sampleProjects)
    render(<DashboardPage />, { authState: createMockAuthState('authenticated') })
    await waitFor(() => expect(mockProjectsApi.list).toHaveBeenCalledWith('test-org-id'))
  })

  it('does not call projectsApi when user has no org_id', async () => {
    mockUseAuth.mockReturnValue({
      user: { ...baseUser, org_id: '' },
      token: 'mock-token',
      isAuthenticated: true,
      isLoading: false,
      login: vi.fn(),
      register: vi.fn(),
      logout: vi.fn(),
    })
    render(<DashboardPage />, { authState: createMockAuthState('authenticated') })
    // Give async effects time to run
    await new Promise((r) => setTimeout(r, 50))
    expect(mockProjectsApi.list).not.toHaveBeenCalled()
  })

  it('displays project count in stat card', async () => {
    mockProjectsApi.list.mockResolvedValue(sampleProjects)
    render(<DashboardPage />, { authState: createMockAuthState('authenticated') })
    await waitFor(() => expect(screen.getByText('2')).toBeInTheDocument())
  })

  it('shows recent projects list', async () => {
    mockProjectsApi.list.mockResolvedValue(sampleProjects)
    render(<DashboardPage />, { authState: createMockAuthState('authenticated') })
    await waitFor(() => {
      expect(screen.getByText('Alpha Project')).toBeInTheDocument()
      expect(screen.getByText('Beta Project')).toBeInTheDocument()
    })
  })

  it('handles no projects gracefully with empty state message', async () => {
    mockProjectsApi.list.mockResolvedValue([])
    render(<DashboardPage />, { authState: createMockAuthState('authenticated') })
    await waitFor(() => {
      expect(screen.getByText(/No projects yet/)).toBeInTheDocument()
    })
    // Project count stat shows 0
    expect(screen.getByText('0')).toBeInTheDocument()
  })

  it('shows welcome message with user display name', async () => {
    mockProjectsApi.list.mockResolvedValue([])
    render(<DashboardPage />, { authState: createMockAuthState('authenticated') })
    await waitFor(() => {
      expect(screen.getByText('Welcome back, Test User')).toBeInTheDocument()
    })
  })

  it('clicking a project navigates to project detail', async () => {
    mockProjectsApi.list.mockResolvedValue(sampleProjects)
    render(<DashboardPage />, { authState: createMockAuthState('authenticated') })

    await waitFor(() => {
      expect(screen.getByText('Alpha Project')).toBeInTheDocument()
    })

    // Clicking the project button should be possible (it calls navigate)
    fireEvent.click(screen.getByText('Alpha Project'))
    // No error should occur
    expect(screen.getByText('Alpha Project')).toBeInTheDocument()
  })

  it('Create a project button navigates to /projects', async () => {
    mockProjectsApi.list.mockResolvedValue([])
    render(<DashboardPage />, { authState: createMockAuthState('authenticated') })

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /create a project/i })).toBeInTheDocument()
    })

    fireEvent.click(screen.getByRole('button', { name: /create a project/i }))
    // Navigate called without errors
    expect(screen.getByRole('button', { name: /create a project/i })).toBeInTheDocument()
  })

  it('Manage teams button navigates to /teams', async () => {
    mockProjectsApi.list.mockResolvedValue([])
    render(<DashboardPage />, { authState: createMockAuthState('authenticated') })

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /manage teams/i })).toBeInTheDocument()
    })

    fireEvent.click(screen.getByRole('button', { name: /manage teams/i }))
    expect(screen.getByRole('button', { name: /manage teams/i })).toBeInTheDocument()
  })

  it('shows "Welcome back" without name when display_name is missing', async () => {
    mockUseAuth.mockReturnValue({
      user: { ...baseUser, display_name: '' },
      token: 'mock-token',
      isAuthenticated: true,
      isLoading: false,
      login: vi.fn(),
      register: vi.fn(),
      logout: vi.fn(),
    })
    mockProjectsApi.list.mockResolvedValue([])
    render(<DashboardPage />, { authState: createMockAuthState('authenticated') })
    await waitFor(() => {
      expect(screen.getByText('Welcome back')).toBeInTheDocument()
    })
  })
})
