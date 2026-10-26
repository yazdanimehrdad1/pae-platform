// @vitest-environment jsdom
import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { EDIT_ON_LARGER_SCREEN, HideOnPhone } from '@/shared/components/HideOnPhone';

function stubWindowWidth(width: number) {
  vi.stubGlobal('matchMedia', (query: string) => ({
    matches: width >= Number(/min-width: (\d+)px/.exec(query)?.[1] ?? 0),
    media: query,
    addEventListener: () => {},
    removeEventListener: () => {},
  }));
}

describe('HideOnPhone', () => {
  it.each([768, 1366])('shows its children at %ipx', (width) => {
    stubWindowWidth(width);
    render(<HideOnPhone note={EDIT_ON_LARGER_SCREEN}><button>Edit</button></HideOnPhone>);
    expect(screen.getByRole('button', { name: 'Edit' })).toBeTruthy();
    expect(screen.queryByText(EDIT_ON_LARGER_SCREEN)).toBeNull();
  });

  it('shows the note instead on a phone', () => {
    stubWindowWidth(390);
    render(<HideOnPhone note={EDIT_ON_LARGER_SCREEN}><button>Edit</button></HideOnPhone>);
    expect(screen.queryByRole('button', { name: 'Edit' })).toBeNull();
    expect(screen.getByText(EDIT_ON_LARGER_SCREEN)).toBeTruthy();
  });

  it('shows nothing on a phone without a note', () => {
    stubWindowWidth(390);
    const { container } = render(<HideOnPhone><button>Edit</button></HideOnPhone>);
    expect(container.innerHTML).toBe('');
  });
});
