// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { alarmsApi } from '@/api';
import type { ActiveAlarmsSummaryRecord } from '@/api/types/alarms';
import { AppSidebar } from '@/app/layout/AppSidebar';
import { stubViewport } from '../../shared/hooks/viewportStub';

const role = vi.hoisted(() => ({ current: 'engineer' }));
vi.mock('@/shared/contexts/auth', () => ({
  useAuth: () => ({ user: { id: 'u1', name: 'Test', email: 't@example.com', role: role.current }, logout: () => {} }),
}));

function navTitles(): string[] {
  // The pages' own links (the "open in a new tab" buttons have no text).
  return screen
    .getAllByRole('link')
    .map((link) => link.textContent?.trim() ?? '')
    .filter((title) => title !== '');
}

const NOTHING_ACTIVE: ActiveAlarmsSummaryRecord = { high_count: 0, medium_count: 0, low_count: 0, sites: [] };

beforeEach(() => {
  localStorage.clear(); // the laptop column remembers being collapsed
  vi.restoreAllMocks();
  vi.spyOn(alarmsApi, 'getActiveSummary').mockResolvedValue(NOTHING_ACTIVE);
});

function renderSidebar() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <AppSidebar />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const alarmsLink = () => screen.getByRole('link', { name: 'System alarms' });

describe('AppSidebar', () => {
  it('lists Simulation between AI Tasks and Optimization for engineers', () => {
    role.current = 'engineer';
    renderSidebar();
    const titles = navTitles();
    const simulation = titles.indexOf('Simulation');
    expect(simulation).toBeGreaterThan(-1);
    expect(titles[simulation - 1]).toBe('AI Tasks');
    expect(titles[simulation + 1]).toBe('Optimization');
  });

  it('opens Simulation in this tab, and in a new tab only from its own button', () => {
    role.current = 'engineer';
    renderSidebar();
    const simulation = screen.getByRole('link', { name: 'Simulation' });
    expect(simulation.getAttribute('href')).toBe('/simulation');
    expect(simulation.getAttribute('target')).toBeNull();
    const newTab = screen.getByRole('link', { name: 'Open Simulation in a new tab' });
    expect(newTab.getAttribute('href')).toBe('/simulation');
    expect(newTab.getAttribute('target')).toBe('_blank');
    expect(newTab.getAttribute('rel')).toContain('noopener');
    expect(screen.queryByRole('link', { name: 'Open Sites in a new tab' })).toBeNull();
  });

  it('lists Optimization between Simulation and Notes, linking to its page', () => {
    role.current = 'engineer';
    renderSidebar();
    const titles = navTitles();
    const optimization = titles.indexOf('Optimization');
    expect(titles[optimization - 1]).toBe('Simulation');
    expect(titles[optimization + 1]).toBe('Notes');
    expect(screen.getByRole('link', { name: 'Optimization' }).getAttribute('href')).toBe('/optimization');
  });

  it('hides Optimization from monitors', () => {
    role.current = 'monitor';
    renderSidebar();
    expect(navTitles()).not.toContain('Optimization');
  });

  it('hides Simulation from monitors', () => {
    role.current = 'monitor';
    renderSidebar();
    expect(navTitles()).not.toContain('Simulation');
  });

  it('lists Devices right under Sites, active on a device page too', () => {
    role.current = 'monitor';
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={['/devices/5']}>
          <AppSidebar />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    const titles = navTitles();
    expect(titles[titles.indexOf('Sites') + 1]).toBe('Devices');
    const devices = screen.getByRole('link', { name: 'Devices' });
    expect(devices.getAttribute('href')).toBe('/site-devices');
    expect(devices.className).toMatch(/bg-sidebar-primary/);
    expect(screen.getByRole('link', { name: 'Sites' }).className).not.toMatch(/bg-sidebar-primary/);
  });

  describe('per breakpoint', () => {
    it('is a full column on a laptop, and collapses to icons it names', () => {
      role.current = 'engineer';
      stubViewport(1366);
      renderSidebar();
      expect(navTitles()).toContain('Sites');
      screen.getByRole('button', { name: 'Collapse navigation' }).click();
      return waitFor(() => {
        expect(navTitles()).not.toContain('Sites');
        expect(screen.getByRole('link', { name: 'Sites' }).getAttribute('title')).toBe('Sites');
      });
    });

    it('is an icon rail on a tablet whose chevron opens the full navigation in a drawer', async () => {
      role.current = 'engineer';
      stubViewport(1024);
      renderSidebar();
      expect(navTitles()).not.toContain('Sites');
      expect(screen.getByRole('link', { name: 'Sites' })).toBeTruthy();
      screen.getByRole('button', { name: 'Expand navigation' }).click();
      const drawer = await screen.findByRole('dialog', { name: 'Navigation' });
      expect(drawer.textContent).toContain('Sites');
    });

    it('renders nothing on a phone (the top bar holds the menu)', () => {
      role.current = 'engineer';
      stubViewport(390);
      const { container } = renderSidebar();
      expect(container.innerHTML).toBe('');
    });
  });

  describe('System alarms bell', () => {
    it('stays plain while nothing is active', async () => {
      renderSidebar();
      await waitFor(() => expect(alarmsApi.getActiveSummary).toHaveBeenCalled());
      expect(alarmsLink().getAttribute('data-alarm-severity')).toBe('none');
      expect(alarmsLink().getAttribute('title')).toBeNull();
      expect(alarmsLink().querySelector('svg')?.getAttribute('class')).not.toMatch(/text-alarm-/);
    });

    it('rings red while any site has an active HIGH alarm, whatever else is active', async () => {
      vi.spyOn(alarmsApi, 'getActiveSummary').mockResolvedValue({
        high_count: 1,
        medium_count: 2,
        low_count: 3,
        sites: [
          { site_id: 1, high_count: 1, medium_count: 0, low_count: 3 },
          { site_id: 2, high_count: 0, medium_count: 2, low_count: 0 },
        ],
      });
      renderSidebar();
      await waitFor(() => expect(alarmsLink().getAttribute('data-alarm-severity')).toBe('HIGH'));
      expect(alarmsLink().querySelector('svg')?.getAttribute('class')).toMatch(/text-alarm-high/);
      expect(alarmsLink().getAttribute('title')).toBe('1 high, 2 medium, 3 low active');
    });

    it('rings amber while MEDIUM is the worst active severity', async () => {
      vi.spyOn(alarmsApi, 'getActiveSummary').mockResolvedValue({
        high_count: 0,
        medium_count: 1,
        low_count: 0,
        sites: [{ site_id: 2, high_count: 0, medium_count: 1, low_count: 0 }],
      });
      renderSidebar();
      await waitFor(() => expect(alarmsLink().getAttribute('data-alarm-severity')).toBe('MEDIUM'));
      expect(alarmsLink().querySelector('svg')?.getAttribute('class')).toMatch(/text-alarm-medium/);
      expect(alarmsLink().getAttribute('title')).toBe('1 medium active');
    });

    it('rings blue while only LOW alarms are active', async () => {
      vi.spyOn(alarmsApi, 'getActiveSummary').mockResolvedValue({
        high_count: 0,
        medium_count: 0,
        low_count: 2,
        sites: [{ site_id: 2, high_count: 0, medium_count: 0, low_count: 2 }],
      });
      renderSidebar();
      await waitFor(() => expect(alarmsLink().getAttribute('data-alarm-severity')).toBe('LOW'));
      expect(alarmsLink().querySelector('svg')?.getAttribute('class')).toMatch(/text-alarm-low/);
      expect(alarmsLink().getAttribute('title')).toBe('2 low active');
    });
  });
});
