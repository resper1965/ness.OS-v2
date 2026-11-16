import { useCallback, useEffect, useMemo, useState } from 'react';
import { Search } from 'lucide-react';
import { asApiError, request, type ApiError } from '../http';
import { timeAgo } from '../access';
import { Badge, Empty, ErrorState, ICON, Panel, Screen, Skeleton, type Tone } from './ui/kit';
import SecurityAlerts from './SecurityAlerts';

type Band = 'critical' | 'high' | 'medium' | 'low';
interface Ranked { key: string; count: number }
interface SocEvent {
  id: number; created_at: string; agent: string; customer_id: string | null; rule_id: string;
  description: string; level: number; band: Band; tactics: string[]; classification: string | null; action: string | null;
}
interface SocOverview {
  hours: number; bucket_seconds: number; total: number; truncated: boolean;
  bands: Record<Band, number>; auth_failures: number; auth_successes: number;
  pending_tenant_review: number; archived_no_llm: number;
  series: ({ t: string } & Record<Band, number>)[];
  top_agents: Ranked[]; top_customers: Ranked[]; top_tactics: Ranked[];
  top_rules: { id: string; description: string; level: number; count: number }[];
  events: SocEvent[];
}

// Faixas do dashboard do Wazuh: crítico 15+, alto 12–14, médio 7–11, baixo 0–6.
const BANDS: { key: Band; label: string; range: string; tone: Tone }[] = [
  { key: 'critical', label: 'Crítico', range: '15+', tone: 'bad' },
  { key: 'high', label: 'Alto', range: '12–14', tone: 'bad' },
  { key: 'medium', label: 'Médio', range: '7–11', tone: 'warn' },
  { key: 'low', label: 'Baixo', range: '0–6', tone: 'neutral' },
];
const PERIODS = [[24, '24h'], [168, '7d'], [720, '30d']] as const;
const NO_CUSTOMER = 'sem_cliente';
const customerLabel = (c: string | null) => (!c || c === NO_CUSTOMER ? 'Sem cliente' : c);
const ACTION: Record<string, [Tone, string]> = {
  ARCHIVE_NO_LLM: ['neutral', 'Arquivado'],
  PENDING_TENANT_REVIEW: ['warn', 'Sem cliente'],
};
const actionOf = (a: string | null): [Tone, string] => (a && ACTION[a]) || ['info', 'Escalado'];

interface Cve { id: string; title: string; severity: string; cvss: number; affected_tech: string; exploited_wild: boolean; patch_available: boolean; action: string }

// Catálogo de referência (estático no servidor), não alerta: fica recolhido no fim da tela.
function CveReference() {
  const [items, setItems] = useState<Cve[] | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [open, setOpen] = useState(false);
  useEffect(() => {
    if (!open || items) return;
    request<{ items: Cve[] }>('/api/secops/cve-intel').then(r => setItems(r.items), e => setError(asApiError(e)));
  }, [open, items]);
  return (
    <Panel title="Vulnerabilidades de referência" meta={<span className="nx-meta">catálogo</span>} flush
      actions={<button type="button" className="nx-btn" aria-expanded={open} onClick={() => setOpen(o => !o)}>{open ? 'Recolher' : 'Mostrar'}</button>}>
      {open && (error ? <ErrorState error={error} /> : !items ? <Skeleton rows={3} /> :
        <table className="nx-table nx-dense nx-cards">
          <thead><tr><th>CVSS</th><th>CVE</th><th>Título</th><th>Tecnologia</th><th>Situação</th><th>Ação</th></tr></thead>
          <tbody>{items.map(c => (
            <tr key={c.id}>
              <td><Badge tone={c.severity === 'medium' ? 'warn' : 'bad'}>{c.cvss ? c.cvss.toFixed(1) : '—'}</Badge></td>
              <td className="nx-mono">{c.id}</td>
              <td className="nx-main">{c.title}</td>
              <td>{c.affected_tech}</td>
              <td>{c.exploited_wild ? <Badge tone="bad">Explorada</Badge> : <Badge tone={c.patch_available ? 'ok' : 'warn'}>{c.patch_available ? 'Com correção' : 'Sem correção'}</Badge>}</td>
              <td className="nx-muted">{c.action}</td>
            </tr>
          ))}</tbody>
        </table>)}
    </Panel>
  );
}

/** Filtro local da tabela: busca em descrição, agente, regra e tática; faixa opcional. */
function filterEvents(events: SocEvent[], q: string, band: Band | '') {
  const t = q.trim().toLowerCase();
  return events.filter(e => (!band || e.band === band) && (!t ||
    [e.description, e.agent, e.rule_id, ...e.tactics].some(v => v.toLowerCase().includes(t))));
}

function Rank({ title, rows, label = (k: string) => k }: { title: string; rows: Ranked[]; label?: (k: string) => string }) {
  const max = Math.max(1, ...rows.map(r => r.count));
  return (
    <Panel title={title} flush>
      {!rows.length ? <div className="nx-empty">Sem dado na janela.</div> :
        <ol className="nx-rank">{rows.map(r => (
          <li key={r.key}>
            <span className="nx-rank-label" title={label(r.key)}>{label(r.key)}</span>
            <span className="nx-rank-bar" aria-hidden><span style={{ width: `${(r.count / max) * 100}%` }} /></span>
            <span className="nx-mono">{r.count.toLocaleString('pt-BR')}</span>
          </li>
        ))}</ol>}
    </Panel>
  );
}

function Evolution({ data }: { data: SocOverview }) {
  const max = Math.max(1, ...data.series.map(s => BANDS.reduce((a, b) => a + s[b.key], 0)));
  const fmt = (t: string) => new Date(t).toLocaleString('pt-BR', data.bucket_seconds < 86400 ? { hour: '2-digit', minute: '2-digit' } : { day: '2-digit', month: '2-digit' });
  const summary = BANDS.map(b => `${b.label} ${data.bands[b.key]}`).join(', ');
  return (
    <Panel title="Evolução por nível" meta={<span className="nx-meta">por {data.bucket_seconds < 86400 ? 'hora' : 'dia'}</span>}
      actions={<ul className="nx-legend">{BANDS.map(b => <li key={b.key}><i className={`nx-b-${b.key}`} />{b.label} <span className="nx-muted">{b.range}</span></li>)}</ul>}>
      <div className="nx-evo" role="img" aria-label={`Alertas por ${data.bucket_seconds < 86400 ? 'hora' : 'dia'}: ${summary}`}>
        {data.series.map(s => (
          <div key={s.t} className="nx-evo-col" title={`${fmt(s.t)} · ${BANDS.map(b => `${b.label} ${s[b.key]}`).join(' · ')}`}>
            {BANDS.map(b => s[b.key] > 0 && <span key={b.key} className={`nx-b-${b.key}`} style={{ height: `${(s[b.key] / max) * 100}%` }} />)}
          </div>
        ))}
      </div>
      <div className="nx-evo-axis nx-mono nx-muted" aria-hidden>
        <span>{fmt(data.series[0]?.t ?? '')}</span><span>{fmt(data.series[Math.floor(data.series.length / 2)]?.t ?? '')}</span><span>agora</span>
      </div>
    </Panel>
  );
}

export default function SocView({ refreshKey = 0 }: { refreshKey?: number }) {
  const [hours, setHours] = useState(24);
  const [customer, setCustomer] = useState('');
  const [customers, setCustomers] = useState<{ id: string; name: string }[]>([]);
  const [q, setQ] = useState('');
  const [band, setBand] = useState<Band | ''>('');
  const [data, setData] = useState<SocOverview | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [at, setAt] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const qs = new URLSearchParams({ hours: String(hours), ...(customer && { customer_id: customer }) });
      const next = await request<SocOverview>(`/api/secops/overview?${qs}`);
      setData(next); setError(null); setAt(new Date().toISOString());
    } catch (e) { setError(asApiError(e)); }
  }, [hours, customer, refreshKey]); // eslint-disable-line react-hooks/exhaustive-deps

  // Lista completa de clientes: o ranking do painel corta em 8.
  useEffect(() => {
    request<{ id: string; name: string }[]>('/api/tenants/list').then(setCustomers, () => setCustomers([]));
  }, []);

  useEffect(() => {
    void load();
    const t = window.setInterval(() => { void load(); }, 60_000);
    return () => window.clearInterval(t);
  }, [load]);

  const events = useMemo(() => filterEvents(data?.events ?? [], q, band), [data, q, band]);
  const severe = data ? data.bands.critical + data.bands.high : 0;

  return (
    <Screen>
      <SecurityAlerts />
      <div className="nx-filters" role="search" aria-label="Filtrar alertas de segurança">
        <div className="nx-actions" role="group" aria-label="Período">
          {PERIODS.map(([h, label]) => <button key={h} type="button" className="nx-btn nx-toggle" aria-pressed={hours === h} onClick={() => setHours(h)}>{label}</button>)}
        </div>
        <label className="nx-field nx-inline">Cliente
          <select value={customer} onChange={e => setCustomer(e.target.value)}>
            <option value="">Todos</option>
            {customers.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        </label>
        <span className="nx-meta">{at ? `Atualizado ${timeAgo(at)}` : 'Consultando…'}</span>
      </div>

      {error && <ErrorState error={error} onRetry={() => void load()} />}
      {!data && !error && <Skeleton rows={6} />}

      {data && <>
        <dl className="nx-kpis">
          <div><dt>Alertas triados</dt><dd>{data.total.toLocaleString('pt-BR')}</dd></div>
          <div><dt>Crítico + alto (12+)</dt><dd className={severe ? 'bad' : ''}>{severe.toLocaleString('pt-BR')}</dd></div>
          <div><dt>Falhas de autenticação</dt><dd className={data.auth_failures ? 'bad' : ''}>{data.auth_failures.toLocaleString('pt-BR')}</dd></div>
          <div><dt>Autenticações aceitas</dt><dd>{data.auth_successes.toLocaleString('pt-BR')}</dd></div>
          <div><dt>Arquivados sem IA</dt><dd>{data.archived_no_llm.toLocaleString('pt-BR')}</dd></div>
          <div><dt>Sem cliente (revisar)</dt><dd className={data.pending_tenant_review ? 'bad' : ''}>{data.pending_tenant_review.toLocaleString('pt-BR')}</dd></div>
        </dl>
        {data.truncated && <div className="nx-alert warn" role="alert">Mais de 5.000 alertas na janela: os números consideram os 5.000 mais recentes.</div>}

        {!data.total ? (
          <Panel title="Alertas de segurança">
            <Empty title="Nenhum alerta triado nesta janela." hint="Os alertas entram pela triagem automática. Confira o estado da fonte de segurança na Visão geral." />
          </Panel>
        ) : <>
          <Evolution data={data} />
          <div className="nx-cols">
            <Rank title="Táticas MITRE ATT&CK" rows={data.top_tactics} />
            <Rank title="Agentes com mais alertas" rows={data.top_agents} />
            <Rank title="Clientes" rows={data.top_customers} label={customerLabel} />
          </div>

          <Panel title="Regras mais disparadas" flush>
            <table className="nx-table nx-dense nx-cards">
              <thead><tr><th>Nível</th><th>Regra</th><th>Descrição</th><th>Alertas</th></tr></thead>
              <tbody>{data.top_rules.map(r => {
                const b = BANDS.find(x => x.key === bandOf(r.level))!;
                return (
                  <tr key={r.id}>
                    <td><Badge tone={b.tone}>{r.level} · {b.label}</Badge></td>
                    <td className="nx-mono">{r.id}</td>
                    <td className="nx-main">{r.description || '—'}</td>
                    <td className="nx-mono">{r.count.toLocaleString('pt-BR')}</td>
                  </tr>
                );
              })}</tbody>
            </table>
          </Panel>

          <Panel title="Eventos" meta={<span className="nx-meta">{events.length} de {Math.min(data.total, 100)} mais recentes</span>} flush
            actions={<div className="nx-actions">
              <label className="nx-search"><Search {...ICON} /><span className="sr-only">Buscar evento</span>
                <input type="search" placeholder="Descrição, agente, regra ou tática" value={q} onChange={e => setQ(e.target.value)} /></label>
              <div className="nx-actions" role="group" aria-label="Nível">
                {BANDS.map(b => <button key={b.key} type="button" className="nx-btn nx-toggle" aria-pressed={band === b.key} onClick={() => setBand(band === b.key ? '' : b.key)}>{b.label} <span className="nx-mono">{data.bands[b.key]}</span></button>)}
              </div>
            </div>}>
            {!events.length ? <div className="nx-empty">Nenhum evento com esses filtros.</div> :
              <table className="nx-table nx-dense nx-cards">
                <thead><tr><th>Quando</th><th>Nível</th><th>Cliente</th><th>Agente</th><th>Descrição</th><th>Tática</th><th>Regra</th><th>Decisão</th></tr></thead>
                <tbody>{events.map(e => {
                  const b = BANDS.find(x => x.key === e.band)!;
                  const [tone, label] = actionOf(e.action);
                  return (
                    <tr key={e.id}>
                      <td className="nx-mono" title={new Date(e.created_at).toLocaleString('pt-BR')}>{timeAgo(e.created_at)}</td>
                      <td><Badge tone={b.tone}>{e.level} · {b.label}</Badge></td>
                      <td>{customerLabel(e.customer_id)}</td>
                      <td className="nx-mono">{e.agent}</td>
                      <td className="nx-main">{e.description || '—'}</td>
                      <td>{e.tactics.join(', ') || <span className="nx-muted">—</span>}</td>
                      <td className="nx-mono">{e.rule_id}</td>
                      <td><Badge tone={tone}>{label}</Badge></td>
                    </tr>
                  );
                })}</tbody>
              </table>}
          </Panel>
        </>}
      </>}

      <CveReference />
    </Screen>
  );
}

const bandOf = (level: number): Band => (level >= 15 ? 'critical' : level >= 12 ? 'high' : level >= 7 ? 'medium' : 'low');
