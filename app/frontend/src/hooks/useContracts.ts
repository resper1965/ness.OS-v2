import { useEffect, useMemo } from 'react';
import { asApiError, describeError, request, type ApiError } from '../http';
import { createStore, useStore } from '../store';

export type Modality = 'managed' | 'onsite' | 'shared';
export type ContractStatus = 'draft' | 'active' | 'suspended' | 'ended';

export interface Contract {
  id: number;
  tenant_id: string | null;
  is_default: boolean;
  contractual: boolean;
  name: string;
  modality: Modality | null;
  status: ContractStatus;
  starts_on: string | null;
  ends_on: string | null;
  calendar_id: number | null;
  notes: string | null;
  updated_at?: string | null;
}
export interface Policy {
  id: number; key: string; name: string; min_severity: number | null; severity: number | null;
  has_tenant: boolean | null; ack_minutes: number; tto_minutes: number | null; ttr_minutes: number | null;
  calendar_id: number | null; enabled: boolean;
}
export interface Step { id: number; position: number; role: string; enabled: boolean }
export interface ContractDetail extends Contract { policies: Policy[]; escalation_steps: Step[] }
export interface CalendarHours { id: number; weekday: number; start_time: string; end_time: string }
export interface Holiday { id: number; holiday_date: string; name: string }
export interface Calendar {
  id: number; name: string; timezone: string; is_24x7: boolean; hours: CalendarHours[]; holidays: Holiday[];
}
export interface Divergence { tenant_id: string; contract_modality: Modality; mapping_modality: Modality | null }

export interface ContractForm {
  tenant_id: string; name: string; modality: '' | Modality; starts_on: string; ends_on: string;
  calendar_id: string; notes: string;
}

// Valor vindo do padrão interno ou sem marca contratual nunca é tratado como contratual.
export const isNonContractual = (c: Pick<Contract, 'is_default' | 'contractual'>) => c.is_default || !c.contractual;

export const TRANSITIONS: Record<ContractStatus, ContractStatus[]> = {
  draft: ['active', 'ended'], active: ['suspended', 'ended'], suspended: ['active', 'ended'], ended: [],
};

export interface ContractsState {
  phase: 'loading' | 'ready' | 'error';
  error: ApiError | null;
  contracts: Contract[];
  divergences: Divergence[];
  calendars: Calendar[];
  selectedId: number | null;
  detail: ContractDetail | null;
  detailLoading: boolean;
  detailError: ApiError | null;
  editing: 'new' | 'edit' | null;
  busy: boolean;
  actionError: string | null;
  actionField: ContractField | null;
  notice: string | null;
}

const INITIAL: ContractsState = {
  phase: 'loading', error: null, contracts: [], divergences: [], calendars: [], selectedId: null, detail: null,
  detailLoading: false, detailError: null, editing: null, busy: false, actionError: null, actionField: null, notice: null,
};

export type ContractField = 'calendar_id' | 'ends_on';
// Mensagens conhecidas do servidor ligadas a um campo; o resto fica no alerta geral.
export function contractFieldOf(message: string): ContractField | null {
  if (/calendário/i.test(message)) return 'calendar_id';
  if (/starts_on deve ser/.test(message)) return 'ends_on';
  return null;
}

const BASE = '/api/v1/sla';
const orNull = (v: string) => (v.trim() === '' ? null : v.trim());

export function toPayload(f: ContractForm, creating: boolean) {
  const body = {
    name: f.name.trim(),
    modality: f.modality || null,
    starts_on: orNull(f.starts_on),
    ends_on: orNull(f.ends_on),
    calendar_id: f.calendar_id ? Number(f.calendar_id) : null,
    notes: orNull(f.notes),
  };
  return creating ? { tenant_id: f.tenant_id.trim().toLowerCase(), ...body } : body;
}

export function createContractsStore() {
  const store = createStore<ContractsState>(INITIAL);
  let detailSeq = 0;

  async function load(silent = false) {
    if (!silent) store.set({ phase: 'loading', error: null });
    try {
      const [contracts, divergences, calendars] = await Promise.all([
        request<Contract[]>(`${BASE}/contracts`),
        request<Divergence[]>(`${BASE}/contracts/modality-divergences`),
        request<Calendar[]>(`${BASE}/calendars`),
      ]);
      store.set({ phase: 'ready', error: null, contracts, divergences, calendars });
    } catch (e) {
      store.set({ phase: 'error', error: asApiError(e) });
    }
  }

  async function loadDetail(id: number) {
    const seq = ++detailSeq;
    store.set({ selectedId: id, detailLoading: true, detailError: null });
    try {
      const detail = await request<ContractDetail>(`${BASE}/contracts/${id}`);
      if (seq === detailSeq) store.set({ detail, detailLoading: false });
    } catch (e) {
      if (seq === detailSeq) store.set({ detail: null, detailLoading: false, detailError: asApiError(e) });
    }
  }

  // 409/422 do servidor chegam como mensagem pronta em `actionError`.
  async function act(fn: () => Promise<void>, notice: string, fieldOf?: (m: string) => ContractField | null): Promise<boolean> {
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

  const refreshSelected = async () => {
    await load(true);
    const id = store.get().selectedId;
    if (id !== null) await loadDetail(id);
  };

  const actions = {
    load,
    select: (id: number) => {
      store.set({ editing: null, actionError: null, notice: null });
      return loadDetail(id);
    },
    startCreate: () => store.set({ editing: 'new', actionError: null, notice: null }),
    startEdit: () => store.set({ editing: 'edit', actionError: null, notice: null }),
    cancelEdit: () => store.set({ editing: null, actionError: null }),
    async save(form: ContractForm) {
      const creating = store.get().editing === 'new';
      const id = store.get().selectedId;
      let created: Contract | null = null;
      const ok = await act(async () => {
        if (creating) {
          created = await request<Contract>(`${BASE}/contracts`, { method: 'POST', body: toPayload(form, true) });
        } else {
          await request(`${BASE}/contracts/${id}`, { method: 'PUT', body: toPayload(form, false) });
        }
      }, creating ? 'Contrato criado como rascunho.' : 'Contrato salvo.', contractFieldOf);
      if (!ok) return false;
      store.set({ editing: null });
      if (created) store.set({ selectedId: (created as Contract).id });
      await refreshSelected();
      return true;
    },
    async transition(id: number, status: ContractStatus) {
      const ok = await act(async () => {
        await request(`${BASE}/contracts/${id}/status`, { method: 'POST', body: { status } });
      }, 'Status atualizado.');
      if (ok) await refreshSelected();
      return ok;
    },
  };

  return { store, actions };
}

export type ContractsActions = ReturnType<typeof createContractsStore>['actions'];

export function useContracts(enabled: boolean) {
  const { store, actions } = useMemo(createContractsStore, []);
  useEffect(() => { if (enabled) void actions.load(); }, [enabled, actions]);
  return { state: useStore(store), actions };
}
