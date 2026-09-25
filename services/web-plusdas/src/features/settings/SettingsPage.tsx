import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Users, Settings as SettingsIcon, UserPlus, Palette, Bell, Globe } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";

const Settings = () => {
  return (
    <div className="p-6 space-y-6 h-full flex flex-col">
      <div>
        <h1 className="text-3xl font-bold text-foreground">Settings</h1>
        <p className="text-muted-foreground mt-1">
          Manage your teams and personalize your application experience
        </p>
      </div>

      <div className="flex-1 space-y-6">
        <Card>
          <CardHeader>
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-gradient-primary rounded-lg flex items-center justify-center">
                <Users className="w-5 h-5 text-white" />
              </div>
              <div>
                <CardTitle>Teams Management</CardTitle>
                <CardDescription>
                  Manage your team members and control who can access your shared information and trends
                </CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="bg-muted/30 rounded-lg p-6 border border-dashed border-border text-center">
              <Users className="w-12 h-12 mx-auto mb-4 text-muted-foreground/50" />
              <h3 className="text-lg font-semibold text-foreground mb-2">Team Management</h3>
              <p className="text-sm text-muted-foreground mb-4 max-w-md mx-auto">
                Configure your team members and set permissions for sharing information, trends, and data insights.
              </p>
              <Button variant="outline" disabled>
                <UserPlus className="w-4 h-4 mr-2" />
                Add Team Member
              </Button>
            </div>

            <Separator />

            <div className="space-y-3">
              <h4 className="text-sm font-semibold text-foreground">Coming Soon</h4>
              <ul className="space-y-2 text-sm text-muted-foreground">
                <li className="flex items-start gap-2"><span className="text-primary">•</span><span>Invite team members via email</span></li>
                <li className="flex items-start gap-2"><span className="text-primary">•</span><span>Set role-based permissions (view, edit, share)</span></li>
                <li className="flex items-start gap-2"><span className="text-primary">•</span><span>Share specific trends and reports with team members</span></li>
                <li className="flex items-start gap-2"><span className="text-primary">•</span><span>Manage team access to sites and devices</span></li>
                <li className="flex items-start gap-2"><span className="text-primary">•</span><span>Track team activity and collaboration</span></li>
              </ul>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-gradient-secondary rounded-lg flex items-center justify-center">
                <SettingsIcon className="w-5 h-5 text-white" />
              </div>
              <div>
                <CardTitle>General Settings</CardTitle>
                <CardDescription>
                  Personalize your application to match your preferences and workflow
                </CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="bg-muted/30 rounded-lg p-6 border border-dashed border-border text-center">
              <Palette className="w-12 h-12 mx-auto mb-4 text-muted-foreground/50" />
              <h3 className="text-lg font-semibold text-foreground mb-2">Personalization Options</h3>
              <p className="text-sm text-muted-foreground mb-4 max-w-md mx-auto">
                Customize your application experience with various settings and preferences.
              </p>
            </div>

            <Separator />

            <div className="space-y-4">
              <div className="space-y-3">
                <h4 className="text-sm font-semibold text-foreground flex items-center gap-2">
                  <Palette className="w-4 h-4" />
                  Display & Appearance
                </h4>
                <div className="bg-muted/20 rounded-lg p-4">
                  <p className="text-xs text-muted-foreground">Theme, color scheme, and layout preferences will be available here</p>
                </div>
              </div>

              <Separator />

              <div className="space-y-3">
                <h4 className="text-sm font-semibold text-foreground flex items-center gap-2">
                  <Bell className="w-4 h-4" />
                  Notifications
                </h4>
                <div className="bg-muted/20 rounded-lg p-4">
                  <p className="text-xs text-muted-foreground">Configure notification preferences and alert settings</p>
                </div>
              </div>

              <Separator />

              <div className="space-y-3">
                <h4 className="text-sm font-semibold text-foreground flex items-center gap-2">
                  <Globe className="w-4 h-4" />
                  Language & Region
                </h4>
                <div className="bg-muted/20 rounded-lg p-4">
                  <p className="text-xs text-muted-foreground">Set your preferred language, timezone, and regional settings</p>
                </div>
              </div>

              <Separator />

              <div className="space-y-3">
                <h4 className="text-sm font-semibold text-foreground">Additional Options</h4>
                <ul className="space-y-2 text-sm text-muted-foreground">
                  <li className="flex items-start gap-2"><span className="text-primary">•</span><span>Default dashboard view preferences</span></li>
                  <li className="flex items-start gap-2"><span className="text-primary">•</span><span>Data refresh intervals</span></li>
                  <li className="flex items-start gap-2"><span className="text-primary">•</span><span>Chart and visualization defaults</span></li>
                  <li className="flex items-start gap-2"><span className="text-primary">•</span><span>Export and report preferences</span></li>
                </ul>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default Settings;
