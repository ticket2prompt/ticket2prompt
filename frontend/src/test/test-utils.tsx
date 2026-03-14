import { render, type RenderOptions } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { createContext, useContext, type ReactNode } from 'react';

interface User {
  user_id: string;
  email: string;
  display_name: string;
  org_id: string;
  role: string;
}

interface AuthContextType {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (data: { email: string; password: string; display_name: string; org_name: string; org_slug: string }) => Promise<void>;
  logout: () => void;
}

const MockAuthContext = createContext<AuthContextType | undefined>(undefined);

export function useMockAuth() {
  const context = useContext(MockAuthContext);
  if (!context) throw new Error('useMockAuth must be used within a MockAuthProvider');
  return context;
}

const defaultUnauthenticated: AuthContextType = {
  user: null,
  token: null,
  isAuthenticated: false,
  isLoading: false,
  login: vi.fn().mockResolvedValue(undefined),
  register: vi.fn().mockResolvedValue(undefined),
  logout: vi.fn(),
};

const defaultUser: User = {
  user_id: 'test-user-id',
  email: 'test@example.com',
  display_name: 'Test User',
  org_id: 'test-org-id',
  role: 'member',
};

const defaultAuthenticated: AuthContextType = {
  user: defaultUser,
  token: 'mock-token',
  isAuthenticated: true,
  isLoading: false,
  login: vi.fn().mockResolvedValue(undefined),
  register: vi.fn().mockResolvedValue(undefined),
  logout: vi.fn(),
};

const defaultLoading: AuthContextType = {
  user: null,
  token: null,
  isAuthenticated: false,
  isLoading: true,
  login: vi.fn().mockResolvedValue(undefined),
  register: vi.fn().mockResolvedValue(undefined),
  logout: vi.fn(),
};

export function createMockAuthState(
  variant: 'authenticated' | 'unauthenticated' | 'loading',
  overrides?: Partial<AuthContextType>,
): AuthContextType {
  const base =
    variant === 'authenticated'
      ? defaultAuthenticated
      : variant === 'loading'
        ? defaultLoading
        : defaultUnauthenticated;
  return { ...base, ...overrides };
}

interface WrapperOptions extends RenderOptions {
  authState?: AuthContextType;
  initialEntries?: string[];
}

function createWrapper(authState: AuthContextType, initialEntries: string[]) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return (
      <MemoryRouter initialEntries={initialEntries}>
        <MockAuthContext value={authState}>
          {children}
        </MockAuthContext>
      </MemoryRouter>
    );
  };
}

export function renderWithProviders(
  ui: React.ReactElement,
  {
    authState = defaultUnauthenticated,
    initialEntries = ['/'],
    ...renderOptions
  }: WrapperOptions = {},
) {
  const Wrapper = createWrapper(authState, initialEntries);
  return render(ui, { wrapper: Wrapper, ...renderOptions });
}

export * from '@testing-library/react';
export { renderWithProviders as render };
