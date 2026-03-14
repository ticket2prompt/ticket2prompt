import { screen, fireEvent } from '@testing-library/react'
import { render } from '@testing-library/react'
import { ThemeProvider, useTheme } from '../theme-provider'

// Helper component to read and set theme
function ThemeConsumer() {
  const { theme, setTheme } = useTheme()
  return (
    <div>
      <span data-testid="current-theme">{theme}</span>
      <button onClick={() => setTheme('dark')}>Set Dark</button>
      <button onClick={() => setTheme('light')}>Set Light</button>
      <button onClick={() => setTheme('system')}>Set System</button>
    </div>
  )
}

beforeEach(() => {
  localStorage.clear()
  // Reset document class list
  document.documentElement.classList.remove('light', 'dark')
})

describe('ThemeProvider', () => {
  it('provides theme context with default system theme', () => {
    render(
      <ThemeProvider>
        <ThemeConsumer />
      </ThemeProvider>
    )

    expect(screen.getByTestId('current-theme')).toHaveTextContent('system')
  })

  it('uses defaultTheme prop', () => {
    render(
      <ThemeProvider defaultTheme="dark">
        <ThemeConsumer />
      </ThemeProvider>
    )

    expect(screen.getByTestId('current-theme')).toHaveTextContent('dark')
  })

  it('reads theme from localStorage', () => {
    localStorage.setItem('ttp-theme', 'light')

    render(
      <ThemeProvider>
        <ThemeConsumer />
      </ThemeProvider>
    )

    expect(screen.getByTestId('current-theme')).toHaveTextContent('light')
  })

  it('setTheme updates the theme value', () => {
    render(
      <ThemeProvider defaultTheme="light">
        <ThemeConsumer />
      </ThemeProvider>
    )

    expect(screen.getByTestId('current-theme')).toHaveTextContent('light')

    fireEvent.click(screen.getByText('Set Dark'))

    expect(screen.getByTestId('current-theme')).toHaveTextContent('dark')
  })

  it('setTheme persists to localStorage', () => {
    render(
      <ThemeProvider storageKey="test-theme-key">
        <ThemeConsumer />
      </ThemeProvider>
    )

    fireEvent.click(screen.getByText('Set Dark'))

    expect(localStorage.getItem('test-theme-key')).toBe('dark')
  })

  it('applies theme class to documentElement', () => {
    render(
      <ThemeProvider defaultTheme="dark">
        <ThemeConsumer />
      </ThemeProvider>
    )

    expect(document.documentElement.classList.contains('dark')).toBe(true)
  })

  it('throws error when useTheme is used outside ThemeProvider', () => {
    // Suppress console.error for this test
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {})

    expect(() => {
      render(<ThemeConsumer />)
    }).toThrow('useTheme must be used within a ThemeProvider')

    spy.mockRestore()
  })

  it('switches from dark to light theme', () => {
    render(
      <ThemeProvider defaultTheme="dark">
        <ThemeConsumer />
      </ThemeProvider>
    )

    expect(screen.getByTestId('current-theme')).toHaveTextContent('dark')

    fireEvent.click(screen.getByText('Set Light'))

    expect(screen.getByTestId('current-theme')).toHaveTextContent('light')
    expect(document.documentElement.classList.contains('light')).toBe(true)
    expect(document.documentElement.classList.contains('dark')).toBe(false)
  })
})
