/**
 * LoginPage — SSO é o caminho principal.
 * E-mail e senha ficam recolhidos como acesso de emergência (conta local).
 */
import { useState, useEffect } from 'react';
import { useAuth } from '../hooks/useAuth';
import BrandMark from './BrandMark';

const inputCls =
  'w-full px-4 py-3 text-sm text-white bg-[#0b1326] border border-white/15 placeholder:text-[#8fa0b6] focus:outline-none focus:border-[#00ADE8]';

const Spinner = ({ cls }: { cls: string }) => (
  <svg className={`animate-spin ${cls}`} viewBox="0 0 24 24" fill="none" aria-hidden>
    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
  </svg>
);

export default function LoginPage() {
  const { login, loginWithSSO, exchangeCodeForToken } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [ssoLoading, setSsoLoading] = useState(false);
  const [showPwd, setShowPwd] = useState(false);

  useEffect(() => {
    // Callback do SSO na URL
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
          window.history.replaceState({}, document.title, window.location.pathname.replace('/callback', '/'));
        })
        .catch((err) => {
          setError(err instanceof Error ? err.message : 'Falha na autenticação SSO');
          setSsoLoading(false);
        });
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
    <div className="min-h-screen flex items-center justify-center bg-[#0b1326] px-4 py-8">
      <div className="w-full max-w-sm border border-white/10 bg-[#162244] p-8">
        <div className="mb-8 text-center">
          <BrandMark size="lg" />
          <p className="mt-4 text-sm text-[#cbd5e1]">Acesse o painel de operações</p>
        </div>

        {ssoLoading ? (
          <div className="flex flex-col items-center justify-center py-10 gap-4" role="status">
            <Spinner cls="w-8 h-8 text-[#00ADE8]" />
            <span className="text-[#cbd5e1] text-sm">Autenticando via SSO...</span>
          </div>
        ) : (
          <>
            <button
              type="button"
              onClick={() => { Promise.resolve(loginWithSSO()).catch(err => setError(err instanceof Error ? err.message : 'Falha no SSO')); }}
              className="w-full py-3 text-sm font-semibold text-[#04121c] bg-[#00ADE8] hover:bg-[#33bdee] transition-colors"
            >
              Entrar com conta corporativa
            </button>

            {error && (
              <div role="alert" className="mt-3 border border-red-500/40 px-3 py-2.5 text-xs text-red-300">
                {error}
              </div>
            )}

            <details className="mt-6 border-t border-white/10 pt-4">
              <summary className="cursor-pointer text-xs text-[#94a3b8] hover:text-[#f1f5f9]">
                Acesso de emergência (conta local)
              </summary>
              <form onSubmit={handleSubmit} className="mt-4 space-y-4">
                <div>
                  <label htmlFor="email" className="block text-xs font-medium text-[#cbd5e1] mb-1.5">E-mail</label>
                  <input id="email" type="email" autoComplete="email" required value={email}
                    onChange={(e) => setEmail(e.target.value)} placeholder="voce@ness.com.br" className={inputCls} />
                </div>
                <div>
                  <label htmlFor="password" className="block text-xs font-medium text-[#cbd5e1] mb-1.5">Senha</label>
                  <div className="relative">
                    <input id="password" type={showPwd ? 'text' : 'password'} autoComplete="current-password" required
                      value={password} onChange={(e) => setPassword(e.target.value)} className={`${inputCls} pr-16`} />
                    <button type="button" onClick={() => setShowPwd((v) => !v)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-[#94a3b8] hover:text-[#f1f5f9]"
                      aria-label={showPwd ? 'Ocultar senha' : 'Mostrar senha'}>
                      {showPwd ? 'Ocultar' : 'Mostrar'}
                    </button>
                  </div>
                </div>
                <button type="submit" disabled={loading}
                  className="w-full py-3 text-sm font-semibold text-[#f1f5f9] border border-white/20 hover:border-[#00ADE8] disabled:opacity-50 disabled:cursor-not-allowed transition-colors">
                  {loading ? <span className="flex items-center justify-center gap-2"><Spinner cls="w-4 h-4" />Entrando…</span> : 'Entrar'}
                </button>
              </form>
            </details>
          </>
        )}

        <p className="mt-6 text-center text-xs text-[#8fa0b6]">© {new Date().getFullYear()} ness.</p>
      </div>
    </div>
  );
}
