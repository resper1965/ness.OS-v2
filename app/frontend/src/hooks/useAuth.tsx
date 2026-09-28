/**
 * useAuth — sessão segura de navegador para n.infraops
 * O JWT permanece somente no cookie HttpOnly emitido pelo backend.
 */
import { useState, useEffect, useCallback, createContext, useContext } from 'react';

const API_BASE = import.meta.env.VITE_API_URL ?? '';
const OIDC_STATE_KEY = 'oidc_state';
const OIDC_VERIFIER_KEY = 'oidc_code_verifier';

function base64Url(bytes: Uint8Array): string {
  let binary = '';
  bytes.forEach((byte) => { binary += String.fromCharCode(byte); });
  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

async function createPkce(): Promise<{ verifier: string; challenge: string }> {
  const verifier = base64Url(crypto.getRandomValues(new Uint8Array(64)));
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(verifier));
  return { verifier, challenge: base64Url(new Uint8Array(digest)) };
}

export interface User {
  id: number;
  email: string;
  full_name: string;
  role: 'platform_admin' | 'admin' | 'noc' | 'soc' | 'helpdesk' | 'gestao' | 'cliente';
}

interface AuthState {
  user: User | null;
  loading: boolean;
}

interface AuthContextValue extends AuthState {
  login: (email: string, password: string) => Promise<void>;
  loginWithSSO: () => void;
  exchangeCodeForToken: (code: string, returnedState: string) => Promise<void>;
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

  // Recuperar a sessão existente sem expor o token ao JavaScript.
  useEffect(() => {
    fetch(`${API_BASE}/api/auth/me`, {
      credentials: 'include',
    })
      .then((r) => (r.ok ? r.json() : Promise.reject()))
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

  const loginWithSSO = useCallback(async () => {
    const clientId = "hub-ness";
    const redirectUri = encodeURIComponent(`${window.location.origin}/callback`);
    const stateBytes = crypto.getRandomValues(new Uint8Array(32));
    const oidcState = Array.from(stateBytes, (byte) => byte.toString(16).padStart(2, '0')).join('');
    const { verifier, challenge } = await createPkce();
    sessionStorage.setItem(OIDC_STATE_KEY, oidcState);
    sessionStorage.setItem(OIDC_VERIFIER_KEY, verifier);
    
    const authorizeUrl = `https://sso.ness.com.br/application/o/authorize/?client_id=${clientId}&response_type=code&redirect_uri=${redirectUri}&scope=openid+profile+email+groups&state=${oidcState}&code_challenge=${challenge}&code_challenge_method=S256`;
    window.location.href = authorizeUrl;
  }, []);

  const exchangeCodeForToken = useCallback(async (code: string, returnedState: string) => {
    const expectedState = sessionStorage.getItem(OIDC_STATE_KEY);
    const codeVerifier = sessionStorage.getItem(OIDC_VERIFIER_KEY);
    sessionStorage.removeItem(OIDC_STATE_KEY);
    sessionStorage.removeItem(OIDC_VERIFIER_KEY);
    if (!expectedState || !returnedState || expectedState !== returnedState || !codeVerifier) {
      throw new Error('Estado OIDC inválido ou expirado. Inicie o login novamente.');
    }

    const redirectUri = `${window.location.origin}/callback`;
    const r = await fetch(`${API_BASE}/api/auth/oidc/callback`, {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ code, redirect_uri: redirectUri, code_verifier: codeVerifier }),
    });
    
    if (!r.ok) {
      const err = await r.json().catch(() => ({}));
      throw new Error(err.detail ?? 'Falha na autenticação SSO');
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
      const clientId = "hub-ness";
      const postLogoutRedirectUri = encodeURIComponent(window.location.origin);
      window.location.href = `https://sso.ness.com.br/application/o/hub/end-session/?client_id=${clientId}&post_logout_redirect_uri=${postLogoutRedirectUri}`;
    } catch {
      window.alert('Não foi possível encerrar a sessão no Hub. Tente novamente.');
    }
  }, []);

  // Mantém a interface dos consumidores enquanto a autenticação via cookie
  // é enviada automaticamente pelo navegador nas chamadas same-origin.
  const authHeader = useCallback(() => ({}), []);

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
