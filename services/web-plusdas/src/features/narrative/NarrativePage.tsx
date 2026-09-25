import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  PlayCircle, SkipBack, SkipForward, Rewind, FastForward,
  Calendar, Clock, Activity, AlertTriangle, Zap, TrendingUp, FileText, Download
} from "lucide-react";

const suggestedFeatures = [
  { icon: PlayCircle, title: "Event Playback", description: "Replay historical events in chronological order with adjustable speed controls", status: "planned" },
  { icon: Calendar, title: "Timeline Navigation", description: "Visual timeline with zoom and pan capabilities to navigate through historical data", status: "planned" },
  { icon: AlertTriangle, title: "Incident Reconstruction", description: "Step-by-step reconstruction of fault events showing cause and effect chains", status: "planned" },
  { icon: Activity, title: "Live Annotations", description: "Add notes and annotations to specific points in time for documentation", status: "planned" },
  { icon: TrendingUp, title: "Trend Analysis", description: "Overlay trend data during playback to correlate events with measurements", status: "planned" },
  { icon: FileText, title: "Report Generation", description: "Auto-generate incident reports from narrative playback sessions", status: "planned" }
];

export default function Narrative() {
  return (
    <div className="h-screen flex flex-col">
      <div className="border-b border-border p-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-foreground">Narrative Mode</h1>
            <p className="text-muted-foreground mt-1">
              Playback and analyze historical events in sequence
            </p>
          </div>
          <div className="flex space-x-2">
            <Button variant="outline" size="sm">
              <Download className="w-4 h-4 mr-2" />
              Export Session
            </Button>
          </div>
        </div>
      </div>

      <div className="border-b border-border p-6 bg-muted/30">
        <Card className="max-w-2xl mx-auto">
          <CardContent className="p-6">
            <div className="flex flex-col items-center space-y-4">
              <div className="text-center">
                <p className="text-sm text-muted-foreground">Playback Preview</p>
                <p className="text-2xl font-mono font-bold">00:00:00.000</p>
              </div>
              <div className="flex items-center space-x-2">
                <Button variant="outline" size="sm" disabled><SkipBack className="w-4 h-4" /></Button>
                <Button variant="outline" size="sm" disabled><Rewind className="w-4 h-4" /></Button>
                <Button size="lg" className="bg-gradient-primary" disabled><PlayCircle className="w-6 h-6" /></Button>
                <Button variant="outline" size="sm" disabled><FastForward className="w-4 h-4" /></Button>
                <Button variant="outline" size="sm" disabled><SkipForward className="w-4 h-4" /></Button>
              </div>
              <div className="w-full bg-muted rounded-full h-2">
                <div className="bg-primary h-2 rounded-full w-0"></div>
              </div>
              <p className="text-xs text-muted-foreground">
                Select a time range to begin narrative playback
              </p>
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="flex-1 overflow-auto p-6">
        <div className="mb-6">
          <h2 className="text-xl font-semibold mb-2">Planned Features</h2>
          <p className="text-muted-foreground">
            The following capabilities are planned for the Narrative Mode
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {suggestedFeatures.map((feature, index) => {
            const Icon = feature.icon;
            return (
              <Card key={index} className="hover:shadow-lg transition-shadow">
                <CardHeader>
                  <div className="flex items-start justify-between">
                    <div className="w-12 h-12 bg-gradient-primary rounded-lg flex items-center justify-center">
                      <Icon className="w-6 h-6 text-white" />
                    </div>
                    <Badge variant="outline" className="text-xs">{feature.status}</Badge>
                  </div>
                  <CardTitle className="text-lg mt-4">{feature.title}</CardTitle>
                  <CardDescription>{feature.description}</CardDescription>
                </CardHeader>
              </Card>
            );
          })}
        </div>

        <div className="mt-8">
          <h2 className="text-xl font-semibold mb-4">Use Cases</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Card className="bg-muted/30">
              <CardContent className="p-4">
                <div className="flex items-start space-x-3">
                  <Zap className="w-5 h-5 text-warning mt-1" />
                  <div>
                    <h3 className="font-medium">Fault Analysis</h3>
                    <p className="text-sm text-muted-foreground">
                      Replay fault events to understand the sequence of operations and identify root causes
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>
            <Card className="bg-muted/30">
              <CardContent className="p-4">
                <div className="flex items-start space-x-3">
                  <Clock className="w-5 h-5 text-primary mt-1" />
                  <div>
                    <h3 className="font-medium">Operational Review</h3>
                    <p className="text-sm text-muted-foreground">
                      Review operator actions and system responses during specific time periods
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </div>
  );
}
