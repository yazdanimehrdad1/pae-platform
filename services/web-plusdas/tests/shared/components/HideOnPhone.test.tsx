// @vitest-environment jsdom
import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { EDIT_ON_LARGER_SCREEN, HideOnPhone } from '@/shared/components/HideOnPhone';
import { stubViewport } from '../hooks/viewportStub';

describe('HideOnPhone', () => {
  it.each([768, 1366])('shows its children at %ipx', (width) => {
    stubViewport(width);
    render(<HideOnPhone note={EDIT_ON_LARGER_SCREEN}><button>Edit</button></HideOnPhone>);
    expect(screen.getByRole('button', { name: 'Edit' })).toBeTruthy();
    expect(screen.queryByText(EDIT_ON_LARGER_SCREEN)).toBeNull();
  });

  it('shows the note instead on a phone', () => {
    stubViewport(390);
    render(<HideOnPhone note={EDIT_ON_LARGER_SCREEN}><button>Edit</button></HideOnPhone>);
    expect(screen.queryByRole('button', { name: 'Edit' })).toBeNull();
    expect(screen.getByText(EDIT_ON_LARGER_SCREEN)).toBeTruthy();
  });

  it('shows nothing on a phone without a note', () => {
    stubViewport(390);
    const { container } = render(<HideOnPhone><button>Edit</button></HideOnPhone>);
    expect(container.innerHTML).toBe('');
  });
});
