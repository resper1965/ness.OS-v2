/**
 * LoginPage — SSO é o caminho principal.
 * E-mail e senha ficam recolhidos como acesso de emergência (conta local).
 */
import { useState, useEffect } from 'react';
import { useAuth } from '../hooks/useAuth';
import BrandMark from './BrandMark';

const inputCls =
  'w-full h-[34px] px-3 text-sm text-brand-text bg-brand-base border border-brand-border placeholder:text-brand-muted focus:border-brand-primary';

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
      // A URL volta antes da troca: o shell monta assim que o usuário chega e lê ?view= dali.
      const back = sessionStorage.getItem('oidc_return') ?? '';
      sessionStorage.removeItem('oidc_return');
      window.history.replaceState({}, document.title, `/${back.startsWith('?') ? back : ''}`);
      exchangeCodeForToken(code, returnedState ?? '')
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
    <div className="min-h-screen flex items-center justify-center bg-brand-base px-4 py-8">
      <div className="w-full max-w-sm border border-brand-border bg-brand-surface p-8">
        <div className="mb-8 flex flex-col items-center text-center">
          <BrandMark size="lg" />
          <p className="mt-4 text-sm text-brand-text-2">Acesse o painel de operações</p>
        </div>

        {ssoLoading ? (
          <div className="flex flex-col items-center justify-center py-10 gap-4" role="status">
            <div className="w-32 h-1 bg-brand-elevated" aria-hidden />
            <span className="text-brand-text-2 text-sm">Autenticando…</span>
          </div>
        ) : (
          <>
            <button
              type="button"
              onClick={() => { Promise.resolve(loginWithSSO()).catch(err => setError(err instanceof Error ? err.message : 'Falha no SSO')); }}
              className="w-full h-[34px] text-sm font-semibold text-brand-accent-ink bg-brand-primary hover:bg-brand-primary-hover transition-colors"
            >
              Entrar com conta corporativa
            </button>

            {error && (
              <div role="alert" className="mt-3 border border-brand-border border-l-2 border-l-brand-danger px-3 py-2.5 text-xs text-brand-text-2">
                {error}
              </div>
            )}

            <details className="mt-6 border-t border-brand-border pt-4">
              <summary className="cursor-pointer text-xs text-brand-text-3 hover:text-brand-text">
                Acesso de emergência (conta local)
              </summary>
              <form onSubmit={handleSubmit} className="mt-4 space-y-4">
                <div>
                  <label htmlFor="email" className="block text-xs font-medium text-brand-text-2 mb-1.5">E-mail</label>
                  <input id="email" type="email" autoComplete="email" required value={email}
                    onChange={(e) => setEmail(e.target.value)} placeholder="voce@ness.com.br" className={inputCls} />
                </div>
                <div>
                  <label htmlFor="password" className="block text-xs font-medium text-brand-text-2 mb-1.5">Senha</label>
                  <div className="relative">
                    <input id="password" type={showPwd ? 'text' : 'password'} autoComplete="current-password" required
                      value={password} onChange={(e) => setPassword(e.target.value)} className={`${inputCls} pr-16`} />
                    <button type="button" onClick={() => setShowPwd((v) => !v)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-brand-text-3 hover:text-brand-text"
                      aria-label={showPwd ? 'Ocultar senha' : 'Mostrar senha'}>
                      {showPwd ? 'Ocultar' : 'Mostrar'}
                    </button>
                  </div>
                </div>
                <button type="submit" disabled={loading}
                  className="w-full h-[34px] text-sm font-semibold text-brand-text border border-brand-border hover:border-brand-primary disabled:opacity-50 disabled:cursor-not-allowed transition-colors">
                  {loading ? 'Entrando…' : 'Entrar'}
                </button>
              </form>
            </details>
          </>
        )}

        <p className="mt-6 text-center text-xs text-brand-muted">© {new Date().getFullYear()} ness.</p>
      </div>
    </div>
  );
}
