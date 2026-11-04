// @vitest-environment jsdom
import type { ReactNode } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { act, renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { meApi } from '@/api/me';
import type { SavedNote } from '@/api/types/me';
import { useNotes } from '@/features/notes/hooks/useNotes';

const note = (id: number, content: string): SavedNote => ({ id, content, created_at: '2026-11-01T00:00:00Z', updated_at: '2026-11-02T00:00:00Z' });

function render() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const wrapper = ({ children }: { children: ReactNode }) => <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  return renderHook(() => useNotes(), { wrapper });
}

afterEach(() => vi.restoreAllMocks());

describe('useNotes', () => {
  it("lists the user's notes in the UI's shape", async () => {
    vi.spyOn(meApi, 'listNotes').mockResolvedValue([note(4, 'check INV2')]);
    const { result } = render();
    await waitFor(() => expect(result.current.notes).toEqual([
      { id: '4', content: 'check INV2', createdAt: '2026-11-01T00:00:00Z', updatedAt: '2026-11-02T00:00:00Z' },
    ]));
  });

  it('adds, edits and deletes through the API, then reloads the list', async () => {
    const list = vi.spyOn(meApi, 'listNotes').mockResolvedValue([]);
    vi.spyOn(meApi, 'createNote').mockResolvedValue(note(5, 'new'));
    vi.spyOn(meApi, 'updateNote').mockResolvedValue(note(5, 'edited'));
    vi.spyOn(meApi, 'deleteNote').mockResolvedValue(undefined);
    const { result } = render();
    await waitFor(() => expect(list).toHaveBeenCalledTimes(1));

    await act(async () => { await result.current.addNote.mutateAsync('  new  '); });
    await act(async () => { await result.current.updateNote.mutateAsync({ id: '5', content: 'edited ' }); });
    await act(async () => { await result.current.deleteNote.mutateAsync('5'); });

    expect(meApi.createNote).toHaveBeenCalledWith({ content: 'new' });
    expect(meApi.updateNote).toHaveBeenCalledWith(5, 'edited');
    expect(meApi.deleteNote).toHaveBeenCalledWith(5);
    await waitFor(() => expect(list).toHaveBeenCalledTimes(4));
  });
});
