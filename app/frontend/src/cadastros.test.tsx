import { renderToStaticMarkup } from 'react-dom/server';
import { afterEach, describe, expect, it, vi } from 'vitest';
import ContractsScreen from './components/ContractsScreen';
import CustomersScreen from './components/CustomersScreen';
import ContractsView from './components/contracts/ContractsView';
import CustomersView from './components/customers/CustomersView';
import { ApiError, scrub } from './http';
import { maskEmail, maskPhone } from './format';
import { createContactsStore, type Contact } from './hooks/useCustomers';
import { createContractsStore, type Contract, type ContractDetail } from './hooks/useContracts';
import { createCustomersStore, type Customer } from './hooks/useCustomers';

afterEach(() => vi.unstubAllGlobals());

const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } });
const stubFetch = (fn: (url: string, init?: RequestInit) => Response) =>
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => fn(url, init)));

const text = (html: string) => html.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ');

const std: Contract = {
  id: 2, tenant_id: 'acme', is_default: false, contractual: true, name: 'Acme gerenciado', modality: 'managed',
  status: 'active', starts_on: '2026-01-01', ends_on: null, calendar_id: 1, notes: null,
};
const dflt: Contract = { ...std, id: 1, tenant_id: null, is_default: true, contractual: false, name: 'Padrão interno' };
const detail = (c: Contract): ContractDetail => ({
  ...c,
  policies: [{ id: 1, key: 'p1', name: 'Crítico', min_severity: 4, severity: null, has_tenant: null, ack_minutes: 15, tto_minutes: null, ttr_minutes: 240, calendar_id: null, enabled: true }],
  escalation_steps: [{ id: 1, position: 1, role: 'noc', enabled: true }],
});
const calendars = [{ id: 1, name: 'Comercial', timezone: 'America/Sao_Paulo', is_24x7: false, hours: [{ id: 1, weekday: 0, start_time: '08:00:00', end_time: '18:00:00' }], holidays: [] }];

function contractsState(over = {}) {
  const { store } = createContractsStore();
  store.set({ phase: 'ready', contracts: [dflt, std], calendars, divergences: [{ tenant_id: 'acme', contract_modality: 'managed', mapping_modality: null }], ...over });
  return store.get();
}
const noop = new Proxy({}, { get: () => () => undefined }) as never;

const customer: Customer = { id: 7, key: 'acme', display_name: 'Acme', glpi_entity_id: 12, active: true, aliases: ['acme', 'acme sa'] };
const contact: Contact = { id: 3, customer_id: 7, name: 'Maria Souza', email: 'maria.souza@acme.com.br', phone: '+55 11 91234-5678', role: 'TI', notify_severity_min: 3, active: true };

function customersMarkup(canEdit = true, contactsOver = {}) {
  const c = createCustomersStore().store;
  c.set({ phase: 'ready', customers: [customer], selectedId: 7 });
  const k = createContactsStore().store;
  k.set({ phase: 'ready', contacts: [contact], ...contactsOver });
  return renderToStaticMarkup(
    <CustomersView state={c.get()} actions={noop} canEdit={canEdit} contacts={k.get()} contactsActions={noop} canReadContacts />,
  );
}

describe('test_contract_form_blocks_viewer', () => {
  it.each(['viewer', 'cliente', 'gestao', undefined])('%s sees no contract data nor controls', (role) => {
    const fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);
    const html = renderToStaticMarkup(<ContractsScreen role={role} />);
    expect(text(html)).toContain('não acessa contratos');
    expect(html).not.toMatch(/Novo contrato|<form|<table/);
    expect(fetchMock).not.toHaveBeenCalled();
  });
  it('operator and noc read but get no edit controls', () => {
    const state = contractsState({ selectedId: 2, detail: detail(std) });
    const html = renderToStaticMarkup(<ContractsView state={state} actions={noop} canEdit={false} />);
    expect(html).toContain('Acme gerenciado');
    expect(html).not.toMatch(/Novo contrato|Editar|Suspender|Encerrar/);
  });
  it('admin gets edit controls and transitions', () => {
    const state = contractsState({ selectedId: 2, detail: detail(std) });
    const html = renderToStaticMarkup(<ContractsView state={state} actions={noop} canEdit />);
    expect(html).toMatch(/Novo contrato/);
    expect(html).toMatch(/Suspender/);
  });
  it('shows server 409 messages for forbidden transitions', async () => {
    stubFetch(() => json(409, { detail: 'Ativar exige calendário' }));
    const { store, actions } = createContractsStore();
    await expect(actions.transition(2, 'active')).resolves.toBe(false);
    expect(store.get().actionError).toBe('Ativar exige calendário');
    const html = renderToStaticMarkup(<ContractsView state={{ ...contractsState(), actionError: store.get().actionError }} actions={noop} canEdit />);
    expect(text(html)).toContain('Ativar exige calendário');
  });
});

describe('test_default_contract_marked_non_contractual', () => {
  it('flags the default contract in list, detail, policies, escalation and calendar', () => {
    const html = renderToStaticMarkup(
      <ContractsView state={contractsState({ selectedId: 1, detail: detail(dflt) })} actions={noop} canEdit />,
    );
    expect(html.split('padrão interno · não contratual').length - 1).toBeGreaterThanOrEqual(5);
    expect(text(html)).toContain('Não são contratuais');
  });
  it('does not flag a real contract', () => {
    const html = renderToStaticMarkup(
      <ContractsView state={contractsState({ contracts: [std], selectedId: 2, detail: detail(std) })} actions={noop} canEdit />,
    );
    expect(html).not.toContain('não contratual');
  });
  it('contractual=false from the API is non-contractual even without is_default', () => {
    const odd = { ...std, contractual: false };
    const html = renderToStaticMarkup(<ContractsView state={contractsState({ contracts: [odd] })} actions={noop} canEdit />);
    expect(html).toContain('não contratual');
  });
});

describe('test_canonical_alias_removal_shows_message', () => {
  it('surfaces the 422 text from the server and keeps the alias', async () => {
    stubFetch(() => json(422, { detail: 'Apelido canônico não pode ser removido' }));
    const { store, actions } = createCustomersStore();
    store.set({ phase: 'ready', customers: [customer], selectedId: 7 });
    await expect(actions.removeAlias(7, 'acme')).resolves.toBe(false);
    expect(store.get().customers[0].aliases).toContain('acme');
    const c = createContactsStore().store;
    const html = renderToStaticMarkup(
      <CustomersView state={store.get()} actions={noop} canEdit contacts={c.get()} contactsActions={noop} canReadContacts />,
    );
    expect(text(html)).toContain('Apelido canônico não pode ser removido');
    expect(html).toContain('canônico');
  });
  it('sends the alias in the query, never contact data', async () => {
    const f = vi.fn((_url: string) => json(200, { ...customer, aliases: ['acme'] }));
    stubFetch(f);
    const { actions } = createCustomersStore();
    await actions.removeAlias(7, 'acme sa');
    expect(f.mock.calls[0][0]).toBe('/api/customers/7/aliases?alias=acme%20sa');
  });
  it('shows the 409 for a duplicate entity id with neutral wording', async () => {
    stubFetch(() => json(409, { detail: 'Entidade GLPI já em uso' }));
    const { store, actions } = createCustomersStore();
    store.set({ editing: 'edit', selectedId: 7, customers: [customer] });
    await expect(actions.save({ key: 'acme', display_name: 'Acme', entity_id: '12', active: true })).resolves.toBe(false);
    expect(store.get().actionError).toBe('Entidade de atendimento já em uso por outro cliente ativo');
  });
});

describe('test_contact_pii_masked_by_default', () => {
  it('masks email and phone until revealed', () => {
    const html = customersMarkup();
    expect(html).not.toContain('maria.souza@acme.com.br');
    expect(html).not.toContain('91234-5678');
    expect(html).toContain(maskEmail(contact.email));
    expect(html).toContain(maskPhone(contact.phone as string));
    expect(html).toContain('aria-pressed="false"');
  });
  it('reveals only the chosen contact', () => {
    const html = customersMarkup(true, { revealed: [3] });
    expect(html).toContain('maria.souza@acme.com.br');
    expect(html).toContain('aria-pressed="true"');
  });
  it('never logs PII, never puts it in a URL, and hides it again on customer change', async () => {
    const log = vi.spyOn(console, 'log');
    const err = vi.spyOn(console, 'error');
    const f = vi.fn((_url: string, init?: RequestInit) =>
      init?.method === 'POST' ? json(201, contact) : json(200, [contact]));
    stubFetch(f);
    const { store, actions } = createContactsStore();
    await actions.load(7);
    actions.toggleReveal(3);
    store.set({ editingId: 'new' });
    await actions.save({ name: contact.name, email: contact.email, phone: contact.phone as string, role: 'TI', notify_severity_min: '3', active: true });
    for (const [url] of f.mock.calls) expect(String(url)).not.toMatch(/maria|acme\.com|91234|@/);
    expect(log).not.toHaveBeenCalled();
    expect(err).not.toHaveBeenCalled();
    await actions.load(8);
    expect(store.get().revealed).toEqual([]);
  });
  it('does not echo validation detail (it may repeat the e-mail) in errors', async () => {
    stubFetch(() => json(422, { detail: [{ msg: 'value is not a valid email', input: 'maria@x' }] }));
    const { store, actions } = createContactsStore();
    store.set({ editingId: 'new' });
    await actions.save({ name: 'M', email: 'maria@x', phone: '', role: 'TI', notify_severity_min: '3', active: true });
    expect(store.get().actionError).toBe('Dados inválidos. Revise os campos.');
  });
  it('masks helpers keep the shape without the value', () => {
    expect(maskEmail('a.b@dom.com')).toBe('a***@d***.com');
    expect(maskPhone('11912345678')).toBe('*********78');
  });
});

describe('test_no_vendor_name_in_ui', () => {
  const VENDORS = /zabbix|wazuh|glpi|action1|resend|authentik/i;
  it('renders no vendor name in any state of either screen', () => {
    const pages = [
      renderToStaticMarkup(<ContractsView state={contractsState({ selectedId: 1, detail: detail(dflt) })} actions={noop} canEdit />),
      renderToStaticMarkup(<ContractsView state={contractsState({ editing: 'new' })} actions={noop} canEdit />),
      renderToStaticMarkup(<ContractsView state={contractsState({ phase: 'error', error: new ApiError(500, scrub('falha no Zabbix')) })} actions={noop} canEdit />),
      renderToStaticMarkup(<ContractsView state={contractsState({ phase: 'loading' })} actions={noop} canEdit />),
      renderToStaticMarkup(<ContractsScreen role="viewer" />),
      renderToStaticMarkup(<CustomersScreen role="viewer" />),
      customersMarkup(),
      customersMarkup(true, { editingId: 'new' }),
    ];
    for (const html of pages) expect(html).not.toMatch(VENDORS);
  });
  it('scrubs vendor names from server messages', () => {
    expect(scrub('Falha no Wazuh e no Resend')).not.toMatch(VENDORS);
    expect(scrub('Entidade GLPI ou nome já em uso')).not.toMatch(VENDORS);
  });
});

describe('test_403_renders_message', () => {
  it('contracts: 403 from the API shows the role message, not a blank page', async () => {
    stubFetch(() => json(403, { detail: 'Acesso restrito a operadores' }));
    const { store, actions } = createContractsStore();
    await actions.load();
    expect(store.get().phase).toBe('error');
    const html = renderToStaticMarkup(<ContractsView state={store.get()} actions={noop} canEdit={false} />);
    expect(text(html)).toContain('Seu papel não tem permissão');
    expect(html).toContain('role="alert"');
    expect(html).not.toContain('Tentar de novo');
  });
  it('customers: contacts 403 shows the message', async () => {
    stubFetch(() => json(403, { detail: 'Acesso restrito a operadores NOC/SOC' }));
    const { store, actions } = createContactsStore();
    await actions.load(7);
    const c = createCustomersStore().store;
    c.set({ phase: 'ready', customers: [customer], selectedId: 7 });
    const html = renderToStaticMarkup(
      <CustomersView state={c.get()} actions={noop} canEdit={false} contacts={store.get()} contactsActions={noop} canReadContacts />,
    );
    expect(text(html)).toContain('Seu papel não tem permissão');
  });
  it('network failure is explicit', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => { throw new TypeError('x'); }));
    const { store, actions } = createCustomersStore();
    await actions.load();
    expect(store.get().error?.message).toMatch(/Sem conexão/);
  });
});
