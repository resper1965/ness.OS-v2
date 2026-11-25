import { useEffect, useMemo, useRef } from 'react';
import { asApiError, describeError, request, type ApiError } from '../http';
import { createStore, useStore } from '../store';
import type { Customer } from './useCustomers';

export interface Person {
  id: number; email: string; full_name: string | null; kind: 'ness' | 'externo'; role: string;
  customer_ids: number[]; is_oncall: boolean; is_active: boolean;
}
export interface PendingLogin { issuer: string; subject: string; email: string | null; attempts: number; last_seen: string }
export interface PersonForm { email: string; full_name: string; kind: 'ness' | 'externo'; customer_ids: number[]; is_oncall: boolean; is_active: boolean }

export interface PeopleState {
  phase: 'loading' | 'ready' | 'error';
  error: ApiError | null;
  people: Person[];
  customers: Customer[];
  editing: number | 'new' | null;
  busy: boolean;
  actionError: string | null;
  notice: string | null;
  pending: PendingLogin[];
  canLink: boolean;
  diff: string[] | null; // simulação da reconciliação com o GLPI; null = ainda não verificada
}

const INITIAL: PeopleState = {
  phase: 'loading', error: null, people: [], customers: [], editing: null, busy: false, actionError: null, notice: null, pending: [], canLink: false, diff: null,
};

export function createPeopleStore() {
  const store = createStore<PeopleState>(INITIAL);

  async function load(silent = false) {
    if (!silent) store.set({ phase: 'loading', error: null });
    try {
      const [people, customers] = await Promise.all([request<Person[]>('/api/people'), request<Customer[]>('/api/customers')]);
      // Só platform_admin lista e vincula; para os demais a fila fica vazia, sem erro.
      const pending = await request<PendingLogin[]>('/api/auth/pending').then((p) => ({ p, ok: true }), (e) => {
        if (asApiError(e).status === 403) return { p: [] as PendingLogin[], ok: false };
        throw e;
      });
      store.set({ phase: 'ready', error: null, people, customers, pending: pending.p, canLink: pending.ok });
    } catch (e) {
      store.set({ phase: 'error', error: asApiError(e) });
    }
  }

  async function act(fn: () => Promise<void>, notice: string): Promise<boolean> {
    store.set({ busy: true, actionError: null, notice: null });
    try {
      await fn();
      store.set({ notice, diff: null });
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
    startEdit: (id: number | 'new') => store.set({ editing: id, actionError: null, notice: null }),
    cancelEdit: () => store.set({ editing: null, actionError: null }),
    async save(f: PersonForm) {
      const editing = store.get().editing;
      const ok = await act(async () => {
        if (editing === 'new') {
          await request('/api/people', { method: 'POST', body: {
            email: f.email.trim(), full_name: f.full_name.trim(), kind: f.kind, customer_ids: f.customer_ids, is_oncall: f.is_oncall,
          } });
        } else {
          // Só envia o que mudou: cliente que ficou inativo continua na equipe e não pode travar a edição do nome.
          const cur = store.get().people.find((p) => p.id === editing);
          const same = (a: number[], b: number[]) => a.length === b.length && [...a].sort().every((x, i) => x === [...b].sort()[i]);
          await request(`/api/people/${editing}`, { method: 'PUT', body: {
            full_name: f.full_name.trim(), is_active: f.is_active,
            // Mudou a equipe: manda só clientes que a API aceita; vínculo obsoleto (inativo/sem entidade) cai aqui.
            ...(cur && same(cur.customer_ids, f.customer_ids) ? {} : { customer_ids: f.customer_ids.filter((id) => store.get().customers.some((c) => c.id === id && c.active && c.glpi_entity_id !== null)) }),
            ...(cur && cur.is_oncall === f.is_oncall ? {} : { is_oncall: f.is_oncall }),
          } });
        }
      }, editing === 'new' ? 'Pessoa cadastrada. O acesso é liberado no próximo ciclo.' : 'Pessoa salva.');
      if (!ok) return false;
      store.set({ editing: null });
      await load(true);
      return true;
    },
    async deactivate(id: number) {
      const ok = await act(async () => { await request(`/api/people/${id}`, { method: 'DELETE' }); }, 'Pessoa desativada.');
      if (ok) await load(true);
      return ok;
    },
    async link(p: PendingLogin, userId: number) {
      const ok = await act(async () => {
        await request('/api/auth/pending/link', { method: 'POST', body: { issuer: p.issuer, subject: p.subject, user_id: userId } });
      }, 'Login vinculado. A pessoa já pode entrar.');
      if (ok) await load(true);
      return ok;
    },
    // Só simula: mostra o que o GLPI ainda não reflete.
    async checkSync() {
      store.set({ busy: true, actionError: null, notice: null });
      try {
        const r = await request<{ diff: string[] }>('/api/people/sync');
        store.set({ diff: r.diff });
      } catch (e) {
        store.set({ actionError: describeError(e), diff: null });
      } finally {
        store.set({ busy: false });
      }
    },
  };
  return { store, actions };
}

export type PeopleActions = ReturnType<typeof createPeopleStore>['actions'];

export function usePeople(enabled: boolean, refreshKey = 0) {
  const { store, actions } = useMemo(createPeopleStore, []);
  useEffect(() => { if (enabled) void actions.load(); }, [enabled, actions]);
  const first = useRef(refreshKey);
  useEffect(() => {
    if (enabled && refreshKey !== first.current) { first.current = refreshKey; void actions.load(true); }
  }, [enabled, refreshKey, actions]);
  return { state: useStore(store), actions };
}
