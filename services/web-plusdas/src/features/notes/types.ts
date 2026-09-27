// One note in the notes sidebar/page, kept in localStorage (lib/notesStorage.ts).
export interface Note {
  id: string;
  content: string;
  createdAt: string;
  updatedAt: string;
}
