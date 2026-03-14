import { vi } from 'vitest'

// Mock the api client
vi.mock('../client', () => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}))

import { api } from '../client'
import apiClient from '../client'
import { authApi } from '../auth'
import { projectsApi } from '../projects'
import { reposApi } from '../repos'
import { teamsApi } from '../teams'
import { ticketsApi } from '../tickets'
import { promptsApi } from '../prompts'
import { orgsApi } from '../orgs'
import { getHealth } from '../health'
import { jiraSyncApi } from '../jira-sync'

const mockApi = api as unknown as {
  get: ReturnType<typeof vi.fn>
  post: ReturnType<typeof vi.fn>
  put: ReturnType<typeof vi.fn>
  delete: ReturnType<typeof vi.fn>
}

const mockApiClient = apiClient as unknown as {
  get: ReturnType<typeof vi.fn>
  post: ReturnType<typeof vi.fn>
  put: ReturnType<typeof vi.fn>
  delete: ReturnType<typeof vi.fn>
}

beforeEach(() => {
  vi.clearAllMocks()
  mockApi.get.mockResolvedValue({ data: {} })
  mockApi.post.mockResolvedValue({ data: {} })
  mockApi.put.mockResolvedValue({ data: {} })
  mockApi.delete.mockResolvedValue({ data: {} })
  mockApiClient.get.mockResolvedValue({ data: {} })
  mockApiClient.post.mockResolvedValue({ data: {} })
})

// ---- authApi ----
describe('authApi', () => {
  it('register calls POST /api/auth/register', async () => {
    mockApi.post.mockResolvedValue({ data: { access_token: 'tok', token_type: 'bearer', expires_in: 3600 } })
    await authApi.register({ email: 'a@b.com', password: 'pass', display_name: 'A', org_name: 'Org', org_slug: 'org' })
    expect(mockApi.post).toHaveBeenCalledWith('/api/auth/register', expect.any(Object))
  })

  it('login calls POST /api/auth/login', async () => {
    mockApi.post.mockResolvedValue({ data: { access_token: 'tok', token_type: 'bearer', expires_in: 3600 } })
    await authApi.login({ email: 'a@b.com', password: 'pass' })
    expect(mockApi.post).toHaveBeenCalledWith('/api/auth/login', expect.any(Object))
  })

  it('getMe calls GET /api/auth/me', async () => {
    mockApi.get.mockResolvedValue({ data: { user_id: 'u1', email: 'a@b.com', display_name: 'A', org_id: 'o1', role: 'member' } })
    await authApi.getMe()
    expect(mockApi.get).toHaveBeenCalledWith('/api/auth/me')
  })

  it('createApiKey calls POST /api/auth/api-keys', async () => {
    mockApi.post.mockResolvedValue({ data: { key_id: 'k1', name: 'test', prefix: 'sk-', created_at: '2024-01-01' } })
    await authApi.createApiKey({ name: 'test' })
    expect(mockApi.post).toHaveBeenCalledWith('/api/auth/api-keys', { name: 'test' })
  })
})

// ---- projectsApi ----
describe('projectsApi', () => {
  it('create calls POST /api/orgs/:orgId/projects', async () => {
    mockApi.post.mockResolvedValue({ data: { project_id: 'p1' } })
    await projectsApi.create('org1', { name: 'P', slug: 'p', github_repo_url: 'https://github.com/x/y' })
    expect(mockApi.post).toHaveBeenCalledWith('/api/orgs/org1/projects', expect.any(Object))
  })

  it('list calls GET /api/orgs/:orgId/projects', async () => {
    mockApi.get.mockResolvedValue({ data: [] })
    await projectsApi.list('org1')
    expect(mockApi.get).toHaveBeenCalledWith('/api/orgs/org1/projects')
  })

  it('get calls GET /api/orgs/:orgId/projects/:projectId', async () => {
    mockApi.get.mockResolvedValue({ data: { project_id: 'p1' } })
    await projectsApi.get('org1', 'p1')
    expect(mockApi.get).toHaveBeenCalledWith('/api/orgs/org1/projects/p1')
  })

  it('update calls PUT /api/orgs/:orgId/projects/:projectId', async () => {
    mockApi.put.mockResolvedValue({ data: { project_id: 'p1' } })
    await projectsApi.update('org1', 'p1', { name: 'New Name' })
    expect(mockApi.put).toHaveBeenCalledWith('/api/orgs/org1/projects/p1', { name: 'New Name' })
  })

  it('delete calls DELETE /api/orgs/:orgId/projects/:projectId', async () => {
    mockApi.delete.mockResolvedValue({ data: {} })
    await projectsApi.delete('org1', 'p1')
    expect(mockApi.delete).toHaveBeenCalledWith('/api/orgs/org1/projects/p1')
  })
})

// ---- reposApi ----
describe('reposApi', () => {
  it('index calls POST /api/projects/:projectId/index', async () => {
    mockApi.post.mockResolvedValue({ data: { job_id: 'job-1' } })
    await reposApi.index('p1')
    expect(mockApi.post).toHaveBeenCalledWith('/api/projects/p1/index', {})
  })

  it('index passes data when provided', async () => {
    mockApi.post.mockResolvedValue({ data: { job_id: 'job-1' } })
    await reposApi.index('p1', { branch: 'main' })
    expect(mockApi.post).toHaveBeenCalledWith('/api/projects/p1/index', { branch: 'main' })
  })

  it('getStatus calls GET /api/projects/:projectId/index/:jobId', async () => {
    mockApi.get.mockResolvedValue({ data: { status: 'completed' } })
    await reposApi.getStatus('p1', 'job-1')
    expect(mockApi.get).toHaveBeenCalledWith('/api/projects/p1/index/job-1')
  })
})

// ---- teamsApi ----
describe('teamsApi', () => {
  it('create calls POST /api/orgs/:orgId/teams', async () => {
    mockApi.post.mockResolvedValue({ data: { team_id: 't1' } })
    await teamsApi.create('org1', { name: 'Engineering' })
    expect(mockApi.post).toHaveBeenCalledWith('/api/orgs/org1/teams', { name: 'Engineering' })
  })

  it('list calls GET /api/orgs/:orgId/teams', async () => {
    mockApi.get.mockResolvedValue({ data: [] })
    await teamsApi.list('org1')
    expect(mockApi.get).toHaveBeenCalledWith('/api/orgs/org1/teams')
  })

  it('addMember calls POST /api/orgs/:orgId/teams/:teamId/members', async () => {
    mockApi.post.mockResolvedValue({ data: {} })
    await teamsApi.addMember('org1', 't1', { user_id: 'u1' })
    expect(mockApi.post).toHaveBeenCalledWith('/api/orgs/org1/teams/t1/members', { user_id: 'u1' })
  })
})

// ---- ticketsApi ----
describe('ticketsApi', () => {
  it('submit calls POST /api/projects/:projectId/ticket', async () => {
    mockApi.post.mockResolvedValue({ data: { ticket_id: 'TK-1', status: 'pending', message: 'ok' } })
    await ticketsApi.submit('p1', { ticket_id: 'TK-1', title: 'Fix bug', description: 'desc' })
    expect(mockApi.post).toHaveBeenCalledWith('/api/projects/p1/ticket', expect.any(Object))
  })
})

// ---- promptsApi ----
describe('promptsApi', () => {
  it('get calls GET /api/projects/:projectId/prompt/:ticketId', async () => {
    mockApi.get.mockResolvedValue({ data: { ticket_id: 'TK-1', prompt_text: 'prompt' } })
    await promptsApi.get('p1', 'TK-1')
    expect(mockApi.get).toHaveBeenCalledWith('/api/projects/p1/prompt/TK-1')
  })
})

// ---- orgsApi ----
describe('orgsApi', () => {
  it('create calls POST /api/orgs', async () => {
    mockApi.post.mockResolvedValue({ data: { org_id: 'o1' } })
    await orgsApi.create({ name: 'My Org', slug: 'my-org' })
    expect(mockApi.post).toHaveBeenCalledWith('/api/orgs', { name: 'My Org', slug: 'my-org' })
  })

  it('list calls GET /api/orgs', async () => {
    mockApi.get.mockResolvedValue({ data: [] })
    await orgsApi.list()
    expect(mockApi.get).toHaveBeenCalledWith('/api/orgs')
  })

  it('get calls GET /api/orgs/:orgId', async () => {
    mockApi.get.mockResolvedValue({ data: { org_id: 'o1' } })
    await orgsApi.get('o1')
    expect(mockApi.get).toHaveBeenCalledWith('/api/orgs/o1')
  })

  it('addMember calls POST /api/orgs/:orgId/members', async () => {
    mockApi.post.mockResolvedValue({ data: {} })
    await orgsApi.addMember('o1', { user_id: 'u1', role: 'member' })
    expect(mockApi.post).toHaveBeenCalledWith('/api/orgs/o1/members', { user_id: 'u1', role: 'member' })
  })
})

// ---- health ----
describe('getHealth', () => {
  it('calls GET /health', async () => {
    mockApiClient.get.mockResolvedValue({ data: { status: 'ok', version: '1.0.0' } })
    await getHealth()
    expect(mockApiClient.get).toHaveBeenCalledWith('/health')
  })
})

// ---- jiraSyncApi ----
describe('jiraSyncApi', () => {
  it('sync calls POST /api/projects/:projectId/jira/sync', async () => {
    mockApi.post.mockResolvedValue({ data: { job_id: 'sync-1', status: 'started' } })
    await jiraSyncApi.sync('p1')
    expect(mockApi.post).toHaveBeenCalledWith('/api/projects/p1/jira/sync')
  })

  it('getStatus calls GET /api/projects/:projectId/jira/sync/:jobId', async () => {
    mockApi.get.mockResolvedValue({ data: { job_id: 'sync-1', status: 'completed' } })
    await jiraSyncApi.getStatus('p1', 'sync-1')
    expect(mockApi.get).toHaveBeenCalledWith('/api/projects/p1/jira/sync/sync-1')
  })
})
