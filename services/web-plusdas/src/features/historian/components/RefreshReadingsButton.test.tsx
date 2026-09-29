// @vitest-environment jsdom
import type { ReactNode } from 'react';
import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { RefreshReadingsButton } from './RefreshReadingsButton';

function renderButton(siteId: string | null) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const wrapper = ({ children }: { children: ReactNode }) => <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  render(<RefreshReadingsButton siteId={siteId} />, { wrapper });
  return queryClient;
}

describe('RefreshReadingsButton', () => {
  it('refetches every historian series of the site', () => {
    const queryClient = renderButton('1001');
    const invalidate = vi.spyOn(queryClient, 'invalidateQueries');

    fireEvent.click(screen.getByRole('button', { name: 'Refresh' }));

    expect(invalidate).toHaveBeenCalledWith({ queryKey: ['historian-series', '1001'] });
  });

  it('is disabled without a site', () => {
    renderButton(null);
    expect((screen.getByRole('button', { name: 'Refresh' }) as HTMLButtonElement).disabled).toBe(true);
  });

  it('spins and is disabled while a series of the site is fetching', async () => {
    const queryClient = renderButton('1001');
    let finish: (value: number[]) => void = () => {};
    void queryClient.fetchQuery({
      queryKey: ['historian-series', '1001', '2', '7', 'preset', '1H'],
      queryFn: () => new Promise<number[]>(resolve => { finish = resolve; }),
    });

    const button = await screen.findByRole('button', { name: 'Refreshing…' });
    expect((button as HTMLButtonElement).disabled).toBe(true);

    finish([]);
    await waitFor(() => expect(screen.getByRole('button', { name: 'Refresh' })).toBeTruthy());
  });

  it('ignores queries of another site', async () => {
    const queryClient = renderButton('1001');
    void queryClient.fetchQuery({
      queryKey: ['historian-series', '2002', '5'],
      queryFn: () => new Promise<number[]>(() => {}),
    });
    await new Promise(resolve => setTimeout(resolve, 10));
    expect((screen.getByRole('button', { name: 'Refresh' }) as HTMLButtonElement).disabled).toBe(false);
  });
});
