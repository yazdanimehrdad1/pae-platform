import { vi } from 'vitest';

// A window.matchMedia for a viewport the test sets: it answers (min|max)-(width|height) queries,
// joined with "and", and notifies listeners when the test resizes the viewport.
export function stubViewport(initialWidth: number, initialHeight = 900) {
  let width = initialWidth;
  let height = initialHeight;
  const listeners = new Set<() => void>();
  const matches = (query: string) =>
    [...query.matchAll(/\((min|max)-(width|height): (\d+)px\)/g)].every(([, bound, side, pixels]) => {
      const size = side === 'width' ? width : height;
      return bound === 'min' ? size >= Number(pixels) : size <= Number(pixels);
    });
  vi.stubGlobal('matchMedia', (query: string) => ({
    get matches() { return matches(query); },
    media: query,
    addEventListener: (_type: string, listener: () => void) => listeners.add(listener),
    removeEventListener: (_type: string, listener: () => void) => listeners.delete(listener),
  }));
  return (nextWidth: number, nextHeight = height) => {
    width = nextWidth;
    height = nextHeight;
    listeners.forEach((listener) => listener());
  };
}
