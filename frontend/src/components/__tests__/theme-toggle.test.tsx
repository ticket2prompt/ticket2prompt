import { screen, fireEvent } from '@testing-library/react'
import { render } from '@testing-library/react'
import { ThemeProvider } from '../theme-provider'
import { ThemeToggle } from '../theme-toggle'

function renderWithTheme(defaultTheme: 'light' | 'dark' | 'system' = 'system') {
  return render(
    <ThemeProvider defaultTheme={defaultTheme}>
      <ThemeToggle />
    </ThemeProvider>
  )
}

beforeEach(() => {
  localStorage.clear()
  document.documentElement.classList.remove('light', 'dark')
})

describe('ThemeToggle', () => {
  it('renders the toggle button', () => {
    renderWithTheme('light')
    expect(screen.getByRole('button', { name: /toggle theme/i })).toBeInTheDocument()
  })

  it('cycles from light to dark on click', () => {
    renderWithTheme('light')

    const button = screen.getByRole('button', { name: /toggle theme/i })
    fireEvent.click(button)

    // After clicking from light, theme should be dark
    expect(localStorage.getItem('ttp-theme')).toBe('dark')
  })

  it('cycles from dark to system on click', () => {
    renderWithTheme('dark')

    const button = screen.getByRole('button', { name: /toggle theme/i })
    fireEvent.click(button)

    expect(localStorage.getItem('ttp-theme')).toBe('system')
  })

  it('cycles from system to light on click', () => {
    renderWithTheme('system')

    const button = screen.getByRole('button', { name: /toggle theme/i })
    fireEvent.click(button)

    expect(localStorage.getItem('ttp-theme')).toBe('light')
  })

  it('has sr-only toggle theme text', () => {
    renderWithTheme()
    expect(screen.getByText('Toggle theme')).toBeInTheDocument()
  })
})
