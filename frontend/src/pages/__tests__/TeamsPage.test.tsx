import { screen, waitFor, fireEvent } from '@testing-library/react'
import { render, createMockAuthState } from '../../test/test-utils'
import TeamsPage from '../TeamsPage'
import { teamsApi } from '../../api/teams'
import type { TeamResponse } from '../../api/types'

vi.mock('../../api/teams', () => ({
  teamsApi: {
    list: vi.fn(),
    create: vi.fn(),
  },
}))

vi.mock('@/contexts/auth-context', () => ({
  useAuth: vi.fn(),
}))

import { useAuth } from '@/contexts/auth-context'

const mockUseAuth = useAuth as ReturnType<typeof vi.fn>
const mockTeamsApi = teamsApi as unknown as {
  list: ReturnType<typeof vi.fn>
  create: ReturnType<typeof vi.fn>
}

const baseUser = {
  user_id: 'test-user-id',
  email: 'test@example.com',
  display_name: 'Test User',
  org_id: 'test-org-id',
  role: 'member',
}

const sampleTeams: TeamResponse[] = [
  {
    team_id: 't1',
    org_id: 'test-org-id',
    name: 'Engineering',
    created_at: '2024-01-01T00:00:00Z',
  },
  {
    team_id: 't2',
    org_id: 'test-org-id',
    name: 'Design',
    created_at: '2024-02-01T00:00:00Z',
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

describe('TeamsPage', () => {
  it('loads teams on mount', async () => {
    mockTeamsApi.list.mockResolvedValue(sampleTeams)

    render(<TeamsPage />, { authState: createMockAuthState('authenticated') })

    await waitFor(() => {
      expect(mockTeamsApi.list).toHaveBeenCalledWith('test-org-id')
    })
  })

  it('displays teams after loading', async () => {
    mockTeamsApi.list.mockResolvedValue(sampleTeams)

    render(<TeamsPage />, { authState: createMockAuthState('authenticated') })

    await waitFor(() => {
      expect(screen.getByText('Engineering')).toBeInTheDocument()
      expect(screen.getByText('Design')).toBeInTheDocument()
    })
  })

  it('shows empty state when no teams', async () => {
    mockTeamsApi.list.mockResolvedValue([])

    render(<TeamsPage />, { authState: createMockAuthState('authenticated') })

    await waitFor(() => {
      expect(screen.getByText('No teams yet')).toBeInTheDocument()
    })
  })

  it('shows empty state description', async () => {
    mockTeamsApi.list.mockResolvedValue([])

    render(<TeamsPage />, { authState: createMockAuthState('authenticated') })

    await waitFor(() => {
      expect(screen.getByText(/organize your members/i)).toBeInTheDocument()
    })
  })

  it('creates a team successfully', async () => {
    mockTeamsApi.list.mockResolvedValue([])
    const newTeam: TeamResponse = {
      team_id: 't3',
      org_id: 'test-org-id',
      name: 'Backend',
      created_at: '2024-03-01T00:00:00Z',
    }
    mockTeamsApi.create.mockResolvedValue(newTeam)
    // After create, list returns the new team
    mockTeamsApi.list
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce([newTeam])

    render(<TeamsPage />, { authState: createMockAuthState('authenticated') })

    await waitFor(() => {
      expect(screen.getByText('No teams yet')).toBeInTheDocument()
    })

    // Open dialog via header button
    const newTeamBtn = screen.getAllByRole('button', { name: /new team/i })[0]
    fireEvent.click(newTeamBtn)

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Create team' })).toBeInTheDocument()
    })

    const nameInput = screen.getByLabelText('Team name')
    fireEvent.change(nameInput, { target: { value: 'Backend' } })

    fireEvent.click(screen.getByRole('button', { name: /create team/i }))

    await waitFor(() => {
      expect(mockTeamsApi.create).toHaveBeenCalledWith('test-org-id', { name: 'Backend' })
    })
  })

  it('shows Teams page heading', async () => {
    mockTeamsApi.list.mockResolvedValue([])

    render(<TeamsPage />, { authState: createMockAuthState('authenticated') })

    await waitFor(() => {
      expect(screen.getByText('Teams')).toBeInTheDocument()
    })
  })

  it('empty state New team button opens dialog', async () => {
    mockTeamsApi.list.mockResolvedValue([])

    render(<TeamsPage />, { authState: createMockAuthState('authenticated') })

    await waitFor(() => {
      expect(screen.getByText('No teams yet')).toBeInTheDocument()
    })

    // There's a "New team" button in the empty state action
    const newTeamBtns = screen.getAllByRole('button', { name: /new team/i })
    expect(newTeamBtns.length).toBeGreaterThan(0)
    // Click the empty state button (which calls setDialogOpen(true))
    fireEvent.click(newTeamBtns[newTeamBtns.length - 1])

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Create team' })).toBeInTheDocument()
    })
  })

  it('does not load teams when user has no org_id', async () => {
    mockUseAuth.mockReturnValue({
      user: { ...baseUser, org_id: '' },
      token: null,
      isAuthenticated: false,
      isLoading: false,
      login: vi.fn(),
      register: vi.fn(),
      logout: vi.fn(),
    })

    render(<TeamsPage />, { authState: createMockAuthState('unauthenticated') })

    await new Promise((r) => setTimeout(r, 50))
    expect(mockTeamsApi.list).not.toHaveBeenCalled()
  })
})
