import { Gauge } from "lucide-react";

// Placeholder until the optimizer service exists.
const Optimization = () => {
  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-foreground">Optimization</h1>
      </div>
      <div className="flex flex-col items-center justify-center gap-3 py-24 text-center">
        <div className="w-12 h-12 bg-primary/10 rounded-lg flex items-center justify-center">
          <Gauge className="w-6 h-6 text-primary" />
        </div>
        <p className="text-xl font-semibold">Coming soon</p>
      </div>
    </div>
  );
};

export default Optimization;
