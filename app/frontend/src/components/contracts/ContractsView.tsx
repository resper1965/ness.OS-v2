import { useState } from 'react';
import { CircleCheck, CircleDashed, CirclePause, CircleX, Pencil, Plus, ScrollText, Save, X } from 'lucide-react';
import { fmtDate, fmtDateTime, fmtTime, MODALITY, ROLE, STATUS, WEEKDAY } from '../../format';
import {
  isNonContractual, TRANSITIONS, type Calendar, type Contract, type ContractDetail, type ContractForm,
  type ContractField, type ContractsActions, type ContractsState, type ContractStatus,
} from '../../hooks/useContracts';
import {
  Alert, AreaField, Badge, Button, ConfirmButton, Empty, ErrorState, ICON, Panel, PageHeader, SelectField,
  Skeleton, TextField, type Tone,
} from '../ui/kit';

export const NON_CONTRACTUAL = 'padrão interno · não contratual';

const STATUS_VIEW: Record<ContractStatus, { tone: Tone; icon: typeof CircleCheck }> = {
  draft: { tone: 'neutral', icon: CircleDashed },
  active: { tone: 'ok', icon: CircleCheck },
  suspended: { tone: 'warn', icon: CirclePause },
  ended: { tone: 'neutral', icon: CircleX },
};
const TRANSITION_LABEL: Record<ContractStatus, string> = {
  draft: 'Voltar a rascunho', active: 'Ativar', suspended: 'Suspender', ended: 'Encerrar',
};

export const StatusBadge = ({ status }: { status: ContractStatus }) => {
  const v = STATUS_VIEW[status];
  return <Badge tone={v.tone} icon={v.icon}>{STATUS[status]}</Badge>;
};

export const NonContractualBadge = () => <Badge tone="warn">{NON_CONTRACTUAL}</Badge>;

const vigencia = (c: Contract) =>
  c.starts_on || c.ends_on ? `${fmtDate(c.starts_on)} a ${c.ends_on ? fmtDate(c.ends_on) : 'sem fim'}` : '—';

const sevText = (p: { min_severity: number | null; severity: number | null }) =>
  p.severity !== null ? `= ${p.severity}` : p.min_severity !== null ? `≥ ${p.min_severity}` : 'todas';
const minutes = (v: number | null) => (v === null ? '—' : `${v} min`);

function Divergences({ state }: { state: ContractsState }) {
  return (
    <Panel title="Divergências de modalidade" meta={<Badge tone={state.divergences.length ? 'warn' : 'ok'}>{state.divergences.length}</Badge>} flush>
      {state.divergences.length === 0 ? (
        <Empty title="Contrato ativo e mapeamento de monitoramento estão de acordo." />
      ) : (
        <table className="nx-table">
          <caption className="sr-only">Contratos ativos cuja modalidade difere do mapeamento</caption>
          <thead><tr><th scope="col">Cliente</th><th scope="col">Contrato</th><th scope="col">Mapeamento</th></tr></thead>
          <tbody>
            {state.divergences.map((d, i) => (
              <tr key={`${d.tenant_id}-${i}`}>
                <td className="nx-mono">{d.tenant_id}</td>
                <td>{MODALITY[d.contract_modality]}</td>
                <td>{d.mapping_modality ? MODALITY[d.mapping_modality] : 'Sem modalidade'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Panel>
  );
}

function List({ state, actions }: { state: ContractsState; actions: ContractsActions }) {
  if (state.contracts.length === 0) {
    return <Empty title="Nenhum contrato cadastrado." hint="Um contrato novo nasce como rascunho e só vale depois de ativado." />;
  }
  return (
    <table className="nx-table">
      <caption className="sr-only">Contratos</caption>
      <thead>
        <tr><th scope="col">Contrato</th><th scope="col">Cliente</th><th scope="col">Modalidade</th><th scope="col">Status</th><th scope="col">Vigência</th></tr>
      </thead>
      <tbody>
        {state.contracts.map((c) => (
          <tr key={c.id} className={c.id === state.selectedId ? 'is-selected' : undefined}>
            <td>
              <Button variant="link" aria-current={c.id === state.selectedId ? 'true' : undefined} onClick={() => void actions.select(c.id)}>
                {c.name}
              </Button>
              {isNonContractual(c) && <div><NonContractualBadge /></div>}
            </td>
            <td className="nx-mono">{c.tenant_id ?? '—'}</td>
            <td>{c.modality ? MODALITY[c.modality] : 'Não definida'}</td>
            <td><StatusBadge status={c.status} /></td>
            <td>{vigencia(c)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function Form({ initial, creating, calendars, busy, fieldError, onSave, onCancel }: {
  initial: ContractForm; creating: boolean; calendars: Calendar[]; busy: boolean; fieldError: { field: ContractField | null; message: string | null };
  onSave: (f: ContractForm) => void; onCancel: () => void;
}) {
  const [f, setF] = useState(initial);
  const set = <K extends keyof ContractForm>(k: K, v: ContractForm[K]) => setF((x) => ({ ...x, [k]: v }));
  return (
    <form
      aria-label={creating ? 'Novo contrato' : 'Editar contrato'}
      onSubmit={(e) => { e.preventDefault(); onSave(f); }}
      className="nx-stack"
    >
      <div className="nx-grid">
        <TextField label="Cliente (tenant)" value={f.tenant_id} onChange={(e) => set('tenant_id', e.target.value)}
          required disabled={!creating} hint={creating ? 'Identificador do cliente, sem espaços.' : 'Não muda depois de criado.'} />
        <TextField label="Nome do contrato" value={f.name} onChange={(e) => set('name', e.target.value)} required maxLength={255} />
        <SelectField label="Modalidade" value={f.modality} onChange={(e) => set('modality', e.target.value as ContractForm['modality'])}>
          <option value="">Não definida</option>
          {Object.entries(MODALITY).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </SelectField>
        <SelectField label="Calendário" value={f.calendar_id} onChange={(e) => set('calendar_id', e.target.value)} hint="Obrigatório para ativar." error={fieldError.field === 'calendar_id' ? fieldError.message : null}>
          <option value="">Nenhum</option>
          {calendars.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </SelectField>
        <TextField label="Início da vigência" type="date" value={f.starts_on} onChange={(e) => set('starts_on', e.target.value)} />
        <TextField label="Fim da vigência" type="date" value={f.ends_on} min={f.starts_on || undefined} error={fieldError.field === 'ends_on' ? fieldError.message : null} onChange={(e) => set('ends_on', e.target.value)} />
      </div>
      <AreaField label="Observações" value={f.notes} maxLength={4000} onChange={(e) => set('notes', e.target.value)} />
      <div className="nx-actions">
        <Button variant="primary" type="submit" icon={Save} disabled={busy}>{creating ? 'Criar rascunho' : 'Salvar'}</Button>
        <Button icon={X} onClick={onCancel}>Cancelar</Button>
      </div>
    </form>
  );
}

const emptyForm: ContractForm = { tenant_id: '', name: '', modality: '', starts_on: '', ends_on: '', calendar_id: '', notes: '' };
const toForm = (c: Contract): ContractForm => ({
  tenant_id: c.tenant_id ?? '', name: c.name, modality: c.modality ?? '', starts_on: c.starts_on ?? '',
  ends_on: c.ends_on ?? '', calendar_id: c.calendar_id === null ? '' : String(c.calendar_id), notes: c.notes ?? '',
});

function CalendarView({ calendar }: { calendar: Calendar | undefined }) {
  if (!calendar) return <Empty title="Sem calendário vinculado." hint="Ativar o contrato exige um calendário." />;
  const byDay = WEEKDAY.map((d, i) => ({ d, spans: calendar.hours.filter((h) => h.weekday === i) }));
  return (
    <div className="nx-stack">
      <div className="nx-actions">
        <strong>{calendar.name}</strong>
        <span className="nx-mono nx-muted">{calendar.timezone}</span>
        {calendar.is_24x7 && <Badge tone="info">24x7</Badge>}
      </div>
      {!calendar.is_24x7 && (
        <table className="nx-table">
          <caption className="sr-only">Horários de atendimento</caption>
          <thead><tr><th scope="col">Dia</th><th scope="col">Janelas</th></tr></thead>
          <tbody>
            {byDay.map(({ d, spans }) => (
              <tr key={d}><td>{d}</td><td className="nx-mono">{spans.length ? spans.map((s) => `${fmtTime(s.start_time)}–${fmtTime(s.end_time)}`).join(' · ') : 'sem atendimento'}</td></tr>
            ))}
          </tbody>
        </table>
      )}
      {calendar.holidays.length > 0 && (
        <p className="nx-muted">Feriados: {calendar.holidays.map((h) => `${fmtDate(h.holiday_date)} ${h.name}`).join(' · ')}</p>
      )}
    </div>
  );
}

function Detail({ detail, state, actions, canEdit }: {
  detail: ContractDetail; state: ContractsState; actions: ContractsActions; canEdit: boolean;
}) {
  const nonContractual = isNonContractual(detail);
  const calendar = state.calendars.find((c) => c.id === detail.calendar_id);
  const next = detail.is_default ? [] : TRANSITIONS[detail.status];
  const editable = canEdit && detail.status !== 'ended';
  return (
    <>
      <Panel
        title={detail.name}
        meta={<><StatusBadge status={detail.status} />{nonContractual && <NonContractualBadge />}</>}
        actions={canEdit && !state.editing && (
          <div className="nx-actions">
            {next.map((s) => s === 'ended'
              ? <ConfirmButton key={s} label={TRANSITION_LABEL[s]} confirmLabel="Confirmar encerramento" disabled={state.busy} onConfirm={() => void actions.transition(detail.id, s)} />
              : <Button key={s} disabled={state.busy} onClick={() => void actions.transition(detail.id, s)}>{TRANSITION_LABEL[s]}</Button>)}
            <Button icon={Pencil} disabled={!editable || state.busy} onClick={actions.startEdit}>Editar</Button>
          </div>
        )}
      >
        {nonContractual && (
          <Alert tone="warn">
            Valores do padrão interno, aplicados enquanto o cliente não tem contrato ativo. Não são contratuais e não
            valem como compromisso de prazo com o cliente.
          </Alert>
        )}
        {detail.status === 'ended' && <Alert tone="info">Contrato encerrado é imutável.</Alert>}
        {state.editing === 'edit' ? (
          <Form key={detail.id} initial={toForm(detail)} creating={false} calendars={state.calendars} busy={state.busy} fieldError={{ field: state.actionField, message: state.actionError }}
            onSave={(f) => void actions.save(f)} onCancel={actions.cancelEdit} />
        ) : (
          <dl className="nx-grid" style={{ margin: 0 }}>
            <div><dt className="nx-meta">Cliente</dt><dd className="nx-mono" style={{ margin: 0 }}>{detail.tenant_id ?? 'todos (padrão)'}</dd></div>
            <div><dt className="nx-meta">Modalidade</dt><dd style={{ margin: 0 }}>{detail.modality ? MODALITY[detail.modality] : 'Não definida'}</dd></div>
            <div><dt className="nx-meta">Vigência</dt><dd style={{ margin: 0 }}>{vigencia(detail)}</dd></div>
            <div><dt className="nx-meta">Atualizado</dt><dd style={{ margin: 0 }}>{fmtDateTime(detail.updated_at)}</dd></div>
            {detail.notes && <div style={{ gridColumn: '1 / -1' }}><dt className="nx-meta">Observações</dt><dd style={{ margin: 0 }}>{detail.notes}</dd></div>}
          </dl>
        )}
      </Panel>

      <Panel title="Políticas de prazo" meta={nonContractual ? <NonContractualBadge /> : undefined} flush>
        {detail.policies.length === 0 ? <Empty title="Sem políticas." hint="Ativar exige ao menos uma política habilitada." /> : (
          <table className="nx-table">
            <caption className="sr-only">Políticas de prazo{nonContractual ? ` — ${NON_CONTRACTUAL}` : ''}</caption>
            <thead><tr><th scope="col">Política</th><th scope="col">Severidade</th><th scope="col">Reconhecer em</th><th scope="col">Tratar em</th><th scope="col">Resolver em</th><th scope="col">Estado</th></tr></thead>
            <tbody>
              {detail.policies.map((p) => (
                <tr key={p.key}>
                  <td>{p.name}<div className="nx-mono nx-muted">{p.key}</div></td>
                  <td className="nx-mono">{sevText(p)}</td>
                  <td>{minutes(p.ack_minutes)}</td><td>{minutes(p.tto_minutes)}</td><td>{minutes(p.ttr_minutes)}</td>
                  <td><Badge tone={p.enabled ? 'ok' : 'neutral'}>{p.enabled ? 'Habilitada' : 'Desabilitada'}</Badge></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Panel>

      <Panel title="Escalonamento" meta={nonContractual ? <NonContractualBadge /> : undefined} flush>
        {detail.escalation_steps.length === 0 ? <Empty title="Sem passos próprios." hint="Sem passos habilitados, o contrato usa os do padrão interno (não contratual)." /> : (
          <table className="nx-table">
            <caption className="sr-only">Passos de escalonamento</caption>
            <thead><tr><th scope="col">Passo</th><th scope="col">Papel</th><th scope="col">Estado</th></tr></thead>
            <tbody>
              {detail.escalation_steps.map((s) => (
                <tr key={s.position}><td className="nx-mono">{s.position}</td><td>{ROLE[s.role] ?? s.role}</td>
                  <td><Badge tone={s.enabled ? 'ok' : 'neutral'}>{s.enabled ? 'Habilitado' : 'Desabilitado'}</Badge></td></tr>
              ))}
            </tbody>
          </table>
        )}
      </Panel>

      <Panel title="Calendário" meta={nonContractual ? <NonContractualBadge /> : undefined}>
        <CalendarView calendar={calendar} />
      </Panel>
    </>
  );
}

export default function ContractsView({ state, actions, canEdit }: {
  state: ContractsState; actions: ContractsActions; canEdit: boolean;
}) {
  return (
    <>
      <PageHeader
        title="Contratos"
        kicker="Prazos e modalidade"
        actions={canEdit && <Button variant="primary" icon={Plus} disabled={state.phase !== 'ready' || state.busy} onClick={actions.startCreate}>Novo contrato</Button>}
      />
      <div role="status" aria-live="polite">{state.notice && <Alert tone="info">{state.notice}</Alert>}</div>
      {state.actionError && !state.actionField && <Alert>{state.actionError}</Alert>}

      {state.phase === 'loading' && <Skeleton rows={4} />}
      {state.phase === 'error' && state.error && <ErrorState error={state.error} onRetry={() => void actions.load()} />}
      {state.phase === 'ready' && (
        <>
          <Divergences state={state} />
          {canEdit && state.editing === 'new' && (
            <Panel title="Novo contrato">
              <Form initial={emptyForm} creating calendars={state.calendars} busy={state.busy} fieldError={{ field: state.actionField, message: state.actionError }}
                onSave={(f) => void actions.save(f)} onCancel={actions.cancelEdit} />
            </Panel>
          )}
          <Panel title="Contratos" meta={<Badge>{state.contracts.length}</Badge>} flush><List state={state} actions={actions} /></Panel>
          {state.detailLoading && <Skeleton rows={3} />}
          {state.detailError && <ErrorState error={state.detailError} />}
          {!state.detailLoading && state.detail && <Detail detail={state.detail} state={state} actions={actions} canEdit={canEdit} />}
          {!state.selectedId && state.contracts.length > 0 && (
            <p className="nx-muted"><ScrollText {...ICON} /> Selecione um contrato para ver políticas, escalonamento e calendário.</p>
          )}
        </>
      )}
    </>
  );
}
