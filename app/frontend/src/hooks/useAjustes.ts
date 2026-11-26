import { useEffect, useMemo, useRef } from 'react';
import { asApiError, describeError, request, type ApiError } from '../http';
import { createStore, useStore } from '../store';

export type ParamInfo = { value: number; default: number; max: number };
export type RuleKind = 'noise' | 'action' | 'cause';
export interface Rule { id: number; kind: RuleKind; pattern: string; note: string | null; enabled: boolean }

export interface AjustesState {
  phase: 'loading' | 'ready' | 'error';
  error: ApiError | null;
  params: Record<string, ParamInfo>;
  rules: Rule[];
  busy: boolean;
  actionError: string | null;
  notice: string | null;
}

const INITIAL: AjustesState = { phase: 'loading', error: null, params: {}, rules: [], busy: false, actionError: null, notice: null };

export function createAjustesStore() {
  const store = createStore<AjustesState>(INITIAL);

  async function load(silent = false) {
    if (!silent) store.set({ phase: 'loading', error: null });
    try {
      const [params, rules] = await Promise.all([
        request<Record<string, ParamInfo>>('/api/v1/sla/platform-params'), request<Rule[]>('/api/ticket-rules'),
      ]);
      store.set({ phase: 'ready', error: null, params, rules });
    } catch (e) {
      store.set({ phase: 'error', error: asApiError(e) });
    }
  }

  async function act(fn: () => Promise<void>, notice: string) {
    store.set({ busy: true, actionError: null, notice: null });
    try {
      await fn();
      store.set({ notice });
      await load(true);
    } catch (e) {
      store.set({ actionError: describeError(e) });
    } finally {
      store.set({ busy: false });
    }
  }

  const actions = {
    load,
    saveParam: (key: string, value: number) => act(
      async () => { await request(`/api/v1/sla/platform-params/${key}`, { method: 'PUT', body: { value } }); }, 'Ajuste salvo.'),
    addRule: (kind: RuleKind, pattern: string, note: string) => act(
      async () => { await request('/api/ticket-rules', { method: 'POST', body: { kind, pattern: pattern.trim(), note: note.trim() || null } }); }, 'Regra adicionada.'),
    toggleRule: (id: number, enabled: boolean) => act(
      async () => { await request(`/api/ticket-rules/${id}`, { method: 'PATCH', body: { enabled } }); }, enabled ? 'Regra ligada.' : 'Regra desligada.'),
    removeRule: (id: number) => act(
      async () => { await request(`/api/ticket-rules/${id}`, { method: 'DELETE' }); }, 'Regra removida.'),
  };
  return { store, actions };
}

export type AjustesActions = ReturnType<typeof createAjustesStore>['actions'];

export function useAjustes(enabled: boolean, refreshKey = 0) {
  const { store, actions } = useMemo(createAjustesStore, []);
  useEffect(() => { if (enabled) void actions.load(); }, [enabled, actions]);
  const first = useRef(refreshKey);
  useEffect(() => {
    if (enabled && refreshKey !== first.current) { first.current = refreshKey; void actions.load(true); }
  }, [enabled, refreshKey, actions]);
  return { state: useStore(store), actions };
}
