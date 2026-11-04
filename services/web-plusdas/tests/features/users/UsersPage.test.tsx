// @vitest-environment jsdom
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { authApi, usersApi } from '@/api';
import type { MeResponse, UserAccount } from '@/api/types/me';
import { AuthProvider } from '@/shared/contexts/auth';
import UsersPage from '@/features/users/UsersPage';

const ROOT: UserAccount = { id: 1, email: 'root@example.com', display_name: 'Root', role: 'admin', disabled: false, created_at: '2026-11-01T00:00:00Z', last_login_at: null };
const ANA: UserAccount = { id: 2, email: 'ana@example.com', display_name: 'Ana', role: 'engineer', disabled: true, created_at: '2026-11-01T00:00:00Z', last_login_at: '2026-11-02T08:00:00Z' };

beforeAll(() => {
  Element.prototype.hasPointerCapture ??= () => false;
  Element.prototype.releasePointerCapture ??= () => {};
  Element.prototype.scrollIntoView ??= () => {};
});
afterEach(() => vi.restoreAllMocks());

function renderAs(me: MeResponse) {
  vi.spyOn(authApi, 'me').mockResolvedValue(me);
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={queryClient}><AuthProvider><UsersPage /></AuthProvider></QueryClientProvider>);
}

const asRoot = () => renderAs({ id: 1, email: 'root@example.com', display_name: 'Root', role: 'admin' });

describe('UsersPage', () => {
  it('lists every account for an admin, with its role and status', async () => {
    vi.spyOn(usersApi, 'list').mockResolvedValue([ANA, ROOT]);
    asRoot();
    const anaRow = (await screen.findByText('ana@example.com')).closest('tr') as HTMLElement;
    expect(within(anaRow).getByText('Engineer')).toBeTruthy();
    expect(within(anaRow).getByText('Disabled')).toBeTruthy();
    expect(screen.getByText('(you)')).toBeTruthy();
  });

  it('adds an account, once the password is long enough', async () => {
    vi.spyOn(usersApi, 'list').mockResolvedValue([ROOT]);
    const create = vi.spyOn(usersApi, 'create').mockResolvedValue({ ...ANA, id: 3, email: 'bob@example.com', disabled: false });
    asRoot();
    fireEvent.click(await screen.findByRole('button', { name: /Add user/ }));
    fireEvent.change(screen.getByLabelText('Email'), { target: { value: ' Bob@Example.com ' } });
    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'Bob S' } });
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'short' } });
    expect((screen.getByRole('button', { name: 'Save' }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'long enough password' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));
    await waitFor(() => expect(create).toHaveBeenCalledWith({
      email: 'Bob@Example.com', display_name: 'Bob S', role: 'engineer', password: 'long enough password',
    }));
  });

  it('does not let an admin demote or disable their own account', async () => {
    vi.spyOn(usersApi, 'list').mockResolvedValue([ROOT]);
    asRoot();
    fireEvent.click(await screen.findByRole('button', { name: 'Edit root@example.com' }));
    expect(screen.getByRole('combobox', { name: 'Role' }).hasAttribute('disabled')).toBe(true);
    expect(screen.getByRole('switch', { name: 'Disabled' }).hasAttribute('disabled')).toBe(true);
  });

  it('tells a non-admin it is for administrators, and loads nothing', async () => {
    const list = vi.spyOn(usersApi, 'list');
    renderAs({ id: 2, email: 'ana@example.com', display_name: 'Ana', role: 'engineer' });
    expect(await screen.findByText('Only administrators manage accounts.')).toBeTruthy();
    expect(list).not.toHaveBeenCalled();
  });
});
