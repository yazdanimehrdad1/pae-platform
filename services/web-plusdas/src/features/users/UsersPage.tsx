import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { KeyRound, Pencil, UserPlus } from "lucide-react";
import { usersApi } from "@/api";
import { getErrorMessage } from "@/api/client";
import type { UserAccount, UserRole } from "@/api/types/me";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useAuth } from "@/shared/contexts/auth";
import { EDIT_ON_LARGER_SCREEN, HideOnPhone } from "@/shared/components/HideOnPhone";
import { toast } from "@/shared/hooks/use-toast";

// Accounts are created here by an admin (no self-signup); intelli-gateway keeps them. The first
// admin of an environment comes from its secret. Admins can't demote or disable themselves, so
// there is always an admin left (the server refuses it too).

const USERS_QUERY_KEY = ["users"] as const;
const MIN_PASSWORD_LENGTH = 10;
// A Record, so a role added to the contract fails the typecheck until it has a label.
const ROLE_LABELS: Record<UserRole, string> = { engineer: "Engineer", monitor: "Monitor", admin: "Administrator" };
const ROLES = Object.keys(ROLE_LABELS) as UserRole[];

function formatDate(value: string | null): string {
  return value ? new Date(value).toLocaleString([], { dateStyle: "medium", timeStyle: "short" }) : "Never";
}

type AccountDialog = { mode: "add" } | { mode: "edit"; account: UserAccount } | { mode: "password"; account: UserAccount };

export default function UsersPage() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [dialog, setDialog] = useState<AccountDialog | null>(null);
  const { data: accounts = [], isLoading, isError, error } = useQuery({
    queryKey: USERS_QUERY_KEY,
    queryFn: usersApi.list,
    enabled: user?.role === "admin",
  });
  const refresh = () => queryClient.invalidateQueries({ queryKey: USERS_QUERY_KEY });

  if (user?.role !== "admin") {
    return (
      <div className="p-4 md:p-6">
        <h1 className="text-2xl md:text-3xl font-bold">User Management</h1>
        <p className="text-muted-foreground mt-2">Only administrators manage accounts.</p>
      </div>
    );
  }

  return (
    <div className="p-4 md:p-6 space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl md:text-3xl font-bold text-foreground">User Management</h1>
          <p className="text-muted-foreground mt-1">Add the people who use PlusDAS, set their role, and disable an account when they leave.</p>
        </div>
        <HideOnPhone note={EDIT_ON_LARGER_SCREEN}>
          <Button onClick={() => setDialog({ mode: "add" })}><UserPlus className="w-4 h-4 mr-2" />Add user</Button>
        </HideOnPhone>
      </div>

      {isLoading && <p className="text-muted-foreground">Loading accounts...</p>}
      {isError && <p className="text-destructive">Could not load the accounts: {getErrorMessage(error)}</p>}
      {!isLoading && !isError && (
        <div className="overflow-x-auto rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Email</TableHead>
                <TableHead>Name</TableHead>
                <TableHead>Role</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Last login</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {accounts.map(account => (
                <TableRow key={account.id}>
                  <TableCell className="font-medium">{account.email}{String(account.id) === user.id && <span className="text-muted-foreground"> (you)</span>}</TableCell>
                  <TableCell>{account.display_name}</TableCell>
                  <TableCell>{ROLE_LABELS[account.role]}</TableCell>
                  <TableCell>
                    {account.disabled
                      ? <Badge variant="outline" className="text-muted-foreground">Disabled</Badge>
                      : <Badge variant="outline" className="bg-success/10 text-success border-success">Active</Badge>}
                  </TableCell>
                  <TableCell className="whitespace-nowrap">{formatDate(account.last_login_at)}</TableCell>
                  <TableCell className="text-right whitespace-nowrap">
                    <HideOnPhone>
                      <Button variant="ghost" size="sm" aria-label={`Edit ${account.email}`} onClick={() => setDialog({ mode: "edit", account })}>
                        <Pencil className="w-4 h-4" />
                      </Button>
                      <Button variant="ghost" size="sm" aria-label={`Reset the password of ${account.email}`} onClick={() => setDialog({ mode: "password", account })}>
                        <KeyRound className="w-4 h-4" />
                      </Button>
                    </HideOnPhone>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      {dialog?.mode === "add" && <AccountFormDialog onClose={() => setDialog(null)} onSaved={refresh} />}
      {dialog?.mode === "edit" && (
        <AccountFormDialog account={dialog.account} isSelf={String(dialog.account.id) === user.id} onClose={() => setDialog(null)} onSaved={refresh} />
      )}
      {dialog?.mode === "password" && <ResetPasswordDialog account={dialog.account} onClose={() => setDialog(null)} />}
    </div>
  );
}

function AccountFormDialog({ account, isSelf = false, onClose, onSaved }: {
  account?: UserAccount;
  isSelf?: boolean;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [email, setEmail] = useState("");
  const [displayName, setDisplayName] = useState(account?.display_name ?? "");
  const [role, setRole] = useState<UserRole>(account?.role ?? "engineer");
  const [disabled, setDisabled] = useState(account?.disabled ?? false);
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  const save = useMutation({
    mutationFn: () => account
      ? usersApi.update(account.id, { display_name: displayName.trim(), role, disabled })
      : usersApi.create({ email: email.trim(), display_name: displayName.trim(), role, password }),
    onSuccess: (saved) => {
      onSaved();
      toast({ title: account ? "Account updated" : "Account added", description: account ? saved.email : `${saved.email} can log in now.` });
      onClose();
    },
    onError: (saveError) => setError(getErrorMessage(saveError)),
  });

  const isValid = displayName.trim() !== "" && (account || (email.trim() !== "" && password.length >= MIN_PASSWORD_LENGTH));

  return (
    <Dialog open onOpenChange={open => { if (!open) onClose(); }}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>{account ? `Edit ${account.email}` : "Add user"}</DialogTitle>
          <DialogDescription>
            {account ? "Disabling an account logs it out everywhere at once." : "They sign in with this email address; tell them the password, which they can change in Settings."}
          </DialogDescription>
        </DialogHeader>
        <form className="space-y-4" onSubmit={event => { event.preventDefault(); setError(null); save.mutate(); }}>
          {!account && (
            <div className="space-y-1">
              <Label htmlFor="account-email">Email</Label>
              <Input id="account-email" type="email" autoCapitalize="none" autoComplete="off" value={email} onChange={event => setEmail(event.target.value)} />
            </div>
          )}
          <div className="space-y-1">
            <Label htmlFor="account-name">Name</Label>
            <Input id="account-name" value={displayName} onChange={event => setDisplayName(event.target.value)} />
          </div>
          <div className="space-y-1">
            <Label htmlFor="account-role">Role</Label>
            <Select value={role} onValueChange={value => setRole(value as UserRole)} disabled={isSelf}>
              <SelectTrigger id="account-role"><SelectValue /></SelectTrigger>
              <SelectContent>
                {ROLES.map(option => <SelectItem key={option} value={option}>{ROLE_LABELS[option]}</SelectItem>)}
              </SelectContent>
            </Select>
            {isSelf && <p className="text-xs text-muted-foreground">You can't change your own role.</p>}
          </div>
          {account ? (
            <div className="flex items-center justify-between gap-3">
              <Label htmlFor="account-disabled">Disabled</Label>
              <Switch id="account-disabled" checked={disabled} onCheckedChange={setDisabled} disabled={isSelf} />
            </div>
          ) : (
            <div className="space-y-1">
              <Label htmlFor="account-password">Password</Label>
              <Input id="account-password" type="password" autoComplete="new-password" value={password} onChange={event => setPassword(event.target.value)} />
              <p className="text-xs text-muted-foreground">At least {MIN_PASSWORD_LENGTH} characters.</p>
            </div>
          )}
          {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>Cancel</Button>
            <Button type="submit" disabled={!isValid || save.isPending}>{save.isPending ? "Saving..." : "Save"}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function ResetPasswordDialog({ account, onClose }: { account: UserAccount; onClose: () => void }) {
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const reset = useMutation({
    mutationFn: () => usersApi.resetPassword(account.id, password),
    onSuccess: () => {
      toast({ title: "Password reset", description: `${account.email} is logged out everywhere and signs in with the new password.` });
      onClose();
    },
    onError: (resetError) => setError(getErrorMessage(resetError)),
  });

  return (
    <Dialog open onOpenChange={open => { if (!open) onClose(); }}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Reset the password of {account.email}</DialogTitle>
          <DialogDescription>They are logged out everywhere and sign in with the new password.</DialogDescription>
        </DialogHeader>
        <form className="space-y-4" onSubmit={event => { event.preventDefault(); setError(null); reset.mutate(); }}>
          <div className="space-y-1">
            <Label htmlFor="reset-password">New password</Label>
            <Input id="reset-password" type="password" autoComplete="new-password" value={password} onChange={event => setPassword(event.target.value)} />
            <p className="text-xs text-muted-foreground">At least {MIN_PASSWORD_LENGTH} characters.</p>
          </div>
          {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>Cancel</Button>
            <Button type="submit" disabled={password.length < MIN_PASSWORD_LENGTH || reset.isPending}>{reset.isPending ? "Saving..." : "Reset password"}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
