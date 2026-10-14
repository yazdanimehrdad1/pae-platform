// @vitest-environment jsdom
import { afterEach, describe, expect, it } from 'vitest';
import { act, renderHook } from '@testing-library/react';
import { BROWSER_TIME_ZONE, useDisplayTimeZone } from '@/shared/hooks/useDisplayTimeZone';

// A zone that differs from the machine running the tests, whatever that is.
const SITE_ZONE = BROWSER_TIME_ZONE === 'Asia/Tokyo' ? 'Europe/Berlin' : 'Asia/Tokyo';

afterEach(() => {
  const { result } = renderHook(() => useDisplayTimeZone(SITE_ZONE));
  act(() => result.current.setDisplay('site'));
  window.localStorage.clear();
});

describe('useDisplayTimeZone', () => {
  it("shows the site's zone by default", () => {
    const { result } = renderHook(() => useDisplayTimeZone(SITE_ZONE));
    expect(result.current).toMatchObject({ display: 'site', timeZone: SITE_ZONE, siteTimeZone: SITE_ZONE });
  });

  it("switches to the browser's zone, remembers it, and every page follows", () => {
    const first = renderHook(() => useDisplayTimeZone(SITE_ZONE));
    const second = renderHook(() => useDisplayTimeZone('UTC'));
    act(() => first.result.current.setDisplay('browser'));
    expect(first.result.current.timeZone).toBe(BROWSER_TIME_ZONE);
    expect(second.result.current.timeZone).toBe(BROWSER_TIME_ZONE);
    expect(window.localStorage.getItem('pae.timeDisplay')).toBe('browser');
  });

  it("uses the browser's zone while the site's isn't known", () => {
    const { result } = renderHook(() => useDisplayTimeZone(undefined));
    expect(result.current).toMatchObject({ timeZone: BROWSER_TIME_ZONE, siteTimeZone: null });
  });
});
