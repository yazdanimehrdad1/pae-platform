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
  return screen.getAllByRole('link').map((link) => link.textContent?.trim() ?? '');
}

describe('AppSidebar', () => {
  it('lists Simulation between AI Tasks and Notes for engineers', () => {
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
    expect(titles[simulation + 1]).toBe('Notes');
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
