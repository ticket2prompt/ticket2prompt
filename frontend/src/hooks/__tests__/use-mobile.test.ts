import { renderHook, act } from '@testing-library/react'
import { useIsMobile } from '../use-mobile'

const MOBILE_BREAKPOINT = 768

function setWindowWidth(width: number) {
  Object.defineProperty(window, 'innerWidth', {
    writable: true,
    configurable: true,
    value: width,
  })
}

// Mock matchMedia
function createMatchMedia(matches: boolean) {
  const listeners: Array<(e: MediaQueryListEvent) => void> = []
  return {
    matches,
    addEventListener: (event: string, cb: (e: MediaQueryListEvent) => void) => {
      if (event === 'change') listeners.push(cb)
    },
    removeEventListener: (_event: string, cb: (e: MediaQueryListEvent) => void) => {
      const idx = listeners.indexOf(cb)
      if (idx > -1) listeners.splice(idx, 1)
    },
    triggerChange: () => {
      listeners.forEach(cb => cb({} as MediaQueryListEvent))
    },
  }
}

beforeEach(() => {
  setWindowWidth(1024)
})

describe('useIsMobile', () => {
  it('returns false for desktop width (1024px)', () => {
    setWindowWidth(1024)
    window.matchMedia = vi.fn().mockReturnValue(createMatchMedia(false))

    const { result } = renderHook(() => useIsMobile())
    expect(result.current).toBe(false)
  })

  it('returns true for mobile width (375px)', () => {
    setWindowWidth(375)
    window.matchMedia = vi.fn().mockReturnValue(createMatchMedia(true))

    const { result } = renderHook(() => useIsMobile())
    expect(result.current).toBe(true)
  })

  it('returns false at exactly breakpoint (768px)', () => {
    setWindowWidth(MOBILE_BREAKPOINT)
    window.matchMedia = vi.fn().mockReturnValue(createMatchMedia(false))

    const { result } = renderHook(() => useIsMobile())
    expect(result.current).toBe(false)
  })

  it('returns true just below breakpoint (767px)', () => {
    setWindowWidth(MOBILE_BREAKPOINT - 1)
    window.matchMedia = vi.fn().mockReturnValue(createMatchMedia(true))

    const { result } = renderHook(() => useIsMobile())
    expect(result.current).toBe(true)
  })

  it('updates when window resizes to mobile', () => {
    setWindowWidth(1024)
    const mql = createMatchMedia(false)
    window.matchMedia = vi.fn().mockReturnValue(mql)

    const { result } = renderHook(() => useIsMobile())
    expect(result.current).toBe(false)

    act(() => {
      setWindowWidth(375)
      mql.triggerChange()
    })

    expect(result.current).toBe(true)
  })

  it('cleans up event listener on unmount', () => {
    setWindowWidth(1024)
    const mql = createMatchMedia(false)
    const removeEventListenerSpy = vi.spyOn(mql, 'removeEventListener')
    window.matchMedia = vi.fn().mockReturnValue(mql)

    const { unmount } = renderHook(() => useIsMobile())
    unmount()

    expect(removeEventListenerSpy).toHaveBeenCalledWith('change', expect.any(Function))
  })
})
