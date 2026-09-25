// @vitest-environment jsdom
import { afterEach, describe, expect, it } from 'vitest';
import { getRuntimeConfig } from './runtime';

describe('getRuntimeConfig', () => {
  afterEach(() => {
    delete window.__APP_CONFIG__;
  });

  it('defaults the API base to the same-origin /api when /config.js set nothing', () => {
    expect(getRuntimeConfig()).toEqual({ apiBaseUrl: '/api' });
  });

  it('uses the value /config.js injected at container start', () => {
    window.__APP_CONFIG__ = { apiBaseUrl: '/platform/api' };
    expect(getRuntimeConfig().apiBaseUrl).toBe('/platform/api');
  });

  it('falls back to /api when the container env var was empty', () => {
    window.__APP_CONFIG__ = { apiBaseUrl: '' };
    expect(getRuntimeConfig().apiBaseUrl).toBe('/api');
  });
});
