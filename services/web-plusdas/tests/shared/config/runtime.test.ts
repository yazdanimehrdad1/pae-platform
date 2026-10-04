// @vitest-environment jsdom
import { afterEach, describe, expect, it } from 'vitest';
import { getRuntimeConfig } from '@/shared/config/runtime';

describe('getRuntimeConfig', () => {
  afterEach(() => {
    delete window.__APP_CONFIG__;
  });

  it('defaults the API bases to same-origin paths when /config.js set nothing', () => {
    expect(getRuntimeConfig()).toEqual({ apiBaseUrl: '/api', powerflowBaseUrl: '/powerflow-api' });
  });

  it('uses the value /config.js injected at container start', () => {
    window.__APP_CONFIG__ = { apiBaseUrl: '/platform/api' };
    expect(getRuntimeConfig().apiBaseUrl).toBe('/platform/api');
  });

  it('falls back to /api when the container env var was empty', () => {
    window.__APP_CONFIG__ = { apiBaseUrl: '' };
    expect(getRuntimeConfig().apiBaseUrl).toBe('/api');
  });

  it('uses the injected powerflow base, falling back to /powerflow-api when empty', () => {
    window.__APP_CONFIG__ = { powerflowBaseUrl: '/sim/api' };
    expect(getRuntimeConfig().powerflowBaseUrl).toBe('/sim/api');
    window.__APP_CONFIG__ = { powerflowBaseUrl: '' };
    expect(getRuntimeConfig().powerflowBaseUrl).toBe('/powerflow-api');
  });
});
