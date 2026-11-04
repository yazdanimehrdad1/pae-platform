import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { KeyRound } from "lucide-react";
import { authApi } from "@/api";
import { getErrorMessage } from "@/api/client";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuth } from "@/shared/contexts/auth";
import { toast } from "@/shared/hooks/use-toast";

const MIN_PASSWORD_LENGTH = 10;

// The logged-in user's own password. Changing it logs out their other browsers; this one stays.
export function ChangePasswordCard() {
  const { user } = useAuth();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [repeatPassword, setRepeatPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  const change = useMutation({
    mutationFn: () => authApi.changePassword({ current_password: currentPassword, new_password: newPassword }),
    onSuccess: () => {
      setCurrentPassword("");
      setNewPassword("");
      setRepeatPassword("");
      toast({ title: "Password changed", description: "Your other browsers and devices were logged out." });
    },
    onError: (changeError) => setError(getErrorMessage(changeError)),
  });

  const mismatch = repeatPassword !== "" && repeatPassword !== newPassword;
  const canSubmit = currentPassword !== "" && newPassword.length >= MIN_PASSWORD_LENGTH && newPassword === repeatPassword;

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-gradient-primary rounded-lg flex items-center justify-center">
            <KeyRound className="w-5 h-5 text-white" />
          </div>
          <div>
            <CardTitle>Your account</CardTitle>
            <CardDescription>
              {user ? `Signed in as ${user.email}.` : null} Change your password here.
            </CardDescription>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <form className="grid gap-4 sm:max-w-sm" onSubmit={event => { event.preventDefault(); setError(null); change.mutate(); }}>
          <div className="space-y-1">
            <Label htmlFor="current-password">Current password</Label>
            <Input id="current-password" type="password" autoComplete="current-password" value={currentPassword} onChange={event => setCurrentPassword(event.target.value)} />
          </div>
          <div className="space-y-1">
            <Label htmlFor="new-password">New password</Label>
            <Input id="new-password" type="password" autoComplete="new-password" value={newPassword} onChange={event => setNewPassword(event.target.value)} />
            <p className="text-xs text-muted-foreground">At least {MIN_PASSWORD_LENGTH} characters.</p>
          </div>
          <div className="space-y-1">
            <Label htmlFor="repeat-password">Repeat the new password</Label>
            <Input id="repeat-password" type="password" autoComplete="new-password" value={repeatPassword} onChange={event => setRepeatPassword(event.target.value)} />
            {mismatch && <p className="text-xs text-destructive">The passwords don't match.</p>}
          </div>
          {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
          <div>
            <Button type="submit" disabled={!canSubmit || change.isPending}>{change.isPending ? "Saving..." : "Change password"}</Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}
