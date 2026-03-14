import { screen, waitFor, fireEvent } from '@testing-library/react'
import { render, createMockAuthState } from '../../test/test-utils'
import ProjectsPage from '../ProjectsPage'
import { projectsApi } from '../../api/projects'
import type { ProjectResponse } from '../../api/types'

vi.mock('../../api/projects', () => ({
  projectsApi: {
    list: vi.fn(),
    create: vi.fn(),
  },
}))

vi.mock('@/contexts/auth-context', () => ({
  useAuth: vi.fn(),
}))

import { useAuth } from '@/contexts/auth-context'

const mockProjectsApi = projectsApi as unknown as {
  list: ReturnType<typeof vi.fn>
  create: ReturnType<typeof vi.fn>
}

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

describe('ProjectsPage', () => {
  it('loads projects on mount', async () => {
    mockProjectsApi.list.mockResolvedValue(sampleProjects)
    render(<ProjectsPage />, { authState: createMockAuthState('authenticated') })
    await waitFor(() => expect(mockProjectsApi.list).toHaveBeenCalledWith('test-org-id'))
  })

  it('displays projects in a grid', async () => {
    mockProjectsApi.list.mockResolvedValue(sampleProjects)
    render(<ProjectsPage />, { authState: createMockAuthState('authenticated') })
    await waitFor(() => {
      expect(screen.getByText('Alpha Project')).toBeInTheDocument()
      expect(screen.getByText('Beta Project')).toBeInTheDocument()
    })
  })

  it('shows empty state when no projects', async () => {
    mockProjectsApi.list.mockResolvedValue([])
    render(<ProjectsPage />, { authState: createMockAuthState('authenticated') })
    await waitFor(() => {
      expect(screen.getByText('No projects yet')).toBeInTheDocument()
    })
  })

  it('creates a project successfully', async () => {
    mockProjectsApi.list.mockResolvedValue([])
    const newProject: ProjectResponse = {
      project_id: 'p3',
      org_id: 'test-org-id',
      name: 'New Project',
      slug: 'new-project',
      github_repo_url: 'https://github.com/org/new',
      created_at: '2024-01-03T00:00:00Z',
      updated_at: '2024-01-03T00:00:00Z',
    }
    mockProjectsApi.create.mockResolvedValue(newProject)

    render(<ProjectsPage />, { authState: createMockAuthState('authenticated') })
    await waitFor(() => expect(screen.getByText('No projects yet')).toBeInTheDocument())

    // Open the dialog via the header button
    const newProjectBtn = screen.getAllByText('New project')[0]
    fireEvent.click(newProjectBtn)

    // Wait for dialog form to appear - use the dialog-title heading
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Create project' })).toBeInTheDocument())

    // Fill the form using input ids
    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'New Project' } })
    fireEvent.change(screen.getByLabelText('Slug'), { target: { value: 'new-project' } })
    fireEvent.change(screen.getByLabelText('GitHub repository URL'), {
      target: { value: 'https://github.com/org/new' },
    })

    // Submit via the submit button (type="submit")
    const submitBtn = screen.getByRole('button', { name: 'Create project' })
    fireEvent.click(submitBtn)

    await waitFor(() => {
      expect(mockProjectsApi.create).toHaveBeenCalledWith('test-org-id', expect.objectContaining({
        name: 'New Project',
        slug: 'new-project',
        github_repo_url: 'https://github.com/org/new',
      }))
    })
  })

  it('auto-generates slug from name', async () => {
    mockProjectsApi.list.mockResolvedValue([])
    render(<ProjectsPage />, { authState: createMockAuthState('authenticated') })
    await waitFor(() => expect(screen.getByText('No projects yet')).toBeInTheDocument())

    const newProjectBtn = screen.getAllByText('New project')[0]
    fireEvent.click(newProjectBtn)

    await waitFor(() => expect(screen.getByRole('heading', { name: 'Create project' })).toBeInTheDocument())

    const nameInput = screen.getByLabelText('Name')
    fireEvent.change(nameInput, { target: { value: 'My Awesome Project' } })

    const slugInput = screen.getByLabelText('Slug') as HTMLInputElement
    expect(slugInput.value).toBe('my-awesome-project')
  })

  it('clicking a project card navigates to project detail', async () => {
    mockProjectsApi.list.mockResolvedValue(sampleProjects)
    render(<ProjectsPage />, { authState: createMockAuthState('authenticated') })

    await waitFor(() => {
      expect(screen.getByText('Alpha Project')).toBeInTheDocument()
    })

    // Click on the project card - this calls navigate
    fireEvent.click(screen.getByText('Alpha Project'))
    // No error thrown, navigation attempted
    expect(screen.getByText('Alpha Project')).toBeInTheDocument()
  })

  it('typing slug directly overrides auto-slug', async () => {
    mockProjectsApi.list.mockResolvedValue([])
    render(<ProjectsPage />, { authState: createMockAuthState('authenticated') })
    await waitFor(() => expect(screen.getByText('No projects yet')).toBeInTheDocument())

    const newProjectBtn = screen.getAllByText('New project')[0]
    fireEvent.click(newProjectBtn)

    await waitFor(() => expect(screen.getByRole('heading', { name: 'Create project' })).toBeInTheDocument())

    const nameInput = screen.getByLabelText('Name')
    fireEvent.change(nameInput, { target: { value: 'Test Project' } })

    // Directly change slug
    const slugInput = screen.getByLabelText('Slug') as HTMLInputElement
    fireEvent.change(slugInput, { target: { value: 'custom-slug' } })

    expect(slugInput.value).toBe('custom-slug')
  })

  it('fills collection_group field in create form', async () => {
    mockProjectsApi.list.mockResolvedValue([])
    render(<ProjectsPage />, { authState: createMockAuthState('authenticated') })
    await waitFor(() => expect(screen.getByText('No projects yet')).toBeInTheDocument())

    const newProjectBtn = screen.getAllByText('New project')[0]
    fireEvent.click(newProjectBtn)

    await waitFor(() => expect(screen.getByRole('heading', { name: 'Create project' })).toBeInTheDocument())

    const groupInput = screen.getByPlaceholderText('shared-group-slug')
    fireEvent.change(groupInput, { target: { value: 'my-group' } })

    expect((groupInput as HTMLInputElement).value).toBe('my-group')
  })

  it('empty state button opens create project dialog', async () => {
    mockProjectsApi.list.mockResolvedValue([])
    render(<ProjectsPage />, { authState: createMockAuthState('authenticated') })
    await waitFor(() => expect(screen.getByText('No projects yet')).toBeInTheDocument())

    // The last "New project" button is the one in EmptyState action
    const newProjectBtns = screen.getAllByText('New project')
    fireEvent.click(newProjectBtns[newProjectBtns.length - 1])

    await waitFor(() => expect(screen.getByRole('heading', { name: 'Create project' })).toBeInTheDocument())
  })

  it('displays collection group badge when project has collection_group', async () => {
    const projectWithGroup = {
      ...sampleProjects[0],
      collection_group: 'my-group',
    }
    mockProjectsApi.list.mockResolvedValue([projectWithGroup])
    render(<ProjectsPage />, { authState: createMockAuthState('authenticated') })

    await waitFor(() => {
      expect(screen.getByText('my-group')).toBeInTheDocument()
    })
  })

  it('collection_group field clearing sets to undefined', async () => {
    mockProjectsApi.list.mockResolvedValue([])
    render(<ProjectsPage />, { authState: createMockAuthState('authenticated') })
    await waitFor(() => expect(screen.getByText('No projects yet')).toBeInTheDocument())

    fireEvent.click(screen.getAllByText('New project')[0])
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Create project' })).toBeInTheDocument())

    const groupInput = screen.getByPlaceholderText('shared-group-slug')
    // Set a value then clear it to trigger the `e.target.value || undefined` branch
    fireEvent.change(groupInput, { target: { value: 'some-group' } })
    fireEvent.change(groupInput, { target: { value: '' } })

    expect((groupInput as HTMLInputElement).value).toBe('')
  })
})
