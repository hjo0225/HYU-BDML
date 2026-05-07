'use client';

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import { registerTokenGetter } from '@/lib/api';

// ── 타입 ──────────────────────────────────────────────────────────────────

export interface AuthUser {
  id: string;
  email: string;
  name: string | null;
  role: 'user' | 'admin';
}

interface AuthContextValue {
  user: AuthUser | null;
  accessToken: string | null;   // 메모리에만 보관 (XSS 방지)
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  register: (email: string, password: string, name?: string) => Promise<void>;
  getToken: () => string | null;  // 최신 access token 반환 (api.ts에서 호출)
}

// ── Context ────────────────────────────────────────────────────────────────

const AuthContext = createContext<AuthContextValue | null>(null);

const API_BASE =
  process.env.NODE_ENV === 'development'
    ? `${process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000'}/api`
    : '/api';

// ── Provider ───────────────────────────────────────────────────────────────

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // ref로 최신 token을 항상 참조 (setTimeout 클로저 문제 방지)
  const tokenRef = useRef<string | null>(null);
  const refreshTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // ── 토큰 갱신 스케줄러 ─────────────────────────────────────────────────
  const scheduleRefresh = useCallback((expiresInMs: number) => {
    if (refreshTimerRef.current) clearTimeout(refreshTimerRef.current);
    // 만료 5분 전에 갱신 (최소 10초)
    const delay = Math.max(expiresInMs - 5 * 60 * 1000, 10_000);
    refreshTimerRef.current = setTimeout(() => silentRefresh(), delay);
  }, []);

  const saveAuth = useCallback(
    (token: string, userInfo: AuthUser) => {
      tokenRef.current = token;
      setAccessToken(token);
      setUser(userInfo);

      // JWT exp 파싱해서 남은 시간 계산
      try {
        const payload = JSON.parse(atob(token.split('.')[1]));
        const expiresInMs = payload.exp * 1000 - Date.now();
        scheduleRefresh(expiresInMs);
      } catch {
        scheduleRefresh(55 * 60 * 1000); // 기본 55분
      }
    },
    [scheduleRefresh],
  );

  const clearAuth = useCallback(() => {
    tokenRef.current = null;
    setAccessToken(null);
    setUser(null);
    if (refreshTimerRef.current) clearTimeout(refreshTimerRef.current);
  }, []);

  // ── 무음 토큰 갱신 (httpOnly 쿠키 사용) ───────────────────────────────
  const silentRefresh = useCallback(async (): Promise<boolean> => {
    try {
      const res = await fetch(`${API_BASE}/auth/refresh`, {
        method: 'POST',
        credentials: 'include',  // httpOnly 쿠키 자동 전송
      });
      if (!res.ok) {
        clearAuth();
        return false;
      }
      const data = await res.json();
      saveAuth(data.access_token, data.user);
      return true;
    } catch {
      clearAuth();
      return false;
    }
  }, [saveAuth, clearAuth]);

  // ── 앱 시작 시 쿠키로 복원 + api.ts 토큰 게터 등록 ─────────────────────
  useEffect(() => {
    registerTokenGetter(() => tokenRef.current);  // api.ts의 apiFetch가 사용
    silentRefresh().finally(() => setIsLoading(false));
    return () => {
      if (refreshTimerRef.current) clearTimeout(refreshTimerRef.current);
    };
  }, []);  // eslint-disable-line react-hooks/exhaustive-deps

  // ── 로그인 ────────────────────────────────────────────────────────────
  const login = useCallback(
    async (email: string, password: string): Promise<void> => {
      const res = await fetch(`${API_BASE}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ email, password }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || '로그인에 실패했습니다.');
      }
      const data = await res.json();
      saveAuth(data.access_token, data.user);
    },
    [saveAuth],
  );

  // ── 회원가입 ──────────────────────────────────────────────────────────
  const register = useCallback(
    async (email: string, password: string, name?: string): Promise<void> => {
      const res = await fetch(`${API_BASE}/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ email, password, name }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || '회원가입에 실패했습니다.');
      }
      const data = await res.json();
      saveAuth(data.access_token, data.user);
    },
    [saveAuth],
  );

  // ── 로그아웃 ──────────────────────────────────────────────────────────
  const logout = useCallback(async (): Promise<void> => {
    try {
      await fetch(`${API_BASE}/auth/logout`, {
        method: 'POST',
        credentials: 'include',
      });
    } catch {
      // 네트워크 오류여도 클라이언트 상태는 지운다
    }
    clearAuth();
  }, [clearAuth]);

  const getToken = useCallback(() => tokenRef.current, []);

  return (
    <AuthContext.Provider
      value={{ user, accessToken, isLoading, login, logout, register, getToken }}
    >
      {children}
    </AuthContext.Provider>
  );
}

// ── Hook ───────────────────────────────────────────────────────────────────

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth는 AuthProvider 안에서 사용해야 합니다');
  return ctx;
}
