export interface Note {
  id: string;
  content: string;
  createdAt: string;
  updatedAt: string;
}

const STORAGE_KEY = "user_notes";
const MAX_NOTES = 10;

/**
 * Load notes from localStorage
 */
export function loadNotesFromStorage(): Note[] {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    
    if (!stored) {
      return [];
    }
    
    const notes = JSON.parse(stored) as Note[];
    
    // Validate that we have an array
    if (!Array.isArray(notes)) {
      return [];
    }
    
    // Sort by updatedAt (most recent first)
    return notes.sort((a, b) => 
      new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime()
    );
  } catch (error) {
    console.error('Error loading notes from storage:', error);
    return [];
  }
}

/**
 * Save notes to localStorage
 */
export function saveNotesToStorage(notes: Note[]): void {
  try {
    // Limit to MAX_NOTES
    const limitedNotes = notes.slice(0, MAX_NOTES);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(limitedNotes));
  } catch (error) {
    console.error('Error saving notes to storage:', error);
    // Handle quota exceeded error
    if (error instanceof DOMException && error.name === 'QuotaExceededError') {
      console.warn('localStorage quota exceeded. Consider cleaning up old data.');
    }
  }
}

/**
 * Add a new note
 */
export function addNote(content: string): Note {
  const notes = loadNotesFromStorage();
  
  // Check if we've reached the limit
  if (notes.length >= MAX_NOTES) {
    throw new Error(`Maximum of ${MAX_NOTES} notes allowed. Please delete a note first.`);
  }
  
  const newNote: Note = {
    id: `note-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
    content: content.trim(),
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
  };
  
  const updatedNotes = [newNote, ...notes];
  saveNotesToStorage(updatedNotes);
  
  return newNote;
}

/**
 * Update an existing note
 */
export function updateNote(id: string, content: string): Note | null {
  const notes = loadNotesFromStorage();
  const noteIndex = notes.findIndex(note => note.id === id);
  
  if (noteIndex === -1) {
    return null;
  }
  
  const updatedNote: Note = {
    ...notes[noteIndex],
    content: content.trim(),
    updatedAt: new Date().toISOString(),
  };
  
  notes[noteIndex] = updatedNote;
  saveNotesToStorage(notes);
  
  return updatedNote;
}

/**
 * Delete a note
 */
export function deleteNote(id: string): boolean {
  const notes = loadNotesFromStorage();
  const filteredNotes = notes.filter(note => note.id !== id);
  
  if (filteredNotes.length === notes.length) {
    return false; // Note not found
  }
  
  saveNotesToStorage(filteredNotes);
  return true;
}

/**
 * Clear all notes
 */
export function clearAllNotes(): void {
  localStorage.removeItem(STORAGE_KEY);
}

