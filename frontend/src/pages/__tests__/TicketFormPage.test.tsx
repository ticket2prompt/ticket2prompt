import { screen, waitFor, fireEvent } from '@testing-library/react'
import { render, createMockAuthState } from '../../test/test-utils'
import TicketFormPage from '../TicketFormPage'
import { ticketsApi } from '../../api/tickets'

vi.mock('../../api/tickets', () => ({
  ticketsApi: {
    submit: vi.fn(),
  },
}))

vi.mock('@/contexts/auth-context', () => ({
  useAuth: vi.fn(),
}))

import { useAuth } from '@/contexts/auth-context'

const mockUseAuth = useAuth as ReturnType<typeof vi.fn>
const mockTicketsApi = ticketsApi as { submit: ReturnType<typeof vi.fn> }

const mockNavigate = vi.fn()
vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router-dom')>()
  return {
    ...actual,
    useNavigate: () => mockNavigate,
    useParams: () => ({ projectId: 'proj-123' }),
  }
})

// Mock crypto.randomUUID so we can verify fallback UUID generation
const mockUUID = 'generated-uuid-1234'
vi.stubGlobal('crypto', {
  ...globalThis.crypto,
  randomUUID: vi.fn().mockReturnValue(mockUUID),
})

beforeEach(() => {
  vi.clearAllMocks()
  mockUseAuth.mockReturnValue({
    user: { user_id: 'u1', email: 'a@b.com', display_name: 'Alice', org_id: 'o1', role: 'member' },
    token: 'mock-token',
    isAuthenticated: true,
    isLoading: false,
    login: vi.fn(),
    register: vi.fn(),
    logout: vi.fn(),
  })
})

describe('TicketFormPage', () => {
  it('submits ticket with required fields', async () => {
    mockTicketsApi.submit.mockResolvedValue({ ticket_id: 'PROJ-123', status: 'queued', message: 'ok' })
    render(<TicketFormPage />, { authState: createMockAuthState('authenticated'), initialEntries: ['/projects/proj-123/ticket'] })

    fireEvent.change(screen.getByLabelText(/Ticket ID/), { target: { value: 'PROJ-123' } })
    fireEvent.change(screen.getByLabelText(/Title/), { target: { value: 'Fix the bug' } })
    fireEvent.change(screen.getByLabelText(/Description/), { target: { value: 'There is a bug.' } })

    fireEvent.click(screen.getByRole('button', { name: 'Generate prompt' }))

    await waitFor(() => {
      expect(mockTicketsApi.submit).toHaveBeenCalledWith('proj-123', expect.objectContaining({
        ticket_id: 'PROJ-123',
        title: 'Fix the bug',
        description: 'There is a bug.',
      }))
    })
  })

  it('generates UUID when ticket_id is empty', async () => {
    mockTicketsApi.submit.mockResolvedValue({ ticket_id: mockUUID, status: 'queued', message: 'ok' })
    render(<TicketFormPage />, { authState: createMockAuthState('authenticated'), initialEntries: ['/projects/proj-123/ticket'] })

    // Leave ticket_id empty, only fill title
    fireEvent.change(screen.getByLabelText(/Title/), { target: { value: 'Auto ID ticket' } })
    fireEvent.click(screen.getByRole('button', { name: 'Generate prompt' }))

    await waitFor(() => {
      expect(mockTicketsApi.submit).toHaveBeenCalledWith('proj-123', expect.objectContaining({
        ticket_id: mockUUID,
        title: 'Auto ID ticket',
      }))
    })
  })

  it('navigates to prompt result page on success', async () => {
    mockTicketsApi.submit.mockResolvedValue({ ticket_id: 'PROJ-456', status: 'queued', message: 'ok' })
    render(<TicketFormPage />, { authState: createMockAuthState('authenticated'), initialEntries: ['/projects/proj-123/ticket'] })

    fireEvent.change(screen.getByLabelText(/Title/), { target: { value: 'My ticket' } })
    fireEvent.click(screen.getByRole('button', { name: 'Generate prompt' }))

    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith('/projects/proj-123/prompt/PROJ-456')
    })
  })

  it('shows error on failed submission', async () => {
    mockTicketsApi.submit.mockRejectedValue(new Error('Service unavailable'))
    render(<TicketFormPage />, { authState: createMockAuthState('authenticated'), initialEntries: ['/projects/proj-123/ticket'] })

    fireEvent.change(screen.getByLabelText(/Title/), { target: { value: 'Failing ticket' } })
    fireEvent.click(screen.getByRole('button', { name: 'Generate prompt' }))

    await waitFor(() => {
      expect(screen.getByText('Service unavailable')).toBeInTheDocument()
    })
    expect(mockNavigate).not.toHaveBeenCalled()
  })

  it('acceptance_criteria textarea onChange updates form', () => {
    render(<TicketFormPage />, { authState: createMockAuthState('authenticated'), initialEntries: ['/projects/proj-123/ticket'] })

    const acTextarea = screen.getByLabelText(/Acceptance criteria/)
    fireEvent.change(acTextarea, { target: { value: 'Given x, when y, then z' } })

    expect((acTextarea as HTMLTextAreaElement).value).toBe('Given x, when y, then z')
  })

  it('shows fallback error when non-Error thrown during submission', async () => {
    mockTicketsApi.submit.mockRejectedValue('string error')
    render(<TicketFormPage />, { authState: createMockAuthState('authenticated'), initialEntries: ['/projects/proj-123/ticket'] })

    fireEvent.change(screen.getByLabelText(/Title/), { target: { value: 'My ticket' } })
    fireEvent.click(screen.getByRole('button', { name: 'Generate prompt' }))

    await waitFor(() => {
      expect(screen.getByText('Failed to submit ticket')).toBeInTheDocument()
    })
  })
})
