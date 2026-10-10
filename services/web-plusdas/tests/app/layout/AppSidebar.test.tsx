// @vitest-environment jsdom
import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { AppSidebar } from '@/app/layout/AppSidebar';

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

describe('AppSidebar', () => {
  it('lists Simulation between AI Tasks and Optimization for engineers', () => {
    role.current = 'engineer';
    render(
      <MemoryRouter>
        <AppSidebar />
      </MemoryRouter>,
    );
    const titles = navTitles();
    const simulation = titles.indexOf('Simulation');
    expect(simulation).toBeGreaterThan(-1);
    expect(titles[simulation - 1]).toBe('AI Tasks');
    expect(titles[simulation + 1]).toBe('Optimization');
  });

  it('opens Simulation in this tab, and in a new tab only from its own button', () => {
    role.current = 'engineer';
    render(
      <MemoryRouter>
        <AppSidebar />
      </MemoryRouter>,
    );
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
    render(
      <MemoryRouter>
        <AppSidebar />
      </MemoryRouter>,
    );
    const titles = navTitles();
    const optimization = titles.indexOf('Optimization');
    expect(titles[optimization - 1]).toBe('Simulation');
    expect(titles[optimization + 1]).toBe('Notes');
    expect(screen.getByRole('link', { name: 'Optimization' }).getAttribute('href')).toBe('/optimization');
  });

  it('hides Optimization from monitors', () => {
    role.current = 'monitor';
    render(
      <MemoryRouter>
        <AppSidebar />
      </MemoryRouter>,
    );
    expect(navTitles()).not.toContain('Optimization');
  });

  it('hides Simulation from monitors', () => {
    role.current = 'monitor';
    render(
      <MemoryRouter>
        <AppSidebar />
      </MemoryRouter>,
    );
    expect(navTitles()).not.toContain('Simulation');
  });
});
