/**
 * useAuth — sessão segura de navegador para n.infraops
 * O JWT permanece somente no cookie HttpOnly emitido pelo backend.
 */
import { useState, useEffect, useCallback, createContext, useContext } from 'react';

const API_BASE = import.meta.env.VITE_API_URL ?? '';

export interface User {
  id: number;
  email: string;
  full_name: string;
  role: 'platform_admin' | 'admin' | 'noc' | 'soc' | 'helpdesk' | 'gestao' | 'cliente' | 'operator' | 'viewer';
}

interface AuthState {
  user: User | null;
  loading: boolean;
}

interface AuthContextValue extends AuthState {
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  isAuthenticated: boolean;
  authHeader: () => Record<string, string>;
}

// ─── Context ─────────────────────────────────────────────────────────────────
const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<AuthState>({
    user: null,
    loading: true,
  });

  // Sessão existente; sem ela, tenta o SSO do Cloudflare Access (404/401 = login local).
  useEffect(() => {
    const get = (path: string, method = 'GET') =>
      fetch(`${API_BASE}${path}`, { method, credentials: 'include' }).then((r) =>
        r.ok ? r.json() : Promise.reject(),
      );
    get('/api/auth/me')
      .catch(() => get('/api/auth/access-login', 'POST'))
      .then((user: User) => setState({ user, loading: false }))
      .catch(() => setState({ user: null, loading: false }));
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const r = await fetch(`${API_BASE}/api/auth/login`, {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });
    if (!r.ok) {
      const err = await r.json().catch(() => ({}));
      throw new Error(err.detail ?? 'Credenciais inválidas');
    }
    const data = await r.json();
    setState({ user: data, loading: false });
  }, []);

  const logout = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/api/auth/logout`, {
        method: 'POST',
        credentials: 'include',
      });
      if (!response.ok) throw new Error('Falha ao encerrar a sessão no Hub. Tente novamente.');
      setState({ user: null, loading: false });
    } catch {
      window.alert('Não foi possível encerrar a sessão no Hub. Tente novamente.');
    }
  }, []);

  // Mantém a interface dos consumidores enquanto a autenticação via cookie
  // é enviada automaticamente pelo navegador nas chamadas same-origin.
  const authHeader = useCallback(() => ({}), []);

  return (
    <AuthContext.Provider
      value={{ ...state, login, logout, isAuthenticated: !!state.user, authHeader }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
