// @vitest-environment jsdom
import { describe, expect, it, vi } from 'vitest';
import { act, renderHook } from '@testing-library/react';
import { useBreakpoint } from '@/shared/hooks/use-mobile';

// A matchMedia that answers `(min-width: Npx)` queries for a window width the test can change.
function stubWindowWidth(initialWidth: number) {
  let width = initialWidth;
  const listeners = new Set<() => void>();
  vi.stubGlobal('matchMedia', (query: string) => {
    const minWidth = Number(/min-width: (\d+)px/.exec(query)?.[1] ?? 0);
    return {
      get matches() { return width >= minWidth; },
      media: query,
      addEventListener: (_type: string, listener: () => void) => listeners.add(listener),
      removeEventListener: (_type: string, listener: () => void) => listeners.delete(listener),
    };
  });
  return (nextWidth: number) => {
    width = nextWidth;
    listeners.forEach((listener) => listener());
  };
}

describe('useBreakpoint', () => {
  it.each([
    [390, 'phone'],
    [767, 'phone'],
    [768, 'tablet'],
    [1024, 'tablet'],
    [1279, 'tablet'],
    [1280, 'laptop'],
    [1440, 'laptop'],
  ])('at %ipx is %s', (width, expected) => {
    stubWindowWidth(width);
    const { result } = renderHook(() => useBreakpoint());
    expect(result.current).toBe(expected);
  });

  it('follows the window when it is resized or rotated', () => {
    const resize = stubWindowWidth(1366);
    const { result } = renderHook(() => useBreakpoint());
    expect(result.current).toBe('laptop');
    act(() => resize(1024));
    expect(result.current).toBe('tablet');
    act(() => resize(390));
    expect(result.current).toBe('phone');
  });

  it('is the laptop layout without matchMedia', () => {
    vi.stubGlobal('matchMedia', undefined);
    const { result } = renderHook(() => useBreakpoint());
    expect(result.current).toBe('laptop');
  });
});
