/**
 * useAuth — Hook de autenticação JWT para n.infraops
 * Persiste token no localStorage, expõe user + login/logout
 */
import { useState, useEffect, useCallback, createContext, useContext } from 'react';

const API_BASE = import.meta.env.VITE_API_URL ?? '';
const TOKEN_KEY = 'ninf_token';

export interface User {
  id: number;
  email: string;
  full_name: string;
  role: 'noc' | 'soc' | 'admin' | 'cliente';
}

interface AuthState {
  user: User | null;
  token: string | null;
  loading: boolean;
}

interface AuthContextValue extends AuthState {
  login: (email: string, password: string) => Promise<void>;
  loginWithSSO: () => void;
  exchangeCodeForToken: (code: string) => Promise<void>;
  logout: () => void;
  isAuthenticated: boolean;
  authHeader: () => Record<string, string>;
}

// ─── Context ─────────────────────────────────────────────────────────────────
const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<AuthState>({
    user: null,
    token: localStorage.getItem(TOKEN_KEY),
    loading: true,
  });

  // Verificar token existente no mount
  useEffect(() => {
    const token = localStorage.getItem(TOKEN_KEY);
    if (!token) {
      setState({ user: null, token: null, loading: false });
      return;
    }
    fetch(`${API_BASE}/api/auth/me`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then((user: User) => setState({ user, token, loading: false }))
      .catch(() => {
        localStorage.removeItem(TOKEN_KEY);
        setState({ user: null, token: null, loading: false });
      });
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const r = await fetch(`${API_BASE}/api/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });
    if (!r.ok) {
      const err = await r.json().catch(() => ({}));
      throw new Error(err.detail ?? 'Credenciais inválidas');
    }
    const data = await r.json();
    localStorage.setItem(TOKEN_KEY, data.access_token);
    setState({ user: data, token: data.access_token, loading: false });
  }, []);

  const loginWithSSO = useCallback(() => {
    const clientId = "hub-ness";
    const redirectUri = encodeURIComponent(`${window.location.origin}/callback`);
    const oidcState = Math.random().toString(36).substring(2, 15);
    sessionStorage.setItem('oidc_state', oidcState);
    
    const authorizeUrl = `https://sso.ness.com.br/application/o/authorize/?client_id=${clientId}&response_type=code&redirect_uri=${redirectUri}&scope=openid+profile+email+groups&state=${oidcState}`;
    window.location.href = authorizeUrl;
  }, []);

  const exchangeCodeForToken = useCallback(async (code: string) => {
    const redirectUri = `${window.location.origin}/callback`;
    const r = await fetch(`${API_BASE}/api/auth/oidc/callback`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ code, redirect_uri: redirectUri }),
    });
    
    if (!r.ok) {
      const err = await r.json().catch(() => ({}));
      throw new Error(err.detail ?? 'Falha na autenticação SSO');
    }
    
    const data = await r.json();
    localStorage.setItem(TOKEN_KEY, data.access_token);
    setState({ user: data, token: data.access_token, loading: false });
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY);
    setState({ user: null, token: null, loading: false });
    
    // Redirecionamento de saída do Authentik
    const clientId = "hub-ness";
    const postLogoutRedirectUri = encodeURIComponent(window.location.origin);
    window.location.href = `https://sso.ness.com.br/application/o/hub/end-session/?client_id=${clientId}&post_logout_redirect_uri=${postLogoutRedirectUri}`;
  }, []);

  const authHeader = useCallback(() =>
    state.token ? { Authorization: `Bearer ${state.token}` } : {},
  [state.token]);

  return (
    <AuthContext.Provider
      value={{ ...state, login, loginWithSSO, exchangeCodeForToken, logout, isAuthenticated: !!state.user, authHeader }}
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
