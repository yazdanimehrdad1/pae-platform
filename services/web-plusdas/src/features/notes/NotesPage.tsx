import { Notes } from "@/shared/components/Notes";

const NotesPage = () => {
  return (
    <div className="p-6 h-full">
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-foreground">Notes</h1>
        <p className="text-muted-foreground mt-1">Keep track of your notes and observations</p>
      </div>

      <div className="bg-card border border-border rounded-lg p-6" style={{ height: "calc(100vh - 180px)" }}>
        <Notes />
      </div>
    </div>
  );
};

export default NotesPage;
