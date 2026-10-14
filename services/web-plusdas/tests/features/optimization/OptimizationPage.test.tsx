// @vitest-environment jsdom
import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import Optimization from '@/features/optimization/OptimizationPage';

describe('Optimization page', () => {
  it('shows its title and that it is coming soon', () => {
    render(<Optimization />);
    expect(screen.getByRole('heading', { name: 'Optimization' })).toBeTruthy();
    expect(screen.getByText('Coming soon')).toBeTruthy();
  });
});
