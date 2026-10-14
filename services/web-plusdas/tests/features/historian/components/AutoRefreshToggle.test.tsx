// @vitest-environment jsdom
import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { AutoRefreshToggle } from '@/features/historian/components/AutoRefreshToggle';

describe('AutoRefreshToggle', () => {
  it('shows off and turns it on', () => {
    const onChange = vi.fn();
    render(<AutoRefreshToggle enabled={false} onChange={onChange} />);
    const button = screen.getByRole('button', { name: 'Auto refresh: off' });
    expect(button.getAttribute('aria-pressed')).toBe('false');
    fireEvent.click(button);
    expect(onChange).toHaveBeenCalledWith(true);
  });

  it('shows how often while on, and turns it off', () => {
    const onChange = vi.fn();
    render(<AutoRefreshToggle enabled onChange={onChange} />);
    const button = screen.getByRole('button', { name: 'Auto refresh: every 1 min' });
    expect(button.getAttribute('aria-pressed')).toBe('true');
    fireEvent.click(button);
    expect(onChange).toHaveBeenCalledWith(false);
  });
});
