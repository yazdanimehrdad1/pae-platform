// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { authApi } from '@/api/me';
import { AuthProvider } from '@/shared/contexts/auth';
import Login from '@/features/auth/LoginPage';

function renderLogin(from?: string) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <MemoryRouter initialEntries={[{ pathname: '/login', state: from ? { from } : undefined }]}>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route path="/sites" element={<p>sites page</p>} />
            <Route path="/historian" element={<p>historian page</p>} />
          </Routes>
        </MemoryRouter>
      </AuthProvider>
    </QueryClientProvider>,
  );
}

function submit(email: string, password: string) {
  fireEvent.change(screen.getByLabelText('Email'), { target: { value: email } });
  fireEvent.change(screen.getByLabelText('Password'), { target: { value: password } });
  fireEvent.click(screen.getByRole('button', { name: 'Sign In' }));
}

afterEach(() => vi.restoreAllMocks());

describe('Login page', () => {
  it('asks for an email address and password only (the role comes with the account)', async () => {
    vi.spyOn(authApi, 'me').mockRejectedValue({ status: 401 });
    renderLogin();
    expect(await screen.findByLabelText('Email')).toBeTruthy();
    expect(screen.queryByText(/select your role/i)).toBeNull();
    expect(screen.queryByText(/any password/i)).toBeNull();
  });

  it('says so on a wrong password and clears it', async () => {
    vi.spyOn(authApi, 'me').mockRejectedValue({ status: 401 });
    vi.spyOn(authApi, 'login').mockRejectedValue({ detail: 'wrong email or password', status: 401 });
    renderLogin();
    submit('ana@example.com', 'nope');
    expect((await screen.findByRole('alert')).textContent).toBe('Wrong email or password.');
    expect((screen.getByLabelText('Password') as HTMLInputElement).value).toBe('');
  });

  it('goes back to the page the user was sent here from', async () => {
    vi.spyOn(authApi, 'me').mockRejectedValue({ status: 401 });
    vi.spyOn(authApi, 'login').mockResolvedValue({ id: 1, email: 'ana@example.com', display_name: 'Ana', role: 'engineer' });
    renderLogin('/historian');
    submit(' ana@example.com ', 'right password');
    expect(await screen.findByText('historian page')).toBeTruthy();
    expect(authApi.login).toHaveBeenCalledWith({ email: 'ana@example.com', password: 'right password' });
  });

  it('skips the form when already logged in', async () => {
    vi.spyOn(authApi, 'me').mockResolvedValue({ id: 1, email: 'ana@example.com', display_name: 'Ana', role: 'engineer' });
    renderLogin();
    expect(await screen.findByText('sites page')).toBeTruthy();
  });
});
