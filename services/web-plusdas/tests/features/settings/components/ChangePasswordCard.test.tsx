// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { authApi } from '@/api';
import { AuthProvider } from '@/shared/contexts/auth';
import { ChangePasswordCard } from '@/features/settings/components/ChangePasswordCard';

afterEach(() => vi.restoreAllMocks());

function renderCard() {
  vi.spyOn(authApi, 'me').mockResolvedValue({ id: 2, email: 'ana@example.com', display_name: 'Ana', role: 'engineer' });
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={queryClient}><AuthProvider><ChangePasswordCard /></AuthProvider></QueryClientProvider>);
}

function fill(current: string, next: string, repeat: string) {
  fireEvent.change(screen.getByLabelText('Current password'), { target: { value: current } });
  fireEvent.change(screen.getByLabelText('New password'), { target: { value: next } });
  fireEvent.change(screen.getByLabelText('Repeat the new password'), { target: { value: repeat } });
}

const submit = () => screen.getByRole('button', { name: 'Change password' }) as HTMLButtonElement;

describe('ChangePasswordCard', () => {
  it('needs the new password twice, alike', () => {
    renderCard();
    fill('old password', 'a new password', 'a different one');
    expect(screen.getByText(/passwords don.t match/)).toBeTruthy();
    expect(submit().disabled).toBe(true);
  });

  it('shows the error for a wrong current password, then sends a right one', async () => {
    const change = vi.spyOn(authApi, 'changePassword')
      .mockRejectedValueOnce({ detail: 'the current password is wrong', status: 403 })
      .mockResolvedValueOnce(undefined);
    renderCard();
    fill('wrong password', 'a new password', 'a new password');
    fireEvent.click(submit());
    expect((await screen.findByRole('alert')).textContent).toBe('the current password is wrong');

    fill('old password', 'a new password', 'a new password');
    fireEvent.click(submit());
    await waitFor(() => expect(change).toHaveBeenLastCalledWith({ current_password: 'old password', new_password: 'a new password' }));
    await waitFor(() => expect((screen.getByLabelText('Current password') as HTMLInputElement).value).toBe(''));
  });
});
