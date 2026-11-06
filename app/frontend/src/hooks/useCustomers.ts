import { useEffect, useMemo } from 'react';
import { asApiError, describeError, request, type ApiError } from '../http';
import { createStore, useStore } from '../store';

export interface Customer {
  id: number; key: string; display_name: string; glpi_entity_id: number | null; active: boolean; aliases: string[];
}
export interface Contact {
  id: number; customer_id: number; name: string; email: string; phone: string | null; role: string;
  notify_severity_min: number; active: boolean;
}
export interface CustomerForm { key: string; display_name: string; entity_id: string; active: boolean }
export interface ContactForm {
  name: string; email: string; phone: string; role: string; notify_severity_min: string; active: boolean;
}

export const normAlias = (s: string) => s.toLowerCase().trim();
export const isCanonicalAlias = (c: Customer, alias: string) =>
  [c.display_name, c.key].some((n) => normAlias(n) === normAlias(alias));

// ---------- clientes ----------
export type CustomerField = 'entity_id' | 'display_name' | 'key' | 'alias';
export function customerFieldOf(message: string): CustomerField | null {
  if (/^Entidade/.test(message)) return 'entity_id';
  if (/^Nome já/.test(message)) return 'display_name';
  if (/^Chave ou apelido/.test(message)) return 'key';
  return null;
}

export interface CustomersState {
  phase: 'loading' | 'ready' | 'error';
  error: ApiError | null;
  customers: Customer[];
  selectedId: number | null;
  editing: 'new' | 'edit' | null;
  busy: boolean;
  actionError: string | null;
  actionField: CustomerField | null;
  notice: string | null;
}

const INITIAL: CustomersState = {
  phase: 'loading', error: null, customers: [], selectedId: null, editing: null, busy: false, actionError: null, actionField: null, notice: null,
};

export function createCustomersStore() {
  const store = createStore<CustomersState>(INITIAL);

  async function load(silent = false) {
    if (!silent) store.set({ phase: 'loading', error: null });
    try {
      store.set({ phase: 'ready', error: null, customers: await request<Customer[]>('/api/customers') });
    } catch (e) {
      store.set({ phase: 'error', error: asApiError(e) });
    }
  }

  async function act(fn: () => Promise<void>, notice: string, fieldOf?: (m: string) => CustomerField | null): Promise<boolean> {
    store.set({ busy: true, actionError: null, actionField: null, notice: null });
    try {
      await fn();
      store.set({ notice });
      return true;
    } catch (e) {
      const actionError = describeError(e);
      store.set({ actionError, actionField: fieldOf ? fieldOf(actionError) : null });
      return false;
    } finally {
      store.set({ busy: false });
    }
  }

  // O servidor devolve o cliente atualizado: troca na lista sem novo GET.
  const replace = (c: Customer) =>
    store.set({ customers: store.get().customers.map((x) => (x.id === c.id ? c : x)) });

  const actions = {
    load,
    select: (id: number) => store.set({ selectedId: id, editing: null, actionError: null, notice: null }),
    startCreate: () => store.set({ editing: 'new', actionError: null, notice: null }),
    startEdit: () => store.set({ editing: 'edit', actionError: null, notice: null }),
    cancelEdit: () => store.set({ editing: null, actionError: null }),
    async save(form: CustomerForm) {
      const creating = store.get().editing === 'new';
      const id = store.get().selectedId;
      const entity = form.entity_id.trim() === '' ? null : Number(form.entity_id);
      let saved: Customer | null = null;
      const ok = await act(async () => {
        saved = creating
          ? await request<Customer>('/api/customers', {
              method: 'POST',
              body: { key: form.key.trim(), display_name: form.display_name.trim(), glpi_entity_id: entity, active: form.active },
            })
          : await request<Customer>(`/api/customers/${id}`, {
              method: 'PUT',
              body: { display_name: form.display_name.trim(), glpi_entity_id: entity, active: form.active },
            });
      }, creating ? 'Cliente criado.' : 'Cliente salvo.', customerFieldOf);
      if (!ok) return false;
      store.set({ editing: null });
      await load(true);
      if (saved) store.set({ selectedId: (saved as Customer).id });
      return true;
    },
    async addAlias(id: number, alias: string) {
      return act(async () => {
        replace(await request<Customer>(`/api/customers/${id}/aliases`, { method: 'POST', body: { alias: alias.trim() } }));
      }, 'Apelido adicionado.', () => 'alias');
    },
    // O apelido canônico volta 422: a mensagem do servidor é exibida como está.
    async removeAlias(id: number, alias: string) {
      return act(async () => {
        replace(await request<Customer>(`/api/customers/${id}/aliases?alias=${encodeURIComponent(alias)}`, { method: 'DELETE' }));
      }, 'Apelido removido.');
    },
  };
  return { store, actions };
}

export type CustomersActions = ReturnType<typeof createCustomersStore>['actions'];

export function useCustomers(enabled: boolean) {
  const { store, actions } = useMemo(createCustomersStore, []);
  useEffect(() => { if (enabled) void actions.load(); }, [enabled, actions]);
  return { state: useStore(store), actions };
}

// ---------- contatos (dado pessoal) ----------
export interface ContactsState {
  phase: 'idle' | 'loading' | 'ready' | 'error';
  error: ApiError | null;
  contacts: Contact[];
  revealed: number[]; // ids com e-mail/telefone visíveis; vazio por padrão e ao trocar de cliente
  editingId: number | 'new' | null;
  busy: boolean;
  actionError: string | null;
  actionField: null; // erros de contato não trazem campo: o 422 do validador ecoa o valor e nunca é exibido
  notice: string | null;
}

export const CONTACTS_INITIAL: ContactsState = {
  phase: 'idle', error: null, contacts: [], revealed: [], editingId: null, busy: false, actionError: null, actionField: null, notice: null,
};

// Dado pessoal: sem log, sem query string; o corpo só vai no JSON da requisição.
const toBody = (f: ContactForm) => ({
  name: f.name.trim(), email: f.email.trim(), phone: f.phone.trim() || null, role: f.role.trim(),
  notify_severity_min: Number(f.notify_severity_min), active: f.active,
});

export function createContactsStore() {
  const store = createStore<ContactsState>(CONTACTS_INITIAL);
  let customerId: number | null = null;
  const url = (id?: number) => `/api/customers/${customerId}/contacts${id ? `/${id}` : ''}`;

  async function load(id: number) {
    customerId = id;
    store.set({ ...CONTACTS_INITIAL, phase: 'loading' });
    try {
      const contacts = await request<Contact[]>(url());
      if (customerId === id) store.set({ phase: 'ready', contacts });
    } catch (e) {
      if (customerId === id) store.set({ phase: 'error', error: asApiError(e) });
    }
  }

  async function act(fn: () => Promise<void>, notice: string): Promise<boolean> {
    store.set({ busy: true, actionError: null, actionField: null, notice: null });
    try {
      await fn();
      store.set({ notice });
      return true;
    } catch (e) {
      store.set({ actionError: describeError(e) });
      return false;
    } finally {
      store.set({ busy: false });
    }
  }

  const actions = {
    load,
    // Troca de cliente ou perda de permissão: dado pessoal sai da memória e respostas atrasadas são descartadas.
    reset() {
      customerId = null;
      store.set(CONTACTS_INITIAL);
    },
    toggleReveal(id: number) {
      const { revealed } = store.get();
      store.set({ revealed: revealed.includes(id) ? revealed.filter((x) => x !== id) : [...revealed, id] });
    },
    startEdit: (id: number | 'new') => store.set({ editingId: id, actionError: null, notice: null }),
    cancelEdit: () => store.set({ editingId: null, actionError: null }),
    async save(form: ContactForm) {
      const editing = store.get().editingId;
      const ok = await act(async () => {
        if (editing === 'new') await request(url(), { method: 'POST', body: toBody(form) });
        else await request(url(editing as number), { method: 'PUT', body: toBody(form) });
      }, editing === 'new' ? 'Contato criado.' : 'Contato salvo.');
      if (!ok || customerId === null) return false;
      store.set({ editingId: null });
      try {
        store.set({ contacts: await request<Contact[]>(url()) });
      } catch (e) {
        store.set({ actionError: describeError(e) });
      }
      return true;
    },
    async remove(id: number) {
      const ok = await act(async () => { await request(url(id), { method: 'DELETE' }); }, 'Contato excluído.');
      if (ok) store.set({ contacts: store.get().contacts.filter((c) => c.id !== id) });
      return ok;
    },
  };
  return { store, actions };
}

export type ContactsActions = ReturnType<typeof createContactsStore>['actions'];

export function useContacts(customerId: number | null, enabled: boolean) {
  const { store, actions } = useMemo(createContactsStore, []);
  useEffect(() => {
    if (!enabled || customerId === null) return;
    void actions.load(customerId);
    return actions.reset;
  }, [enabled, customerId, actions]);
  return { state: useStore(store), actions };
}
