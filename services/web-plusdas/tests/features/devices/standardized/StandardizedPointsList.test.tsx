// @vitest-environment jsdom
import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import type { DevicePoint } from '@/api/types/devicePoints';
import { StandardizedPointsList } from '@/features/devices/standardized/StandardizedPointsList';

const sources = [{ id: 14, name: 'W', category: 'NATIVE', unit: 'W' }] as unknown as DevicePoint[];
const linked = {
  id: 57, name: 'BESS_ACTIVE_POWER', category: 'STANDARDIZED', source_point_id: 14, unit: 'kW', scale_factor: 0.001,
} as unknown as DevicePoint;
const unlinked = { id: 58, name: 'BESS_STATUS', category: 'STANDARDIZED' } as unknown as DevicePoint;

function renderList() {
  const onLink = vi.fn();
  const onUnlink = vi.fn();
  render(<StandardizedPointsList points={[linked, unlinked]} sources={sources} onLink={onLink} onUnlink={onUnlink} />);
  return { onLink, onUnlink };
}

describe('StandardizedPointsList', () => {
  it('shows each point with its link, or that it is not linked', () => {
    renderList();
    expect(screen.getByText('W × 0.001 → kW')).toBeTruthy();
    expect(screen.getByText('not linked')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Link BESS_STATUS' })).toBeTruthy();
  });

  it('asks for confirmation, naming the point and its source, before unlinking', () => {
    const { onUnlink } = renderList();
    fireEvent.click(screen.getByRole('button', { name: 'Unlink BESS_ACTIVE_POWER' }));

    expect(screen.getByText(/Are you sure you want to unlink standardized point "BESS_ACTIVE_POWER" from "W"\?/)).toBeTruthy();
    expect(onUnlink).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole('button', { name: 'Unlink' }));
    expect(onUnlink).toHaveBeenCalledWith(linked);
  });

  it('does not unlink when the confirmation is cancelled', () => {
    const { onUnlink } = renderList();
    fireEvent.click(screen.getByRole('button', { name: 'Unlink BESS_ACTIVE_POWER' }));
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
    expect(onUnlink).not.toHaveBeenCalled();
  });
});
