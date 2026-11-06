import { useState } from 'react';
import { Pencil, Plus, Save, Trash2, X } from 'lucide-react';
import { ROLE } from '../../format';
import {
  emptyPolicy, policyToForm, STEP_ROLES, type Calendar, type ContractsActions, type ContractsState, type Policy,
  type PolicyForm, type Step, type StepForm,
} from '../../hooks/useContracts';
import { Alert, Button, CheckField, ConfirmButton, SelectField, TextField } from '../ui/kit';

const MODES = { min: 'A partir da severidade', exact: 'Severidade exata', all: 'Todas as severidades' } as const;

export function PolicyEditor({ policy, calendars, state, actions }: {
  policy: Policy | null; calendars: Calendar[]; state: ContractsState; actions: ContractsActions;
}) {
  const [f, setF] = useState<PolicyForm>(policy ? policyToForm(policy) : emptyPolicy);
  const set = <K extends keyof PolicyForm>(k: K, v: PolicyForm[K]) => setF((x) => ({ ...x, [k]: v }));
  return (
    <form aria-label={policy ? 'Editar política' : 'Nova política'} className="nx-stack" onSubmit={(e) => { e.preventDefault(); void actions.savePolicy(f); }}>
      {state.actionError && <Alert>{state.actionError}</Alert>}
      <div className="nx-grid">
        <TextField label="Chave da política" value={f.key} required maxLength={32} disabled={!!policy} onChange={(e) => set('key', e.target.value)}
          hint={policy ? 'Não muda depois de criada.' : 'Ex.: critico, padrao.'} />
        <TextField label="Nome da política" value={f.name} required maxLength={128} onChange={(e) => set('name', e.target.value)} />
        <SelectField label="Classe de severidade" value={f.mode} onChange={(e) => set('mode', e.target.value as PolicyForm['mode'])}>
          {Object.entries(MODES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </SelectField>
        {f.mode !== 'all' && (
          <SelectField label="Severidade" value={f.severity} onChange={(e) => set('severity', e.target.value)}>
            {[0, 1, 2, 3, 4, 5].map((s) => <option key={s} value={s}>{s}</option>)}
          </SelectField>
        )}
        <TextField label="Reconhecer em (min)" type="number" min={1} max={43200} required value={f.ack_minutes} onChange={(e) => set('ack_minutes', e.target.value)} />
        <TextField label="Tratar em (min)" type="number" min={1} max={43200} value={f.tto_minutes} onChange={(e) => set('tto_minutes', e.target.value)} hint="Opcional." />
        <TextField label="Resolver em (min)" type="number" min={1} max={43200} value={f.ttr_minutes} onChange={(e) => set('ttr_minutes', e.target.value)} hint="Opcional." />
        <SelectField label="Calendário da política" value={f.calendar_id} onChange={(e) => set('calendar_id', e.target.value)} hint="Vazio usa o calendário do contrato.">
          <option value="">Do contrato</option>
          {calendars.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </SelectField>
      </div>
      <CheckField label="Política habilitada" checked={f.enabled} onChange={(e) => set('enabled', e.target.checked)} />
      <div className="nx-actions">
        <Button variant="primary" type="submit" icon={Save} disabled={state.busy}>Salvar política</Button>
        <Button icon={X} onClick={actions.cancelPolicy}>Cancelar</Button>
      </div>
    </form>
  );
}

export function PolicyRowActions({ policy, state, actions }: { policy: Policy; state: ContractsState; actions: ContractsActions }) {
  return (
    <div className="nx-actions">
      <Button icon={Pencil} aria-label={`Editar política ${policy.name}`} disabled={state.busy} onClick={() => actions.startPolicy(policy.key)}>Editar</Button>
      <ConfirmButton icon={Trash2} label="Remover" confirmLabel={`Confirmar remoção de ${policy.name}`} disabled={state.busy} onConfirm={() => void actions.deletePolicy(policy.key)} />
    </div>
  );
}

export const AddPolicyButton = ({ state, actions }: { state: ContractsState; actions: ContractsActions }) =>
  <Button icon={Plus} disabled={state.busy || state.policyEditing !== null} onClick={() => actions.startPolicy(null)}>Nova política</Button>;

export function StepEditor({ step, nextPosition, state, actions }: {
  step: Step | null; nextPosition: number; state: ContractsState; actions: ContractsActions;
}) {
  const [f, setF] = useState<StepForm>(step
    ? { position: String(step.position), role: step.role, enabled: step.enabled }
    : { position: String(nextPosition), role: 'noc', enabled: true });
  return (
    <form aria-label={step ? 'Editar passo' : 'Novo passo'} className="nx-stack" onSubmit={(e) => { e.preventDefault(); void actions.saveStep(f); }}>
      {state.actionError && <Alert>{state.actionError}</Alert>}
      <div className="nx-grid">
        <TextField label="Posição do passo" type="number" min={1} max={100} required disabled={!!step} value={f.position} onChange={(e) => setF({ ...f, position: e.target.value })} />
        <SelectField label="Papel do passo" value={f.role} onChange={(e) => setF({ ...f, role: e.target.value })}>
          {STEP_ROLES.map((r) => <option key={r} value={r}>{ROLE[r]}</option>)}
        </SelectField>
      </div>
      <CheckField label="Passo habilitado" checked={f.enabled} onChange={(e) => setF({ ...f, enabled: e.target.checked })} />
      <div className="nx-actions">
        <Button variant="primary" type="submit" icon={Save} disabled={state.busy}>Salvar passo</Button>
        <Button icon={X} onClick={actions.cancelStep}>Cancelar</Button>
      </div>
    </form>
  );
}

export function StepRowActions({ step, state, actions }: { step: Step; state: ContractsState; actions: ContractsActions }) {
  return (
    <div className="nx-actions">
      <Button icon={Pencil} aria-label={`Editar passo ${step.position}`} disabled={state.busy} onClick={() => actions.startStep(step.position)}>Editar</Button>
      <ConfirmButton icon={Trash2} label="Remover" confirmLabel={`Confirmar remoção do passo ${step.position}`} disabled={state.busy} onConfirm={() => void actions.deleteStep(step.position)} />
    </div>
  );
}

export const AddStepButton = ({ state, actions }: { state: ContractsState; actions: ContractsActions }) =>
  <Button icon={Plus} disabled={state.busy || state.stepEditing !== null} onClick={() => actions.startStep(null)}>Novo passo</Button>;
