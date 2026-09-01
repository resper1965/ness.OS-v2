/**
 * LoginPage — Tela de login premium para n.infraops PWA
 * Design: dark glassmorphism, brand ness., mobile-first
 */
import { useState, useRef, useEffect } from 'react';
import { useAuth } from '../hooks/useAuth';
import BrandMark from './BrandMark';

export default function LoginPage() {
  const { login, loginWithSSO, exchangeCodeForToken } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [ssoLoading, setSsoLoading] = useState(false);
  const [showPwd, setShowPwd] = useState(false);
  const emailRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    // Interceptar callback do Authentik SSO na URL
    const params = new URLSearchParams(window.location.search);
    const code = params.get('code');
    const returnedState = params.get('state');
    const oidcError = params.get('error');
    if (oidcError) {
      sessionStorage.removeItem('oidc_state');
      setError('O provedor de identidade recusou a autenticação. Tente novamente.');
      window.history.replaceState({}, document.title, '/');
      return;
    }
    if (code) {
      setSsoLoading(true);
      setError('');
      exchangeCodeForToken(code, returnedState ?? '')
        .then(() => {
          // Limpa os parâmetros da URL redirecionando para a raiz de forma limpa
          window.history.replaceState({}, document.title, window.location.pathname.replace('/callback', '/'));
        })
        .catch((err) => {
          setError(err instanceof Error ? err.message : 'Falha na autenticação SSO');
          setSsoLoading(false);
        });
    } else {
      emailRef.current?.focus();
    }
  }, [exchangeCodeForToken]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await login(email.trim(), password);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Erro ao fazer login');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-[#08111f] px-4 py-8">
      {/* Glow de fundo */}
      <div
        aria-hidden
        className="pointer-events-none fixed inset-0 overflow-hidden"
      >
        <div className="absolute -top-40 left-1/2 -translate-x-1/2 w-[600px] h-[600px] rounded-full bg-[#00ADE8]/8 blur-[120px]" />
      </div>

      <div className="relative w-full max-w-sm">
        {/* Card */}
        <div
          className="rounded-2xl border border-white/8 p-8 shadow-2xl"
          style={{
            background: 'linear-gradient(135deg, rgba(255,255,255,0.05) 0%, rgba(255,255,255,0.02) 100%)',
            backdropFilter: 'blur(20px)',
          }}
        >
          {/* Logo */}
          <div className="mb-8 text-center">
            <BrandMark size="lg" />
            <p className="mt-4 text-sm text-white/40">
              Acesse o painel de operações
            </p>
          </div>

          {ssoLoading ? (
            <div className="flex flex-col items-center justify-center py-10 gap-4">
              <svg className="animate-spin w-8 h-8 text-[#00ADE8]" viewBox="0 0 24 24" fill="none">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
              </svg>
              <span className="text-white/60 text-sm">Autenticando via SSO...</span>
            </div>
          ) : (
            <>
              <form onSubmit={handleSubmit} className="space-y-4">
                {/* Email */}
                <div>
                  <label htmlFor="email" className="block text-xs font-medium text-white/50 mb-1.5">
                    E-mail
                  </label>
                  <input
                    id="email"
                    ref={emailRef}
                    type="email"
                    autoComplete="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="voce@ness.com.br"
                    className="
                      w-full px-4 py-3 rounded-xl text-sm text-white
                      bg-white/[0.06] border border-white/10
                      placeholder:text-white/20
                      focus:outline-none focus:border-[#00ADE8]/60 focus:bg-white/[0.08]
                      transition-all duration-200
                    "
                  />
                </div>

                {/* Senha */}
                <div>
                  <label htmlFor="password" className="block text-xs font-medium text-white/50 mb-1.5">
                    Senha
                  </label>
                  <div className="relative">
                    <input
                      id="password"
                      type={showPwd ? 'text' : 'password'}
                      autoComplete="current-password"
                      required
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      placeholder="••••••••"
                      className="
                        w-full px-4 py-3 pr-12 rounded-xl text-sm text-white
                        bg-white/[0.06] border border-white/10
                        placeholder:text-white/20
                        focus:outline-none focus:border-[#00ADE8]/60 focus:bg-white/[0.08]
                        transition-all duration-200
                      "
                    />
                    <button
                      type="button"
                      onClick={() => setShowPwd((v) => !v)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-white/30 hover:text-white/60 transition-colors p-1"
                      aria-label={showPwd ? 'Ocultar senha' : 'Mostrar senha'}
                    >
                      {showPwd ? (
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                          <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/>
                          <line x1="1" y1="1" x2="23" y2="23"/>
                        </svg>
                      ) : (
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                          <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
                          <circle cx="12" cy="12" r="3"/>
                        </svg>
                      )}
                    </button>
                  </div>
                </div>

                {/* Erro */}
                {error && (
                  <div className="flex items-center gap-2 text-red-400 text-xs bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2.5">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
                    </svg>
                    {error}
                  </div>
                )}

                {/* Botão */}
                <button
                  type="submit"
                  disabled={loading}
                  className="
                    w-full py-3 rounded-xl text-sm font-semibold text-white
                    bg-[#00ADE8] hover:bg-[#00c2ff]
                    disabled:opacity-50 disabled:cursor-not-allowed
                    shadow-[0_0_20px_rgba(0,173,232,0.3)]
                    hover:shadow-[0_0_30px_rgba(0,173,232,0.5)]
                    transition-all duration-200
                    mt-2
                  "
                >
                  {loading ? (
                    <span className="flex items-center justify-center gap-2">
                      <svg className="animate-spin w-4 h-4" viewBox="0 0 24 24" fill="none">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
                      </svg>
                      Entrando…
                    </span>
                  ) : 'Entrar'}
                </button>
              </form>

              {/* Separador */}
              <div className="relative my-6 flex items-center justify-center">
                <div className="absolute inset-0 flex items-center">
                  <div className="w-full border-t border-white/10"></div>
                </div>
                <span className="relative px-3 text-[10px] uppercase tracking-wider text-white/30" style={{ backgroundColor: '#0d1726' }}>
                  Ou continue com
                </span>
              </div>

              {/* Botão Authentik SSO */}
              <button
                type="button"
                onClick={loginWithSSO}
                className="
                  w-full py-3 rounded-xl text-sm font-semibold text-white
                  bg-white/[0.04] border border-white/10 hover:bg-white/[0.08]
                  transition-all duration-200 flex items-center justify-center gap-2
                  shadow-lg hover:border-white/20
                "
              >
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-[#00ADE8]">
                  <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/>
                  <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
                </svg>
                Entrar com SSO
              </button>
            </>
          )}

          {/* Footer */}
          <p className="mt-6 text-center text-xs text-white/20">
            © {new Date().getFullYear()} ness.
          </p>
        </div>
      </div>
    </div>
  );
}
