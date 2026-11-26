import { renderToStaticMarkup } from 'react-dom/server';
import { afterEach, describe, expect, it, vi } from 'vitest';
import AjustesView from './components/ajustes/AjustesView';
import { createAjustesStore } from './hooks/useAjustes';
import { allowedView } from './App';

afterEach(() => vi.unstubAllGlobals());
const noop = new Proxy({}, { get: () => () => undefined }) as never;
const params = {
  ticket_grace_minutes: { value: 15, default: 15, max: 86400 },
  soc_ticket_min_level: { value: 12, default: 12, max: 15 },
};
const rules = [{ id: 1, kind: 'noise' as const, pattern: 'VM3DService', note: null, enabled: true }];

function markup(canEdit: boolean) {
  const { store } = createAjustesStore();
  store.set({ phase: 'ready', params, rules });
  return renderToStaticMarkup(<AjustesView state={store.get()} actions={noop} canEdit={canEdit} />);
}

describe('AjustesView', () => {
  it('platform_admin vê os campos e o formulário de regra', () => {
    const html = markup(true);
    expect(html).toContain('Carência antes de abrir chamado');
    expect(html).toContain('Nova regra');
    expect(html).toContain('Remover');
  });
  it('NOC só lê: sem salvar, sem adicionar, sem remover', () => {
    const html = markup(false);
    expect(html).toContain('Carência antes de abrir chamado');
    expect(html).toContain('VM3DService');
    for (const t of ['Salvar', 'Adicionar regra', 'Remover']) expect(html).not.toContain(t);
  });
  it('só mostra o que a API devolveu', () => {
    expect(markup(false)).not.toContain('Janela de ligação entre NOC e SOC');
  });
});

describe('store', () => {
  it('salva o ajuste e recarrega', async () => {
    const calls: string[] = [];
    vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
      calls.push(`${init?.method ?? 'GET'} ${url}`);
      return new Response(JSON.stringify(url.includes('platform-params') && !init?.method ? params : url.includes('ticket-rules') ? rules : { key: 'x', value: 20 }),
        { status: 200, headers: { 'content-type': 'application/json' } });
    }));
    const { store, actions } = createAjustesStore();
    await actions.saveParam('ticket_grace_minutes', 20);
    expect(calls[0]).toBe('PUT /api/v1/sla/platform-params/ticket_grace_minutes');
    expect(store.get().notice).toBe('Ajuste salvo.');
    expect(store.get().phase).toBe('ready');
  });
});

describe('navegação', () => {
  it('ajustes só para operador', () => {
    expect(allowedView('ajustes', true, false)).toBe('ajustes');
    expect(allowedView('ajustes', false, false)).toBe('incidents');
    expect(allowedView('ajustes', false, false, false, true)).toBe('painel');
  });
});
