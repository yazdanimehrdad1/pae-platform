import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { meApi } from "@/api/me";
import type { SavedNote } from "@/api/types/me";
import type { Note } from "../types";

export const NOTES_QUERY_KEY = ["me", "notes"] as const;
export const MAX_NOTES = 10;

function toNote(saved: SavedNote): Note {
  return { id: String(saved.id), content: saved.content, createdAt: saved.created_at, updatedAt: saved.updated_at };
}

// The user's notes, kept by intelli-gateway (newest first), so they follow the user to any browser.
export function useNotes() {
  const queryClient = useQueryClient();
  const notesQuery = useQuery({
    queryKey: NOTES_QUERY_KEY,
    queryFn: async () => (await meApi.listNotes()).map(toNote),
  });
  const refresh = () => queryClient.invalidateQueries({ queryKey: NOTES_QUERY_KEY });

  const addNote = useMutation({
    mutationFn: (content: string) => meApi.createNote({ content: content.trim() }),
    onSuccess: refresh,
  });
  const updateNote = useMutation({
    mutationFn: ({ id, content }: { id: string; content: string }) => meApi.updateNote(Number(id), content.trim()),
    onSuccess: refresh,
  });
  const deleteNote = useMutation({
    mutationFn: (id: string) => meApi.deleteNote(Number(id)),
    onSuccess: refresh,
  });

  return { notes: notesQuery.data ?? [], isLoading: notesQuery.isLoading, addNote, updateNote, deleteNote };
}
