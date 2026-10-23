// @vitest-environment jsdom
import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { SeriesStylePopover } from '@/features/historian/components/SeriesStylePopover';
import { resolveSeriesStyles, type SeriesStyle } from '@/features/historian/lib/seriesStyles';

function openPopover(styles: Record<string, SeriesStyle> | undefined) {
  const onChange = vi.fn();
  const keys = ['7', '9'];
  render(
    <SeriesStylePopover
      keys={keys}
      labels={{ '7': 'BESS1 - Real Power', '9': 'BESS1 - SoC' }}
      resolved={resolveSeriesStyles(keys, styles)}
      styles={styles}
      onChange={onChange}
    />,
  );
  fireEvent.click(screen.getByRole('button', { name: 'Styles' }));
  return onChange;
}

describe('SeriesStylePopover', () => {
  it('sets a colour from the colour input', () => {
    const onChange = openPopover(undefined);
    fireEvent.change(screen.getByLabelText('Colour of BESS1 - SoC'), { target: { value: '#ff0000' } });
    expect(onChange).toHaveBeenCalledWith({ '9': { color: '#ff0000' } });
  });

  it('sets a line style and width, keeping the other changes', () => {
    const onChange = openPopover({ '9': { color: '#ff0000' } });
    const dottedButtons = screen.getAllByRole('radio', { name: 'Dotted' });
    fireEvent.click(dottedButtons[1]);
    expect(onChange).toHaveBeenLastCalledWith({ '9': { color: '#ff0000', dash: 'dotted' } });
    fireEvent.click(screen.getAllByRole('radio', { name: '3 px' })[0]);
    expect(onChange).toHaveBeenLastCalledWith({ '9': { color: '#ff0000' }, '7': { width: 3 } });
  });

  it('resets one signal, and all', () => {
    const onChange = openPopover({ '7': { width: 1 }, '9': { dash: 'dashed' } });
    fireEvent.click(screen.getByRole('button', { name: 'Reset BESS1 - SoC' }));
    expect(onChange).toHaveBeenLastCalledWith({ '7': { width: 1 } });
    fireEvent.click(screen.getByRole('button', { name: 'Reset all' }));
    expect(onChange).toHaveBeenLastCalledWith(undefined);
  });
});
