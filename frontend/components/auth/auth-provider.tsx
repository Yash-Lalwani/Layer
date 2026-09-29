'use client';

import { createContext, useContext, useEffect, useState } from 'react';
import { api } from '@/lib/api';
import { clearToken, getToken, setToken } from '@/lib/auth';
import type { AuthResponse, User } from '@/lib/types';

interface AuthState {
  user: User | null;
  loading: boolean;
  signIn: (auth: AuthResponse) => void;
  signOut: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!getToken()) {
      setLoading(false);
      return;
    }
    api.me().then(setUser).catch(() => setUser(null)).finally(() => setLoading(false));
  }, []);

  const signIn = (auth: AuthResponse) => {
    setToken(auth.token);
    setUser(auth.user);
  };
  const signOut = () => {
    clearToken();
    setUser(null);
  };

  return <AuthContext.Provider value={{ user, loading, signIn, signOut }}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const context = useContext(AuthContext);
  if (!context) throw new Error('AuthProvider is missing');
  return context;
}

