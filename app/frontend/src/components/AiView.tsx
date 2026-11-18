import { useCallback, useEffect, useState } from 'react';
import { asApiError, request, type ApiError } from '../http';
import { timeAgo } from '../access';
import { Alert, Badge, Empty, ErrorState, Panel, Screen, Skeleton, type Tone } from './ui/kit';

type Verdict = 'useful' | 'wrong' | 'unread';
interface KindMetrics {
  total: number; divergence_rate: number | null; useful_rate: number | null; failure_rate: number | null;
  cost_usd: number | null; cost_missing: number;
  mttr_minutes: { useful: number | null; other: number | null };
}
interface Metrics {
  window_days: number;
  budget: { month_cost_usd: number | null; limit_usd: number | null };
  by_kind: Partial<Record<string, KindMetrics>>;
}
interface Decision {
  id: number; kind: string; customer_id: string | null; ticket_id: string | null; outcome: string;
  rule_value: string | null; model_value: string | null; divergent: boolean; feedback: Verdict | null;
  cost_usd: number | null; created_at: string;
}

const KINDS: [string, string][] = [['incident_analysis', 'NOC (Zabbix)'], ['soc_triage', 'SOC (Wazuh)']];
const kindLabel = (k: string) => KINDS.find(([key]) => key === k)?.[1] ?? k;
const VERDICTS: [Verdict, string, string, Tone][] = [
  ['useful', 'Útil', 'útil', 'ok'], ['wrong', 'Errado', 'errado', 'bad'], ['unread', 'Não li', 'não lido', 'neutral'],
];
const pct = (r: number | null | undefined) => (r == null ? '—' : `${Math.round(r * 100)}%`);
const usd = (v: number | null | undefined) => (v == null ? '—' : `US$ ${v.toFixed(2)}`);
const min = (v: number | null | undefined) => (v == null ? '—' : `${Math.round(v)} min`);

function KindCards({ label, m }: { label: string; m?: KindMetrics }) {
  return (
    <Panel title={label}>
      {!m ? <div className="nx-empty">Sem decisões na janela.</div> : (
        <dl className="nx-kpis">
          <div><dt>Decisões</dt><dd>{m.total.toLocaleString('pt-BR')}</dd></div>
          <div><dt>Divergência da regra</dt><dd>{pct(m.divergence_rate)}</dd></div>
          <div><dt>Útil</dt><dd>{pct(m.useful_rate)}</dd></div>
          <div><dt>Falha</dt><dd className={m.failure_rate ? 'bad' : ''}>{pct(m.failure_rate)}</dd></div>
          <div><dt>Custo</dt><dd>{usd(m.cost_usd)}</dd>{m.cost_missing > 0 && <dd className="nx-muted">{m.cost_missing} sem custo</dd>}</div>
          <div><dt>MTTR (útil × outro)</dt><dd>{min(m.mttr_minutes.useful)} × {min(m.mttr_minutes.other)}</dd></div>
        </dl>
      )}
    </Panel>
  );
}

export default function AiView({ refreshKey = 0 }: { refreshKey?: number }) {
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [rows, setRows] = useState<Decision[] | null>(null);
  const [divergent, setDivergent] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const loadMetrics = useCallback(() => request<Metrics>('/api/ai/metrics?days=30').then(setMetrics), []);
  const load = useCallback(async () => {
    try {
      const qs = new URLSearchParams({ limit: '50', ...(divergent && { divergent: 'true' }) });
      const [m, d] = await Promise.all([request<Metrics>('/api/ai/metrics?days=30'), request<Decision[]>(`/api/ai/decisions?${qs}`)]);
      setMetrics(m); setRows(d); setError(null);
    } catch (e) { setError(asApiError(e)); }
  }, [divergent, refreshKey]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { void load(); }, [load]);

  async function send(id: number, verdict: Verdict) {
    try {
      const r = await request<{ feedback: Verdict }>(`/api/ai/decisions/${id}/feedback`, { method: 'POST', body: { verdict } });
      setRows(rs => rs && rs.map(d => (d.id === id ? { ...d, feedback: r.feedback } : d)));
      setActionError(null);
      void loadMetrics().catch(() => undefined);
    } catch (e) { setActionError(asApiError(e).message); }
  }

  if (error) return <Screen><ErrorState error={error} onRetry={() => void load()} /></Screen>;
  if (!metrics || !rows) return <Screen><Skeleton rows={6} /></Screen>;

  return (
    <Screen>
      <dl className="nx-kpis">
        <div><dt>Custo do mês / teto</dt><dd>{usd(metrics.budget.month_cost_usd)} / {usd(metrics.budget.limit_usd)}</dd></div>
        <div><dt>Janela</dt><dd>{metrics.window_days} dias</dd></div>
      </dl>
      <div className="nx-cols">{KINDS.map(([k, label]) => <KindCards key={k} label={label} m={metrics.by_kind[k]} />)}</div>

      <Panel title="Decisões recentes" meta={<span className="nx-meta">{rows.length} mais recentes</span>} flush
        actions={<button type="button" className="nx-btn nx-toggle" aria-pressed={divergent} onClick={() => setDivergent(v => !v)}>Só divergentes</button>}>
        {actionError && <Alert>{actionError}</Alert>}
        {!rows.length ? <Empty title={divergent ? 'Nenhuma decisão divergente.' : 'Nenhuma decisão registrada.'} /> : (
          <table className="nx-table nx-dense nx-cards">
            <thead><tr><th>Quando</th><th>Origem</th><th>Cliente</th><th>Chamado</th><th>Regra</th><th>IA</th><th>Custo</th><th>Retorno</th></tr></thead>
            <tbody>{rows.map(d => {
              const fb = VERDICTS.find(([v]) => v === d.feedback);
              return (
                <tr key={d.id}>
                  <td className="nx-mono" title={new Date(d.created_at).toLocaleString('pt-BR')}>{timeAgo(d.created_at)}</td>
                  <td>{kindLabel(d.kind)}</td>
                  <td>{d.customer_id ?? '—'}</td>
                  <td className="nx-mono">{d.ticket_id ?? '—'}</td>
                  <td>{d.rule_value ?? '—'}</td>
                  <td>{d.model_value ?? '—'} {d.divergent && <Badge tone="warn">diverge</Badge>}</td>
                  <td className="nx-mono">{usd(d.cost_usd)}</td>
                  <td>
                    <div className="nx-actions">
                      {fb && <Badge tone={fb[3]}>{fb[2]}</Badge>}
                      {VERDICTS.map(([v, label]) => (
                        <button key={v} type="button" className="nx-btn" aria-label={`${label}: decisão ${d.id}`} aria-pressed={d.feedback === v}
                          onClick={() => void send(d.id, v)}>{label}</button>
                      ))}
                    </div>
                  </td>
                </tr>
              );
            })}</tbody>
          </table>
        )}
      </Panel>
    </Screen>
  );
}
