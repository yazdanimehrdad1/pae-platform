// @vitest-environment jsdom
import { describe, expect, it, vi } from 'vitest';
import { act, renderHook } from '@testing-library/react';
import { useBreakpoint } from '@/shared/hooks/use-mobile';
import { stubViewport } from './viewportStub';

describe('useBreakpoint', () => {
  it.each([
    [390, 844, 'phone'],
    [767, 900, 'phone'],
    [768, 1024, 'tablet'],
    [1024, 768, 'tablet'],
    [1279, 800, 'tablet'],
    [1280, 800, 'laptop'],
    [1440, 900, 'laptop'],
  ])('at %ix%i is %s', (width, height, expected) => {
    stubViewport(width, height);
    const { result } = renderHook(() => useBreakpoint());
    expect(result.current).toBe(expected);
  });

  it.each([
    [844, 390],
    [932, 430],
  ])('is a phone when a phone is turned sideways (%ix%i)', (width, height) => {
    stubViewport(width, height);
    const { result } = renderHook(() => useBreakpoint());
    expect(result.current).toBe('phone');
  });

  it('follows the window when it is resized or rotated', () => {
    const resize = stubViewport(1366, 768);
    const { result } = renderHook(() => useBreakpoint());
    expect(result.current).toBe('laptop');
    act(() => resize(1024, 768));
    expect(result.current).toBe('tablet');
    act(() => resize(390, 844));
    expect(result.current).toBe('phone');
    act(() => resize(844, 390));
    expect(result.current).toBe('phone');
  });

  it('is the laptop layout without matchMedia', () => {
    vi.stubGlobal('matchMedia', undefined);
    const { result } = renderHook(() => useBreakpoint());
    expect(result.current).toBe('laptop');
  });
});
