// Vitest setup (vite.config.ts `test.setupFiles`), run in every test file.
import { afterEach } from 'vitest';

if (typeof window !== 'undefined') {
  // Browser APIs that jsdom lacks but Radix UI components call on mount; the tests don't
  // depend on their behavior.
  class ResizeObserverStub {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
  globalThis.ResizeObserver ??= ResizeObserverStub as unknown as typeof ResizeObserver;

  // Testing Library only unmounts automatically when vitest globals are on (they are not), so
  // a still-open modal from one test would capture the next test's clicks.
  afterEach(async () => {
    const { cleanup } = await import('@testing-library/react');
    cleanup();
  });
}
