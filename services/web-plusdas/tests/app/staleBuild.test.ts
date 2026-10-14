// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { isChunkLoadError, reloadForNewBuild } from '@/app/staleBuild';

afterEach(() => window.sessionStorage.clear());

describe('isChunkLoadError', () => {
  it("recognizes each browser's failed dynamic import", () => {
    expect(isChunkLoadError(new TypeError('Failed to fetch dynamically imported module: http://localhost:5173/assets/ReportViewPage-CvpwRNFc.js'))).toBe(true);
    expect(isChunkLoadError(new TypeError('error loading dynamically imported module'))).toBe(true);
    expect(isChunkLoadError(new TypeError('Importing a module script failed.'))).toBe(true);
  });

  it('leaves every other error alone', () => {
    expect(isChunkLoadError(new Error("Cannot read properties of undefined (reading 'map')"))).toBe(false);
    expect(isChunkLoadError(null)).toBe(false);
  });
});

describe('reloadForNewBuild', () => {
  it('reloads once, then not again within 10 s, then again later', () => {
    const reload = vi.fn();
    expect(reloadForNewBuild(1_000_000, reload)).toBe(true);
    expect(reloadForNewBuild(1_005_000, reload)).toBe(false); // the reload didn't help: show the error
    expect(reloadForNewBuild(1_011_000, reload)).toBe(true);
    expect(reload).toHaveBeenCalledTimes(2);
  });
});
