import React from 'react';
import { describeError } from './error-surface';

interface State {
  erro: unknown;
}

/**
 * Sem isto, qualquer exceção de render deixa a tela branca e sem pista (relatado em
 * 11/11 no Android). Mostra o código e a mensagem, e deixa recarregar.
 */
export default class ErrorBoundary extends React.Component<
  { children: React.ReactNode },
  State
> {
  state: State = { erro: null };

  static getDerivedStateFromError(erro: unknown): State {
    return { erro };
  }

  componentDidCatch(erro: unknown) {
    console.error('Falha de render no Hub:', erro);
  }

  render() {
    if (this.state.erro === null) return this.props.children;

    const { code, message } = describeError(this.state.erro);
    return (
      <div className="min-h-screen bg-[#08111f] text-slate-100 flex items-center justify-center p-6">
        <div className="max-w-lg w-full border border-white/10 bg-[#0e1a2d] p-6">
          <div className="text-[10px] uppercase tracking-[0.14em] text-[#00ADE8]">
            n.infraops · falha
          </div>
          <h1 className="mt-2 text-lg font-semibold">A tela não pôde ser carregada</h1>
          <p className="mt-2 text-sm text-slate-300">{message}</p>
          <p className="mt-3 font-mono text-xs text-slate-400">código {code}</p>
          <button
            type="button"
            onClick={() => window.location.reload()}
            className="mt-5 border border-[#00ADE8] bg-[#00ADE8] px-3 py-1.5 text-sm font-medium text-[#04121c]"
          >
            Recarregar
          </button>
        </div>
      </div>
    );
  }
}
