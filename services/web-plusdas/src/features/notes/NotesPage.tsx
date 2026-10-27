import { Notes } from "./components/Notes";

const NotesPage = () => {
  return (
    <div className="flex h-full flex-col p-4 md:p-6">
      <div className="mb-4 md:mb-6">
        <h1 className="text-2xl md:text-2xl md:text-3xl font-bold text-foreground">Notes</h1>
        <p className="text-muted-foreground mt-1">Keep track of your notes and observations</p>
      </div>

      <div className="min-h-[24rem] flex-1 bg-card border border-border rounded-lg p-4 md:p-6">
        <Notes />
      </div>
    </div>
  );
};

export default NotesPage;
