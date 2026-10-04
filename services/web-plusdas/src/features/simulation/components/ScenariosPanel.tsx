import { FlaskConical } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

// Placeholder: mock scenarios (faults, status changes, ...) the user will define and inject into
// the simulation. powerflow has no endpoint for them yet.
export function ScenariosPanel() {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <FlaskConical className="w-5 h-5 text-primary" />
          Scenarios
          <Badge variant="outline">Coming soon</Badge>
        </CardTitle>
        <CardDescription>
          Define mock scenarios to play into the simulation, such as an asset fault, a status change or a
          communication loss, and watch how the site and the EMS respond.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <p className="text-sm text-muted-foreground">Nothing to configure yet.</p>
      </CardContent>
    </Card>
  );
}
