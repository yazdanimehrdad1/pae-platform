import React, { useCallback, useEffect, useState, createContext, useContext, ReactNode } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { authApi } from '@/api/me';
import { isUnauthorized, onUnauthorized } from '@/api/client';
import type { MeResponse } from '@/api/types/me';

// PlusDAS users live in intelli-gateway. The session is an HttpOnly cookie set by its login
// route, so this context never sees a token: it asks /v1/me who is logged in, and any 401 from
// any API (an expired or ended session) sends the user back to the login page.

export type UserRole = MeResponse['role'];

export interface User {
  id: string;
  email: string;
  name: string;
  role: UserRole;
}

export interface AuthContextType {
  user: User | null;
  /** Rejects with the API error (e.g. 401 "wrong email or password"). */
  login: (email: string, password: string) => Promise<User>;
  logout: () => Promise<void>;
  isLoading: boolean;
}

const AuthContext = createContext<AuthContextType | null>(null);

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

function toUser(me: MeResponse): User {
  return { id: String(me.id), email: me.email, name: me.display_name, role: me.role };
}

export const AuthProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const queryClient = useQueryClient();
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // A session ended elsewhere (expired, logged out in another tab, user disabled): drop
  // everything cached for that user so the next login starts clean.
  const endSession = useCallback(() => {
    setUser(null);
    queryClient.clear();
  }, [queryClient]);

  useEffect(() => {
    let cancelled = false;
    authApi.me()
      .then(me => { if (!cancelled) setUser(toUser(me)); })
      .catch(error => {
        // Not logged in is the normal answer here; anything else (the gateway down) also shows
        // the login page, which reports the error when the user tries.
        if (!isUnauthorized(error)) console.warn('Could not check the session', error);
      })
      .finally(() => { if (!cancelled) setIsLoading(false); });
    return () => { cancelled = true; };
  }, []);

  useEffect(() => onUnauthorized(endSession), [endSession]);

  const login = useCallback(async (email: string, password: string) => {
    queryClient.clear();
    const loggedIn = toUser(await authApi.login({ email, password }));
    setUser(loggedIn);
    return loggedIn;
  }, [queryClient]);

  const logout = useCallback(async () => {
    try {
      await authApi.logout();
    } finally {
      endSession();
    }
  }, [endSession]);

  return React.createElement(
    AuthContext.Provider,
    { value: { user, login, logout, isLoading } },
    children
  );
};
