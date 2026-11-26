import { useState } from 'react';
import { Plus, Save } from 'lucide-react';
import type { AjustesActions, AjustesState, ParamInfo, Rule, RuleKind } from '../../hooks/useAjustes';
import { Alert, Badge, Button, ConfirmButton, Empty, ErrorState, Panel, PageHeader, SelectField, Skeleton, TextField } from '../ui/kit';

// Rótulo e unidade de cada ajuste; a chave e os limites vêm da API.
export const PARAMS: { key: string; label: string; unit: string; hint: string }[] = [
  { key: 'ticket_grace_minutes', label: 'Carência antes de abrir chamado', unit: 'min', hint: 'Se o problema se resolver antes, nada é aberto.' },
  { key: 'ticket_reopen_hours', label: 'Reabrir o mesmo chamado em até', unit: 'h', hint: 'Voltou a ocorrer dentro da janela: usa o chamado que já existe.' },
  { key: 'ticket_symptom_lead_minutes', label: 'Antecedência da causa sobre o sintoma', unit: 'min', hint: 'Sintoma do mesmo site vira comentário no chamado da causa.' },
  { key: 'ticket_cross_link_minutes', label: 'Janela de ligação entre NOC e SOC', unit: 'min', hint: 'Chamados de ramos diferentes dentro da janela ficam relacionados.' },
  { key: 'soc_ticket_min_level', label: 'Nível do Wazuh que abre chamado do SOC', unit: 'nível', hint: 'De 1 a 15. Subir reduz o volume de chamados do SOC.' },
];

const KINDS: { kind: RuleKind; title: string; hint: string }[] = [
  { kind: 'action', title: 'Exigem ação', hint: 'Título que casa abre chamado.' },
  { kind: 'noise', title: 'Ruído', hint: 'Título que casa nunca abre chamado (vence a regra de ação).' },
  { kind: 'cause', title: 'Causa', hint: 'Título que casa é a causa; os sintomas do site viram comentário.' },
];

function ParamRow({ spec, info, busy, onSave }: { spec: (typeof PARAMS)[number]; info: ParamInfo; busy: boolean; onSave: (v: number) => void }) {
  const [v, setV] = useState(String(info.value));
  const n = Number(v);
  const valid = Number.isInteger(n) && n >= 1 && n <= info.max;
  return (
    <form className="nx-actions" aria-label={spec.label} onSubmit={(e) => { e.preventDefault(); if (valid) onSave(n); }}>
      <TextField label={`${spec.label} (${spec.unit})`} type="number" min={1} max={info.max} value={v}
        hint={`${spec.hint} Padrão ${info.default}.`} error={valid ? undefined : `Informe de 1 a ${info.max}.`}
        onChange={(e) => setV(e.target.value)} />
      <Button type="submit" icon={Save} disabled={busy || !valid || n === info.value}>Salvar</Button>
    </form>
  );
}

function RuleTable({ rules, canEdit, busy, actions }: { rules: Rule[]; canEdit: boolean; busy: boolean; actions: AjustesActions }) {
  return (
    <table className="nx-table">
      <caption className="sr-only">Regras</caption>
      <thead><tr><th scope="col">Padrão</th><th scope="col">Nota</th><th scope="col">Estado</th>{canEdit && <th scope="col"><span className="sr-only">Ações</span></th>}</tr></thead>
      <tbody>
        {rules.map((r) => (
          <tr key={r.id}>
            <td className="nx-mono">{r.pattern}</td>
            <td>{r.note ?? '—'}</td>
            <td><Badge tone={r.enabled ? 'ok' : 'neutral'}>{r.enabled ? 'Ligada' : 'Desligada'}</Badge></td>
            {canEdit && (
              <td>
                <div className="nx-actions">
                  <Button disabled={busy} aria-label={`${r.enabled ? 'Desligar' : 'Ligar'} ${r.pattern}`} onClick={() => void actions.toggleRule(r.id, !r.enabled)}>{r.enabled ? 'Desligar' : 'Ligar'}</Button>
                  <ConfirmButton label="Remover" confirmLabel={`Confirmar remoção de ${r.pattern}`} disabled={busy} onConfirm={() => void actions.removeRule(r.id)} />
                </div>
              </td>
            )}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function NewRule({ busy, onAdd }: { busy: boolean; onAdd: (k: RuleKind, p: string, n: string) => void }) {
  const [kind, setKind] = useState<RuleKind>('noise');
  const [pattern, setPattern] = useState('');
  const [note, setNote] = useState('');
  return (
    <form aria-label="Nova regra" className="nx-stack" onSubmit={(e) => { e.preventDefault(); onAdd(kind, pattern, note); setPattern(''); setNote(''); }}>
      <div className="nx-grid">
        <SelectField label="Tipo" value={kind} onChange={(e) => setKind(e.target.value as RuleKind)}>
          {KINDS.map((k) => <option key={k.kind} value={k.kind}>{k.title}</option>)}
        </SelectField>
        <TextField label="Padrão (expressão regular, sem diferenciar maiúsculas)" value={pattern} required maxLength={200} onChange={(e) => setPattern(e.target.value)} />
        <TextField label="Nota" value={note} maxLength={200} onChange={(e) => setNote(e.target.value)} />
      </div>
      <div className="nx-actions"><Button variant="primary" type="submit" icon={Plus} disabled={busy || !pattern.trim()}>Adicionar regra</Button></div>
    </form>
  );
}

export default function AjustesView({ state, actions, canEdit }: { state: AjustesState; actions: AjustesActions; canEdit: boolean }) {
  return (
    <>
      <PageHeader title="Ajustes" kicker="Administração" />
      <div role="status" aria-live="polite">{state.notice && <Alert tone="info">{state.notice}</Alert>}</div>
      {state.actionError && <Alert>{state.actionError}</Alert>}
      {state.phase === 'loading' && <Skeleton rows={4} />}
      {state.phase === 'error' && state.error && <ErrorState error={state.error} onRetry={() => void actions.load()} />}
      {state.phase === 'ready' && (
        <>
          <Panel title="Tempos do decisor de chamados" meta={<Badge>{canEdit ? 'Edição' : 'Somente leitura'}</Badge>}>
            <div className="nx-stack">
              {PARAMS.filter((p) => state.params[p.key]).map((p) => (
                canEdit
                  ? <ParamRow key={`${p.key}:${state.params[p.key].value}`} spec={p} info={state.params[p.key]} busy={state.busy} onSave={(v) => void actions.saveParam(p.key, v)} />
                  : <p key={p.key}><strong>{p.label}:</strong> {state.params[p.key].value} {p.unit}</p>
              ))}
            </div>
            <p className="nx-muted">Os prazos de atendimento (SLA) ficam no GLPI.</p>
          </Panel>
          {KINDS.map((k) => {
            const rules = state.rules.filter((r) => r.kind === k.kind);
            return (
              <Panel key={k.kind} title={k.title} meta={<Badge>{rules.length}</Badge>} flush>
                <p className="nx-muted" style={{ padding: '0 var(--nx-space-3, 12px)' }}>{k.hint}</p>
                {rules.length === 0 ? <Empty title="Nenhuma regra." /> : <RuleTable rules={rules} canEdit={canEdit} busy={state.busy} actions={actions} />}
              </Panel>
            );
          })}
          {canEdit && <Panel title="Nova regra"><NewRule busy={state.busy} onAdd={(k, p, n) => void actions.addRule(k, p, n)} /></Panel>}
        </>
      )}
    </>
  );
}
