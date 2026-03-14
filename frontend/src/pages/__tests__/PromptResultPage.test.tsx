import { screen, waitFor, fireEvent, act } from '@testing-library/react'
import { render, createMockAuthState } from '../../test/test-utils'
import PromptResultPage from '../PromptResultPage'
import { promptsApi } from '../../api/prompts'

vi.mock('../../api/prompts', () => ({
  promptsApi: {
    get: vi.fn(),
  },
}))

vi.mock('@/contexts/auth-context', () => ({
  useAuth: vi.fn(),
}))

import { useAuth } from '@/contexts/auth-context'

const mockUseAuth = useAuth as ReturnType<typeof vi.fn>
const mockPromptsApi = promptsApi as { get: ReturnType<typeof vi.fn> }

vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router-dom')>()
  return {
    ...actual,
    useParams: () => ({ projectId: 'proj-123', ticketId: 'PROJ-456' }),
  }
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

describe('PromptResultPage', () => {
  it('fetches prompt on mount using projectId and ticketId from params', async () => {
    mockPromptsApi.get.mockResolvedValue({ ticket_id: 'PROJ-456', prompt_text: 'Generated prompt text here.' })
    render(<PromptResultPage />, { authState: createMockAuthState('authenticated'), initialEntries: ['/projects/proj-123/prompt/PROJ-456'] })

    await waitFor(() => {
      expect(mockPromptsApi.get).toHaveBeenCalledWith('proj-123', 'PROJ-456')
    })
  })

  it('displays the prompt content after loading', async () => {
    mockPromptsApi.get.mockResolvedValue({ ticket_id: 'PROJ-456', prompt_text: 'This is the generated prompt content.' })
    render(<PromptResultPage />, { authState: createMockAuthState('authenticated'), initialEntries: ['/projects/proj-123/prompt/PROJ-456'] })

    await waitFor(() => {
      expect(screen.getByText('This is the generated prompt content.')).toBeInTheDocument()
    })
  })

  it('shows copy button and copies text to clipboard', async () => {
    const promptText = 'Prompt to be copied.'
    mockPromptsApi.get.mockResolvedValue({ ticket_id: 'PROJ-456', prompt_text: promptText })

    const mockWriteText = vi.fn().mockResolvedValue(undefined)
    Object.defineProperty(navigator, 'clipboard', {
      value: { writeText: mockWriteText },
      writable: true,
      configurable: true,
    })

    render(<PromptResultPage />, { authState: createMockAuthState('authenticated'), initialEntries: ['/projects/proj-123/prompt/PROJ-456'] })

    await waitFor(() => expect(screen.getByText(promptText)).toBeInTheDocument())

    // The Copy button - find by accessible name (includes icon sr-only text + visible "Copy" text)
    const copyBtn = screen.getByRole('button', { name: /copy/i })
    await act(async () => {
      fireEvent.click(copyBtn)
    })

    expect(mockWriteText).toHaveBeenCalledWith(promptText)
    // Button text changes to "Copied" after click
    await waitFor(() => expect(screen.getByRole('button', { name: /copied/i })).toBeInTheDocument())
  })

  it('shows error message when fetch fails', async () => {
    mockPromptsApi.get.mockRejectedValue(new Error('Prompt not found'))
    render(<PromptResultPage />, { authState: createMockAuthState('authenticated'), initialEntries: ['/projects/proj-123/prompt/PROJ-456'] })

    await waitFor(() => {
      expect(screen.getByText('Prompt not found')).toBeInTheDocument()
    })
  })

  it('shows fallback error when non-Error thrown', async () => {
    mockPromptsApi.get.mockRejectedValue('string error')
    render(<PromptResultPage />, { authState: createMockAuthState('authenticated'), initialEntries: ['/projects/proj-123/prompt/PROJ-456'] })

    await waitFor(() => {
      expect(screen.getByText('Failed to load prompt')).toBeInTheDocument()
    })
  })
})
