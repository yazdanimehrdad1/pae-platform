import React, { useState, useEffect } from "react";
import { Plus, Edit2, Trash2, X, Save, FileText } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import {
  loadNotesFromStorage,
  addNote,
  updateNote,
  deleteNote,
  type Note,
} from "@/lib/notesStorage";
import { cn } from "@/lib/utils";

interface NotesProps {
  className?: string;
  maxHeight?: string;
}

export const Notes: React.FC<NotesProps> = ({
  className,
  maxHeight = "100%"
}) => {
  const [notes, setNotes] = useState<Note[]>([]);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editContent, setEditContent] = useState("");
  const [newNoteContent, setNewNoteContent] = useState("");
  const [isAdding, setIsAdding] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setNotes(loadNotesFromStorage());
  }, []);

  const handleAddNote = () => {
    if (!newNoteContent.trim()) {
      return;
    }

    try {
      addNote(newNoteContent);
      setNotes(loadNotesFromStorage());
      setNewNoteContent("");
      setIsAdding(false);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add note");
    }
  };

  const handleStartEdit = (note: Note) => {
    setEditingId(note.id);
    setEditContent(note.content);
    setError(null);
  };

  const handleSaveEdit = () => {
    if (!editingId || !editContent.trim()) {
      return;
    }

    const updated = updateNote(editingId, editContent);
    if (updated) {
      setNotes(loadNotesFromStorage());
      setEditingId(null);
      setEditContent("");
      setError(null);
    } else {
      setError("Failed to update note");
    }
  };

  const handleCancelEdit = () => {
    setEditingId(null);
    setEditContent("");
    setError(null);
  };

  const handleDelete = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    e.preventDefault();

    if (window.confirm("Are you sure you want to delete this note?")) {
      const success = deleteNote(id);
      if (success) {
        setNotes(loadNotesFromStorage());
        if (editingId === id) {
          setEditingId(null);
          setEditContent("");
        }
        setError(null);
      } else {
        setError("Failed to delete note");
      }
    }
  };

  const canAddMore = notes.length < 10;

  return (
    <div className={cn("flex flex-col h-full", className)} style={{ maxHeight }}>
      <div className="flex items-center gap-2 mb-4 flex-shrink-0">
        <FileText className="w-4 h-4 text-muted-foreground" />
        <h3 className="text-sm font-semibold text-foreground uppercase tracking-wider">
          Notes
        </h3>
        <span className="text-xs text-muted-foreground ml-auto">
          {notes.length}/10
        </span>
      </div>

      {error && (
        <div className="mb-4 p-3 bg-destructive/10 border border-destructive/20 rounded-lg text-sm text-destructive flex-shrink-0">
          {error}
        </div>
      )}

      <div className="flex-1 overflow-y-auto pr-2 space-y-3" style={{
        scrollbarWidth: "thin",
        scrollbarColor: "hsl(var(--border)) transparent"
      }}>
        {isAdding ? (
          <div className="bg-card border border-border rounded-lg p-4 space-y-3">
            <Textarea
              placeholder="Enter your note..."
              value={newNoteContent}
              onChange={(e) => setNewNoteContent(e.target.value)}
              className="min-h-[100px] resize-none"
              autoFocus
            />
            <div className="flex gap-2 justify-end">
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  setIsAdding(false);
                  setNewNoteContent("");
                  setError(null);
                }}
              >
                <X className="w-4 h-4 mr-1" />
                Cancel
              </Button>
              <Button
                size="sm"
                onClick={handleAddNote}
                disabled={!newNoteContent.trim()}
              >
                <Save className="w-4 h-4 mr-1" />
                Save
              </Button>
            </div>
          </div>
        ) : (
          canAddMore && (
            <Button
              variant="outline"
              className="w-full border-dashed"
              onClick={() => setIsAdding(true)}
            >
              <Plus className="w-4 h-4 mr-2" />
              Add Note
            </Button>
          )
        )}

        {notes.length === 0 && !isAdding && (
          <div className="bg-muted/30 rounded-lg p-8 border border-dashed border-border text-center">
            <FileText className="w-8 h-8 mx-auto mb-2 text-muted-foreground/50" />
            <p className="text-sm text-muted-foreground">
              No notes yet. Click "Add Note" to create your first note.
            </p>
          </div>
        )}

        {notes.map((note) => (
          <div
            key={note.id}
            className="bg-card border border-border rounded-lg p-4 space-y-3 group hover:border-primary/50 transition-colors"
          >
            {editingId === note.id ? (
              <>
                <Textarea
                  value={editContent}
                  onChange={(e) => setEditContent(e.target.value)}
                  className="min-h-[100px] resize-none"
                  autoFocus
                />
                <div className="flex gap-2 justify-end">
                  <Button variant="outline" size="sm" onClick={handleCancelEdit}>
                    <X className="w-4 h-4 mr-1" />
                    Cancel
                  </Button>
                  <Button size="sm" onClick={handleSaveEdit} disabled={!editContent.trim()}>
                    <Save className="w-4 h-4 mr-1" />
                    Save
                  </Button>
                </div>
              </>
            ) : (
              <>
                <div className="text-sm text-foreground whitespace-pre-wrap">
                  {note.content}
                </div>
                <div className="flex items-center justify-between pt-2 border-t border-border">
                  <span className="text-xs text-muted-foreground">
                    {new Date(note.updatedAt).toLocaleDateString()}{" "}
                    {new Date(note.updatedAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </span>
                  <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity" onClick={(e) => e.stopPropagation()}>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-7 w-7 p-0"
                      onClick={(e) => { e.stopPropagation(); handleStartEdit(note); }}
                      title="Edit note"
                      type="button"
                    >
                      <Edit2 className="w-3.5 h-3.5" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-7 w-7 p-0 text-destructive hover:text-destructive"
                      onClick={(e) => handleDelete(note.id, e)}
                      title="Delete note"
                      type="button"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </Button>
                  </div>
                </div>
              </>
            )}
          </div>
        ))}

        {!canAddMore && !isAdding && (
          <div className="text-center text-xs text-muted-foreground p-2">
            Maximum of 10 notes reached. Delete a note to add more.
          </div>
        )}
      </div>
    </div>
  );
};
