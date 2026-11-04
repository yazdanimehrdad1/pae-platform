// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { meApi } from '@/api/me';
import type { Preference, SavedNote, SavedTrend } from '@/api/types/me';
import { importBrowserData } from '@/app/useBrowserDataImport';

const TRENDS = [
  { id: '1', name: 'Default Trend', points: ['101'], scale: 'per-point' },
  { id: '2', name: 'PV', points: [] },
];
const NOTES = [
  { id: 'note-2', content: 'newer', createdAt: '2026-10-02T00:00:00.000Z', updatedAt: '2026-10-03T00:00:00.000Z' },
  { id: 'note-1', content: 'older', createdAt: '2026-10-01T00:00:00.000Z', updatedAt: '2026-10-01T00:00:00.000Z' },
];

function seedBrowser() {
  localStorage.setItem('historian_trends_1', JSON.stringify(TRENDS));
  localStorage.setItem('user_notes', JSON.stringify(NOTES));
  localStorage.setItem('historian_discrete_mode_1', 'steps');
  localStorage.setItem('modbus_config_cache_1', JSON.stringify({ 1: { alias: 'BESS', request: {} } }));
  localStorage.setItem('site_devices_last_site', '1002');
  localStorage.setItem('pae.timeDisplay', 'browser');
  localStorage.setItem('user', '{"id":"1"}');
  localStorage.setItem('vite-ui-theme', 'dark'); // stays: theme is per browser
}

function server({ preferences = [], trends = [], notes = [] }: { preferences?: Preference[]; trends?: SavedTrend[]; notes?: SavedNote[] } = {}) {
  vi.spyOn(meApi, 'listPreferences').mockResolvedValue(preferences);
  vi.spyOn(meApi, 'listTrends').mockResolvedValue(trends);
  vi.spyOn(meApi, 'listNotes').mockResolvedValue(notes);
  vi.spyOn(meApi, 'putPreference').mockImplementation(async (key, value) => ({ key, value, updated_at: '' }) as Preference);
  vi.spyOn(meApi, 'createTrend').mockImplementation(async () => ({}) as SavedTrend);
  vi.spyOn(meApi, 'createNote').mockImplementation(async () => ({}) as SavedNote);
}

beforeEach(() => localStorage.clear());
afterEach(() => vi.restoreAllMocks());

describe('importing what this browser saved before accounts', () => {
  it('does nothing (and calls nothing) in a browser without old data', async () => {
    server();
    await importBrowserData();
    expect(meApi.listPreferences).not.toHaveBeenCalled();
  });

  it('copies trends, notes and preferences to the user, then removes them from the browser', async () => {
    seedBrowser();
    server();
    await importBrowserData();

    expect(vi.mocked(meApi.createTrend).mock.calls.map(([trend]) => trend)).toEqual([
      { name: 'Default Trend', points: ['101'], scale: 'per-point', styles: null },
      { name: 'PV', points: [], scale: null, styles: null },
    ]);
    expect(vi.mocked(meApi.createNote).mock.calls.map(([note]) => note)).toEqual([
      { content: 'older', created_at: '2026-10-01T00:00:00.000Z', updated_at: '2026-10-01T00:00:00.000Z' },
      { content: 'newer', created_at: '2026-10-02T00:00:00.000Z', updated_at: '2026-10-03T00:00:00.000Z' },
    ]);
    expect(Object.fromEntries(vi.mocked(meApi.putPreference).mock.calls)).toEqual({
      'time-display': 'browser',
      'site-devices.last-site': '1002',
      'historian.discrete-mode': 'steps',
      'live-data.configs': { 1: { alias: 'BESS', request: {} } },
    });
    expect(Object.keys(localStorage)).toEqual(['vite-ui-theme']);
  });

  it("never overwrites what the user already has, so a second browser adds nothing twice", async () => {
    seedBrowser();
    server({
      preferences: [{ key: 'time-display', value: 'site', updated_at: '' }],
      trends: [{ id: 9 } as SavedTrend],
      notes: [{ id: 9 } as SavedNote],
    });
    await importBrowserData();
    expect(meApi.createTrend).not.toHaveBeenCalled();
    expect(meApi.createNote).not.toHaveBeenCalled();
    expect(meApi.putPreference).not.toHaveBeenCalledWith('time-display', expect.anything());
    expect(meApi.putPreference).toHaveBeenCalledWith('site-devices.last-site', '1002');
  });

  it('keeps the old data in the browser when a save fails, for the next login', async () => {
    seedBrowser();
    server();
    vi.spyOn(meApi, 'createTrend').mockRejectedValue({ detail: 'down', status: 503 });
    await expect(importBrowserData()).rejects.toMatchObject({ status: 503 });
    expect(localStorage.getItem('historian_trends_1')).not.toBeNull();
  });
});
