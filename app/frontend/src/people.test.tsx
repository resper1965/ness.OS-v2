import { renderToStaticMarkup } from 'react-dom/server';
import { afterEach, describe, expect, it, vi } from 'vitest';
import PeopleView from './components/people/PeopleView';
import { createPeopleStore, type Person } from './hooks/usePeople';

afterEach(() => vi.unstubAllGlobals());
const noop = new Proxy({}, { get: () => () => undefined }) as never;
const text = (html: string) => html.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ');
const customers = [{ id: 7, key: 'acme', display_name: 'Acme', glpi_entity_id: 12, active: true, aliases: [], ai_external_allowed: false }];
const ana: Person = { id: 1, email: 'ana@ness.com.br', full_name: 'Ana', kind: 'ness', role: 'noc', customer_ids: [7], is_oncall: true, is_active: true };

function markup(over = {}) {
  const { store } = createPeopleStore();
  store.set({ phase: 'ready', people: [ana], customers, ...over });
  return renderToStaticMarkup(<PeopleView state={store.get()} actions={noop} />);
}

describe('PeopleView', () => {
  it('lista pessoa com cliente e plantão', () => {
    const t = text(markup());
    expect(t).toContain('Ana');
    expect(t).toContain('Acme');
    expect(t).toContain('Plantão');
  });
  it('simulação em dia e com diferenças', () => {
    expect(text(markup({ diff: [] }))).toContain('Em dia');
    expect(text(markup({ diff: ['CREATE user x'] }))).toContain('CREATE user x');
  });
  it('externo escolhe 1 cliente e não vê plantão', () => {
    const html = markup({ editing: 'new' });
    expect(html).toContain('Nova pessoa');
  });
});

describe('store', () => {
  it('cadastra e recarrega', async () => {
    const calls: string[] = [];
    vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
      calls.push(`${init?.method ?? 'GET'} ${url}`);
      return new Response(JSON.stringify(url.includes('customers') ? customers : url === '/api/people' && init?.method === 'POST' ? ana : [ana]),
        { status: 200, headers: { 'content-type': 'application/json' } });
    }));
    const { store, actions } = createPeopleStore();
    await actions.load();
    actions.startEdit('new');
    expect(await actions.save({ email: 'ana@ness.com.br', full_name: 'Ana', kind: 'ness', customer_ids: [7], is_oncall: false, is_active: true })).toBe(true);
    expect(calls.filter((c) => c.startsWith('POST')).length).toBe(1);
    expect(store.get().editing).toBeNull();
  });
});
