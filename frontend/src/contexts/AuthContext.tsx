'use client';

import React, { createContext, useCallback, useContext, useEffect, useState } from 'react';
import { auth } from '@/lib/api';
import type { User } from '@/lib/types';

interface AuthState {
  user: User | null;
  token: string | null;
  isLoading: boolean;
}

interface AuthContextValue extends AuthState {
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, name?: string) => Promise<void>;
  logout: () => Promise<void>;
  setSession: (token: string, user: User) => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<AuthState>({ user: null, token: null, isLoading: true });

  // 앱 진입 시 토큰 복원 (sessionStorage → refresh 시도)
  useEffect(() => {
    const stored = sessionStorage.getItem('ditto_token');
    if (stored) {
      setState(s => ({ ...s, token: stored, isLoading: false }));
      auth.me(stored)
        .then(user => setState({ user: user as User, token: stored, isLoading: false }))
        .catch(() => {
          sessionStorage.removeItem('ditto_token');
          setState({ user: null, token: null, isLoading: false });
        });
    } else {
      auth.refresh()
        .then(res => {
          sessionStorage.setItem('ditto_token', res.access_token);
          setState({ user: res.user as User, token: res.access_token, isLoading: false });
        })
        .catch(() => setState({ user: null, token: null, isLoading: false }));
    }
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const res = await auth.login(email, password);
    sessionStorage.setItem('ditto_token', res.access_token);
    setState({ user: res.user as User, token: res.access_token, isLoading: false });
  }, []);

  const register = useCallback(async (email: string, password: string, name?: string) => {
    const res = await auth.register(email, password, name);
    sessionStorage.setItem('ditto_token', res.access_token);
    setState({ user: res.user as User, token: res.access_token, isLoading: false });
  }, []);

  const logout = useCallback(async () => {
    await auth.logout().catch(() => {});
    sessionStorage.removeItem('ditto_token');
    setState({ user: null, token: null, isLoading: false });
  }, []);

  const setSession = useCallback((token: string, user: User) => {
    sessionStorage.setItem('ditto_token', token);
    setState({ user, token, isLoading: false });
  }, []);

  return (
    <AuthContext.Provider value={{ ...state, login, register, logout, setSession }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
