// @vitest-environment jsdom
import { act, type ReactNode } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { renderToStaticMarkup } from 'react-dom/server';
import { afterEach, describe, expect, it, vi } from 'vitest';
import faviconSvg from '../public/favicon.svg?raw';
import indexHtml from '../index.html?raw';
import mainTsx from './main.tsx?raw';
import indexCss from './index.css?raw';
import nessCss from './ness-ui.css?raw';
import ContractsScreen from './components/ContractsScreen';
import CustomersScreen from './components/CustomersScreen';
import ContractsView from './components/contracts/ContractsView';
import CustomersView from './components/customers/CustomersView';
import { ConfirmButton, Field, Skeleton } from './components/ui/kit';
import { scrub } from './http';
import { createContractsStore, type Contract, type ContractDetail } from './hooks/useContracts';
import { createContactsStore, createCustomersStore, useContacts, type Contact, type ContactsState, type Customer } from './hooks/useCustomers';

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

let root: Root | null = null;
let host: HTMLElement | null = null;
const flush = () => act(async () => { await new Promise((r) => setTimeout(r, 0)); });
async function mount(node: ReactNode) {
  host = document.createElement('div');
  document.body.append(host);
  root = createRoot(host);
  await act(async () => { root!.render(node); });
  await flush();
}
const rerender = async (node: ReactNode) => { await act(async () => { root!.render(node); }); await flush(); };
afterEach(async () => {
  await act(async () => { root?.unmount(); });
  host?.remove();
  root = host = null;
  vi.unstubAllGlobals();
});

const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } });
const noop = new Proxy({}, { get: () => () => undefined }) as never;
const urls = (f: ReturnType<typeof vi.fn>) => f.mock.calls.map((c) => String(c[0]));

const customer: Customer = { id: 7, key: 'acme', display_name: 'Acme', glpi_entity_id: 12, active: true, aliases: ['acme'] };
const contact: Contact = { id: 3, customer_id: 7, name: 'Maria', email: 'maria@acme.com.br', phone: null, role: 'TI', notify_severity_min: 3, active: true };

describe('P1 fontes próprias', () => {
  const HOSTS = /fonts\.(googleapis|gstatic)\.com/i;
  it('no third-party font host in index.html, css or favicon', () => {
    for (const src of [indexHtml, indexCss, nessCss, faviconSvg]) expect(src).not.toMatch(HOSTS);
  });
  it('fonts are bundled from packages', () => {
    for (const f of ['montserrat', 'inter', 'jetbrains-mono']) expect(mainTsx).toContain(`@fontsource-variable/${f}/wght.css`);
  });
});

describe('P2-1 gate proves no fetch', () => {
  it.each(['viewer', 'cliente', 'gestao', 'helpdesk'])('contracts: %s never calls the API', async (role) => {
    const f = vi.fn(async () => json(200, []));
    vi.stubGlobal('fetch', f);
    await mount(<ContractsScreen role={role} />);
    expect(f).not.toHaveBeenCalled();
    expect(host!.textContent).toContain('não acessa contratos');
  });
  it('contracts: operator loads', async () => {
    const f = vi.fn(async () => json(200, []));
    vi.stubGlobal('fetch', f);
    await mount(<ContractsScreen role="operator" />);
    expect(urls(f)).toContain('/api/v1/sla/contracts');
  });
  it.each(['viewer', 'cliente'])('customers: %s never calls the API', async (role) => {
    const f = vi.fn(async () => json(200, []));
    vi.stubGlobal('fetch', f);
    await mount(<CustomersScreen role={role} />);
    expect(f).not.toHaveBeenCalled();
  });
  const stub = () => {
    const f = vi.fn(async (url: string) => json(200, String(url).endsWith('/contacts') ? [contact] : [customer]));
    vi.stubGlobal('fetch', f);
    return f;
  };
  const pick = async () => {
    const b = [...host!.querySelectorAll('button')].find((x) => x.textContent === 'Acme')!;
    await act(async () => { b.click(); });
    await flush();
  };
  it('customers: operator lists customers but never fetches contacts (PII)', async () => {
    const f = stub();
    await mount(<CustomersScreen role="operator" />);
    await pick();
    expect(urls(f)).toContain('/api/customers');
    expect(urls(f).some((u) => u.includes('/contacts'))).toBe(false);
  });
  it('customers: noc fetches contacts', async () => {
    const f = stub();
    await mount(<CustomersScreen role="noc" />);
    await pick();
    expect(urls(f)).toContain('/api/customers/7/contacts');
  });
});

describe('P2-2 non-contractual badge per region', () => {
  const dflt: Contract = {
    id: 1, tenant_id: null, is_default: true, contractual: false, name: 'Padrão interno', modality: 'managed',
    status: 'active', starts_on: null, ends_on: null, calendar_id: 1, notes: null,
  };
  const detail: ContractDetail = {
    ...dflt,
    policies: [{ id: 1, key: 'p1', name: 'Crítico', min_severity: 4, severity: null, has_tenant: null, ack_minutes: 15, tto_minutes: null, ttr_minutes: 240, calendar_id: null, enabled: true }],
    escalation_steps: [{ id: 1, position: 1, role: 'noc', enabled: true }],
  };
  const cal = { id: 1, name: 'Comercial', timezone: 'America/Sao_Paulo', is_24x7: true, hours: [], holidays: [] };
  const render = (d: ContractDetail) => {
    const { store } = createContractsStore();
    store.set({ phase: 'ready', contracts: [d], calendars: [cal], selectedId: d.id, detail: d });
    const el = document.createElement('div');
    el.innerHTML = renderToStaticMarkup(<ContractsView state={store.get()} actions={noop} canEdit />);
    return el;
  };
  const region = (el: HTMLElement, name: string) => el.querySelector(`section[aria-label="${name}"]`)!;
  const badges = (r: Element) => [...r.querySelectorAll('.nx-badge')].filter((b) => b.textContent === 'padrão interno · não contratual');

  it.each(['Padrão interno', 'Políticas de prazo', 'Escalonamento', 'Calendário'])('%s carries exactly one badge', (name) => {
    expect(badges(region(render(detail), name))).toHaveLength(1);
  });
  it('a real contract has no badge in any region', () => {
    const real = { ...detail, is_default: false, contractual: true };
    for (const name of ['Padrão interno', 'Políticas de prazo', 'Escalonamento', 'Calendário']) {
      expect(badges(region(render(real), name))).toHaveLength(0);
    }
  });
});

describe('P2-3 field a11y', () => {
  const input = (id: string, extra: object = {}) => <input id={id} {...extra} />;
  it('hint is linked through aria-describedby', async () => {
    await mount(<Field label="Chave" hint="Identificador estável.">{(p) => input(p.id, p)}</Field>);
    const el = host!.querySelector('input')!;
    expect(document.getElementById(el.getAttribute('aria-describedby')!)!.textContent).toBe('Identificador estável.');
    expect(el.getAttribute('aria-invalid')).toBeNull();
  });
  it('error sets aria-invalid + aria-errormessage and is also described', async () => {
    await mount(<Field label="Chave" hint="dica" error="Chave já cadastrada">{(p) => input(p.id, p)}</Field>);
    const el = host!.querySelector('input')!;
    expect(el.getAttribute('aria-invalid')).toBe('true');
    expect(document.getElementById(el.getAttribute('aria-errormessage')!)!.textContent).toBe('Chave já cadastrada');
    expect(el.getAttribute('aria-describedby')).toContain(el.getAttribute('aria-errormessage'));
  });
  it('server 409 on the entity id lands on that field only', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => json(409, { detail: 'Entidade GLPI já em uso' })));
    const { store, actions } = createCustomersStore();
    store.set({ phase: 'ready', customers: [customer], selectedId: 7, editing: 'edit' });
    await actions.save({ key: 'acme', display_name: 'Acme', entity_id: '12', active: true });
    expect(store.get().actionField).toBe('entity_id');
    const k = createContactsStore().store;
    await mount(<CustomersView state={store.get()} actions={noop} canEdit contacts={k.get()} contactsActions={noop} canReadContacts />);
    const flagged = [...host!.querySelectorAll('[aria-invalid="true"]')];
    expect(flagged).toHaveLength(1);
    expect(host!.querySelector(`label[for="${flagged[0].id}"]`)!.textContent).toContain('Entidade de atendimento');
    expect(document.getElementById(flagged[0].getAttribute('aria-errormessage')!)!.textContent).toBe('Entidade de atendimento já em uso por outro cliente ativo');
  });
  it('server 409 on the calendar lands on the contract calendar field', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => json(409, { detail: 'Contrato ativo exige calendário' })));
    const { store, actions } = createContractsStore();
    const c: Contract = { id: 2, tenant_id: 'acme', is_default: false, contractual: true, name: 'A', modality: null, status: 'active', starts_on: null, ends_on: null, calendar_id: 1, notes: null };
    store.set({ phase: 'ready', contracts: [c], selectedId: 2, detail: { ...c, policies: [], escalation_steps: [] }, editing: 'edit' });
    await actions.save({ tenant_id: 'acme', name: 'A', modality: '', starts_on: '', ends_on: '', calendar_id: '', notes: '' });
    expect(store.get().actionField).toBe('calendar_id');
    await mount(<ContractsView state={store.get()} actions={noop} canEdit />);
    expect(host!.querySelectorAll('[aria-invalid="true"]')).toHaveLength(1);
  });
  it('a validation detail list is still never rendered', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => json(422, { detail: [{ msg: 'bad', input: 'maria@x.com' }] })));
    const { store, actions } = createContactsStore();
    store.set({ editingId: 'new' });
    await actions.save({ name: 'M', email: 'maria@x.com', phone: '', role: 'TI', notify_severity_min: '3', active: true });
    expect(store.get().actionError).not.toContain('maria');
    expect(store.get().actionField).toBeNull();
  });
});

describe('P2-4 contacts are cleared when the context changes', () => {
  let seen: ContactsState;
  function Probe({ id, enabled }: { id: number | null; enabled: boolean }) {
    seen = useContacts(id, enabled).state;
    return null;
  }
  it('clears on customer change and on disable', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => json(200, [contact])));
    await mount(<Probe id={7} enabled />);
    expect(seen!.contacts).toHaveLength(1);
    await act(async () => { /* reveal */ });
    await rerender(<Probe id={7} enabled={false} />);
    expect(seen!.contacts).toEqual([]);
    expect(seen!.phase).toBe('idle');
  });
  it('a late response for the previous customer is dropped', async () => {
    let release: () => void = () => {};
    vi.stubGlobal('fetch', vi.fn(() => new Promise<Response>((r) => { release = () => r(json(200, [contact])); })));
    await mount(<Probe id={7} enabled />);
    await rerender(<Probe id={null} enabled />);
    release();
    await flush();
    expect(seen!.contacts).toEqual([]);
  });
});

describe('P3', () => {
  it('scrub caps long detail', () => {
    expect(scrub('x'.repeat(201))).toBe('Não foi possível concluir. Nada foi gravado.');
    expect(scrub('curto')).toBe('curto');
  });
  it('confirm moves focus to the confirm button, cancel returns it', async () => {
    await mount(<ConfirmButton label="Excluir" confirmLabel="Confirmar exclusão" onConfirm={() => undefined} />);
    const click = async (text: string) => {
      const b = [...host!.querySelectorAll('button')].find((x) => x.textContent === text)!;
      await act(async () => { b.click(); });
    };
    await click('Excluir');
    expect(document.activeElement?.textContent).toBe('Confirmar exclusão');
    await click('Cancelar');
    expect(document.activeElement?.textContent).toBe('Excluir');
  });
  it('skeleton has no inline style', async () => {
    await mount(<Skeleton />);
    expect(host!.querySelector('[style]')).toBeNull();
  });
});

describe('round 2 P1: draft contract -> policy -> activate', () => {
  const draft: Contract = {
    id: 9, tenant_id: 'acme', is_default: false, contractual: true, name: 'Acme', modality: 'managed',
    status: 'draft', starts_on: null, ends_on: null, calendar_id: 1, notes: null,
  };
  const cal = { id: 1, name: 'Comercial', timezone: 'America/Sao_Paulo', is_24x7: true, hours: [], holidays: [] };
  const policy = { id: 1, key: 'critico', name: 'Crítico', min_severity: 4, severity: null, has_tenant: null, ack_minutes: 15, tto_minutes: null, ttr_minutes: 240, calendar_id: null, enabled: true };

  // Servidor falso: 409 na ativação enquanto não há política habilitada, como o backend.
  function fakeApi() {
    let c = { ...draft };
    const policies: unknown[] = [];
    const calls: string[] = [];
    const f = vi.fn(async (url: string, init?: RequestInit) => {
      const m = init?.method ?? 'GET';
      calls.push(`${m} ${url}`);
      if (url.endsWith('/contracts') && m === 'POST') return json(201, c);
      if (url.endsWith('/contracts')) return json(200, [c]);
      if (url.endsWith('/modality-divergences')) return json(200, []);
      if (url.endsWith('/calendars')) return json(200, [cal]);
      if (url.includes('/policies/') && m === 'PUT') { policies.push({ ...policy, ...JSON.parse(init!.body as string) }); return json(200, policy); }
      if (url.endsWith('/status')) {
        if (!policies.length) return json(409, { detail: 'Ativar exige ao menos uma política habilitada' });
        c = { ...c, status: 'active' };
        return json(200, c);
      }
      if (url.endsWith('/contracts/9')) return json(200, { ...c, policies, escalation_steps: [] });
      return json(404, { detail: 'x' });
    });
    vi.stubGlobal('fetch', f);
    return { calls };
  }

  it('policy add then activation succeeds; 409 shows before the policy exists', async () => {
    const { calls } = fakeApi();
    const { store, actions } = createContractsStore();
    await actions.load();
    await actions.select(9);
    await expect(actions.transition(9, 'active')).resolves.toBe(false);
    expect(store.get().actionError).toBe('Ativar exige ao menos uma política habilitada');

    actions.startPolicy(null);
    await expect(actions.savePolicy({ key: 'critico', name: 'Crítico', mode: 'min', severity: '4', ack_minutes: '15', tto_minutes: '', ttr_minutes: '240', calendar_id: '', enabled: true, has_tenant: null })).resolves.toBe(true);
    const put = calls.find((c) => c.startsWith('PUT') && c.includes('/policies/critico'))!;
    expect(put).toBe('PUT /api/v1/sla/contracts/9/policies/critico');
    expect(store.get().detail?.policies).toHaveLength(1);

    await expect(actions.transition(9, 'active')).resolves.toBe(true);
    expect(store.get().detail?.status).toBe('active');
  });

  it('policy body keeps has_tenant and maps the severity class', async () => {
    const { toPolicyBody, policyToForm } = await import('./hooks/useContracts');
    const form = policyToForm({ ...policy, has_tenant: true, severity: 3, min_severity: null });
    expect(toPolicyBody(form)).toMatchObject({ severity: 3, min_severity: null, has_tenant: true, ack_minutes: 15, ttr_minutes: 240 });
    expect(toPolicyBody({ ...form, mode: 'all' })).toMatchObject({ severity: null, min_severity: null });
  });

  const withPolicyUI = (canEdit: boolean) => {
    const { store } = createContractsStore();
    store.set({ phase: 'ready', contracts: [draft], calendars: [cal], selectedId: 9, detail: { ...draft, policies: [policy], escalation_steps: [{ id: 1, position: 1, role: 'noc', enabled: true }] } });
    return renderToStaticMarkup(<ContractsView state={store.get()} actions={noop} canEdit={canEdit} />);
  };
  it('admin sees policy and step editing controls', () => {
    const html = withPolicyUI(true);
    expect(html).toMatch(/Nova política/);
    expect(html).toMatch(/Novo passo/);
    expect(html).toMatch(/Editar política Crítico/);
    expect(html).toMatch(/Editar passo 1/);
  });
  it('viewer-class (read only) sees none of them', () => {
    const html = withPolicyUI(false);
    expect(html).not.toMatch(/Nova política|Novo passo|Editar política|Editar passo|Remover/);
    expect(html).toContain('Crítico');
  });
  it('editor renders the form with labelled fields and shows the server 409', async () => {
    const { store } = createContractsStore();
    store.set({ phase: 'ready', contracts: [draft], calendars: [cal], selectedId: 9, detail: { ...draft, policies: [], escalation_steps: [] }, policyEditing: { key: null }, actionError: 'Contrato ativo exige ao menos uma política habilitada' });
    await mount(<ContractsView state={store.get()} actions={noop} canEdit />);
    const form = host!.querySelector('form[aria-label="Nova política"]')!;
    expect(form).toBeTruthy();
    for (const input of form.querySelectorAll('input, select')) expect(host!.querySelector(`label[for="${input.id}"]`)).toBeTruthy();
    expect(form.textContent).toContain('exige ao menos uma política habilitada');
  });
  it('a real contract policy is not marked non-contractual, the default one is', () => {
    expect(withPolicyUI(true)).not.toContain('não contratual');
    const d = { ...draft, id: 1, tenant_id: null, is_default: true, contractual: false, status: 'active' as const };
    const { store } = createContractsStore();
    store.set({ phase: 'ready', contracts: [d], calendars: [cal], selectedId: 1, detail: { ...d, policies: [policy], escalation_steps: [] } });
    const el = document.createElement('div');
    el.innerHTML = renderToStaticMarkup(<ContractsView state={store.get()} actions={noop} canEdit />);
    expect(el.querySelector('section[aria-label="Políticas de prazo"] .nx-badge')?.textContent).toBe('padrão interno · não contratual');
  });
});

describe('round 2 P2: refresh button reloads the new screens', () => {
  const fetchAll = () => {
    const f = vi.fn(async (url: string) => json(200, url.includes('/contacts') ? [contact] : String(url).includes('/calendars') || String(url).includes('divergences') ? [] : url.endsWith('/customers') ? [customer] : []));
    vi.stubGlobal('fetch', f);
    return f;
  };
  const count = (f: ReturnType<typeof vi.fn>, part: string) => urls(f).filter((u) => u.endsWith(part)).length;

  it('contracts reload when refreshKey changes, not when it stays', async () => {
    const f = fetchAll();
    await mount(<ContractsScreen role="admin" refreshKey={0} />);
    const before = count(f, '/api/v1/sla/contracts');
    await rerender(<ContractsScreen role="admin" refreshKey={0} />);
    expect(count(f, '/api/v1/sla/contracts')).toBe(before);
    await rerender(<ContractsScreen role="admin" refreshKey={1} />);
    expect(count(f, '/api/v1/sla/contracts')).toBe(before + 1);
  });
  it('customers and the selected customer contacts reload, keeping the selection', async () => {
    const f = fetchAll();
    await mount(<CustomersScreen role="noc" refreshKey={0} />);
    await act(async () => { [...host!.querySelectorAll('button')].find((b) => b.textContent === 'Acme')!.click(); });
    await flush();
    const c0 = count(f, '/api/customers'), k0 = count(f, '/contacts');
    await rerender(<CustomersScreen role="noc" refreshKey={1} />);
    expect(count(f, '/api/customers')).toBe(c0 + 1);
    expect(count(f, '/contacts')).toBe(k0 + 1);
    expect(host!.textContent).toContain('Contatos de aviso');
  });
  it('no reload while the role has no access', async () => {
    const f = fetchAll();
    await mount(<ContractsScreen role="viewer" refreshKey={0} />);
    await rerender(<ContractsScreen role="viewer" refreshKey={1} />);
    expect(f).not.toHaveBeenCalled();
  });
  it('App wires the header button to those screens', async () => {
    const src = (await import('./App.tsx?raw')).default;
    expect(src).toMatch(/currentView === 'contracts' \|\| currentView === 'customers'\) setCadastrosTick/);
    expect(src).toMatch(/<ContractsScreen[^>]*refreshKey=\{cadastrosTick\}/);
    expect(src).toMatch(/<CustomersScreen[^>]*refreshKey=\{cadastrosTick\}/);
  });
});
