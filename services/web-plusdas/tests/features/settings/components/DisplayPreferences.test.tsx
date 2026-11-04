// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { meApi } from '@/api/me';
import type { Preference } from '@/api/types/me';
import { ThemeProvider } from '@/shared/components/theme-provider';
import { DisplayPreferences } from '@/features/settings/components/DisplayPreferences';

const saved = (key: string, value: unknown): Preference => ({ key, value, updated_at: '2026-11-01T00:00:00Z' } as Preference);

function renderWith(preferences: Preference[]) {
  vi.spyOn(meApi, 'listPreferences').mockResolvedValue(preferences);
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <ThemeProvider defaultTheme="dark" storageKey="vite-ui-theme"><DisplayPreferences /></ThemeProvider>
    </QueryClientProvider>,
  );
}

const isOn = (name: string) => screen.getByRole('switch', { name }).getAttribute('aria-checked') === 'true';

beforeEach(() => {
  window.localStorage.clear();
  vi.spyOn(meApi, 'putPreference').mockImplementation(async (key, value) => saved(key, value));
});

afterEach(() => vi.restoreAllMocks());

describe('DisplayPreferences', () => {
  it('starts dark with times in the site zone for a user who never chose', async () => {
    renderWith([]);
    await waitFor(() => expect(meApi.listPreferences).toHaveBeenCalled());
    expect(isOn('Dark mode')).toBe(true);
    expect(isOn('Show times in my time zone')).toBe(false);
  });

  it("shows the user's saved choices", async () => {
    renderWith([saved('theme', 'light'), saved('time-display', 'browser')]);
    await waitFor(() => expect(isOn('Dark mode')).toBe(false));
    expect(isOn('Show times in my time zone')).toBe(true);
  });

  it('saves each change to the account', async () => {
    renderWith([]);
    await waitFor(() => expect(meApi.listPreferences).toHaveBeenCalled());
    fireEvent.click(screen.getByRole('switch', { name: 'Dark mode' }));
    fireEvent.click(screen.getByRole('switch', { name: 'Show times in my time zone' }));
    await waitFor(() => expect(meApi.putPreference).toHaveBeenCalledWith('theme', 'light'));
    await waitFor(() => expect(meApi.putPreference).toHaveBeenCalledWith('time-display', 'browser'));
    expect(document.documentElement.classList.contains('light')).toBe(true);
  });
});
