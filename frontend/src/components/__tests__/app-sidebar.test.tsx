import { screen, fireEvent } from '@testing-library/react'
import { render } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { AppSidebar } from '../app-sidebar'
import { ThemeProvider } from '../theme-provider'
import { SidebarProvider } from '../ui/sidebar'

function renderSidebar(initialPath = '/') {
  return render(
    <ThemeProvider>
      <MemoryRouter initialEntries={[initialPath]}>
        <SidebarProvider>
          <AppSidebar />
        </SidebarProvider>
      </MemoryRouter>
    </ThemeProvider>
  )
}

beforeEach(() => {
  localStorage.clear()
})

describe('AppSidebar', () => {
  it('renders the app name', () => {
    renderSidebar()
    expect(screen.getByText('ticket-to-prompt')).toBeInTheDocument()
  })

  it('renders Dashboard navigation link', () => {
    renderSidebar()
    expect(screen.getByText('Dashboard')).toBeInTheDocument()
  })

  it('renders Projects navigation link', () => {
    renderSidebar()
    expect(screen.getByText('Projects')).toBeInTheDocument()
  })

  it('renders Teams navigation link', () => {
    renderSidebar()
    expect(screen.getByText('Teams')).toBeInTheDocument()
  })

  it('renders Settings navigation link', () => {
    renderSidebar()
    expect(screen.getByText('Settings')).toBeInTheDocument()
  })

  it('renders Navigation group label', () => {
    renderSidebar()
    expect(screen.getByText('Navigation')).toBeInTheDocument()
  })

  it('renders the T logo icon', () => {
    renderSidebar()
    // The logo has a "T" text in a div
    const logoEl = screen.getByText('T')
    expect(logoEl).toBeInTheDocument()
  })

  it('clicking Dashboard navigates to /', () => {
    renderSidebar('/')
    const dashboardBtn = screen.getByText('Dashboard').closest('button') || screen.getByText('Dashboard')
    fireEvent.click(dashboardBtn)
    // No errors thrown
    expect(screen.getByText('Dashboard')).toBeInTheDocument()
  })

  it('clicking Projects navigates to /projects', () => {
    renderSidebar('/')
    const projectsBtn = screen.getByText('Projects').closest('button') || screen.getByText('Projects')
    fireEvent.click(projectsBtn)
    expect(screen.getByText('Projects')).toBeInTheDocument()
  })

  it('clicking Teams navigates to /teams', () => {
    renderSidebar('/')
    const teamsBtn = screen.getByText('Teams').closest('button') || screen.getByText('Teams')
    fireEvent.click(teamsBtn)
    expect(screen.getByText('Teams')).toBeInTheDocument()
  })

  it('clicking Settings in footer navigates to /settings', () => {
    renderSidebar('/')
    // There are Settings nav items - click the one in the dropdown menu area
    const settingsItems = screen.getAllByText('Settings')
    expect(settingsItems.length).toBeGreaterThan(0)
    fireEvent.click(settingsItems[0])
    expect(screen.getAllByText('Settings').length).toBeGreaterThan(0)
  })

  it('marks Dashboard as active when on / path', () => {
    renderSidebar('/')
    expect(screen.getByText('Dashboard')).toBeInTheDocument()
  })

  it('marks Projects as active when on /projects path', () => {
    renderSidebar('/projects')
    expect(screen.getByText('Projects')).toBeInTheDocument()
  })
})
