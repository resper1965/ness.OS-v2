import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react';
import { timeAgo } from '../access';
import { Badge, Panel, Screen, type Tone } from './ui/kit';
import { NO_CUSTOMER, SEVERITIES, type Problem } from './ProblemsView';

const API_BASE = import.meta.env.VITE_API_URL ?? '';

interface SourceStatus {
  status: 'ok' | 'degraded' | 'down' | 'planned' | 'unavailable';
  last_success_at: string | null;
  stale: boolean;
  error_code: string | null;
}
type Sources = Partial<Record<'zabbix' | 'glpi' | 'wazuh', SourceStatus>>;
interface RecentIncident { id: string; title: string; host_name: string; severity_level: number; client?: string; last_seen: string | null; ticket_id?: string | null }

const SOURCE: Record<SourceStatus['status'], [Tone, string]> = {
  ok: ['ok', 'Conectada'], degraded: ['warn', 'Degradada'], down: ['bad', 'Indisponível'],
  planned: ['neutral', 'Não integrada'], unavailable: ['neutral', 'Não configurada'],
};
const SEV = [5, 4, 3, 2, 1] as const;
const sevLabel = (l: number) => SEVERITIES.find(s => s.level === l)?.label ?? 'N/C';

/** Matriz cliente × severidade, ordenada pelo pior problema e depois pelo volume. */
export function customerMatrix(problems: Problem[]) {
  const m = new Map<string, number[]>();
  for (const p of problems) {
    const row = m.get(p.customer ?? NO_CUSTOMER) ?? [0, 0, 0, 0, 0, 0];
    row[p.severity_level] = (row[p.severity_level] ?? 0) + 1;
    m.set(p.customer ?? NO_CUSTOMER, row);
  }
  const worst = (r: number[]) => SEV.find(l => r[l]) ?? 0;
  const sum = (r: number[]) => r.reduce((a, b) => a + b, 0);
  return [...m.entries()].sort(([, a], [, b]) => worst(b) - worst(a) || sum(b) - sum(a));
}

// Navega pelo mesmo caminho do botão voltar: o shell troca a tela e ela lê o filtro da URL.
const go = (view: string, extra = '') => { window.history.pushState(null, '', `?view=${view}${extra}`); window.dispatchEvent(new PopStateEvent('popstate')); };

export default function CoreDashboard({ authHeader, problems, hosts, observedAt, pipeline }: {
  authHeader: Record<string, string>; problems: Problem[]; hosts?: number; observedAt: Date | null; pipeline: ReactNode;
}) {
  const [sources, setSources] = useState<Sources | null>(null);
  const [recent, setRecent] = useState<RecentIncident[]>([]);
  const [incidents24h, setIncidents24h] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    const since = encodeURIComponent(new Date(Date.now() - 86_400_000).toISOString());
    const get = (path: string) => fetch(`${API_BASE}${path}`, { credentials: 'include', headers: authHeader })
      .then(r => { if (!r.ok) throw new Error(String(r.status)); return r.json(); });
    const [src, inc] = await Promise.allSettled([get('/api/dashboard/sources'), get(`/api/incidents?limit=10&from=${since}`)]);
    if (src.status === 'fulfilled') setSources(src.value.sources ?? null);
    if (inc.status === 'fulfilled') { setRecent(inc.value.incidents ?? []); setIncidents24h(inc.value.total ?? 0); }
    setError(src.status === 'rejected' || inc.status === 'rejected' ? 'Parte dos dados não carregou; exibindo a última leitura válida' : null);
  }, [authHeader]);

  useEffect(() => {
    void refresh();
    const t = window.setInterval(() => { void refresh(); }, 60_000);
    return () => window.clearInterval(t);
  }, [refresh]);

  const matrix = useMemo(() => customerMatrix(problems), [problems]);
  const topHosts = useMemo(() => {
    const m = new Map<string, number>();
    for (const p of problems) m.set(p.host, (m.get(p.host) ?? 0) + 1);
    return [...m.entries()].sort((a, b) => b[1] - a[1]).slice(0, 8);
  }, [problems]);
  const severe = problems.filter(p => p.severity_level >= 4).length;
  const unacked = problems.filter(p => !p.acknowledged && p.severity_level >= 4).length;

  return (
    <Screen>
      <dl className="nx-kpis nx-sticky">
        <div><dt>Problemas ativos</dt><dd>{problems.length}</dd></div>
        <div><dt>Desastre + alta</dt><dd className={severe ? 'bad' : ''}>{severe}</dd></div>
        <div><dt>Graves sem reconhecer</dt><dd className={unacked ? 'bad' : ''}>{unacked}</dd></div>
        <div><dt>Hosts com problema</dt><dd>{new Set(problems.map(p => p.host)).size}</dd></div>
        <div><dt>Hosts monitorados</dt><dd>{hosts?.toLocaleString('pt-BR') ?? '—'}</dd></div>
        <div><dt>Incidentes 24h</dt><dd>{incidents24h?.toLocaleString('pt-BR') ?? '—'}</dd></div>
      </dl>
      {error && <div className="nx-alert warn" role="alert">{error}.</div>}
      {/* ponytail: totais saem da lista limitada a 2.000 (hoje ~800); upgrade path: agregado na API (F2/F3). */}
      {problems.length >= 2000 && <div className="nx-alert warn" role="alert">Mais de 2.000 problemas ativos: as contagens abaixo são parciais.</div>}

      <Panel title="Fontes" meta={<span className="nx-meta">Zabbix {observedAt ? timeAgo(observedAt.toISOString()) : 'sem leitura'}</span>} flush>
        <ol className="nx-flow">
          {([['zabbix', 'Zabbix', 'Monitoramento de infraestrutura'], ['wazuh', 'Wazuh', 'Eventos de segurança'], ['glpi', 'GLPI', 'Chamados']] as const).map(([k, label, role]) => {
            const s = sources?.[k];
            const [tone, text] = s ? SOURCE[s.status] : ['neutral', 'Sem leitura'] as [Tone, string];
            return (
              <li key={k}>
                <div className="nx-actions"><strong>{label}</strong><Badge tone={tone}>{text}</Badge></div>
                <span className="nx-muted">{role}</span>
                <span>{s?.status === 'planned' ? 'Alertas ainda não chegam ao Hub' : s?.last_success_at ? `Última coleta ${timeAgo(s.last_success_at)}` : '—'}{s?.error_code && s.status !== 'planned' ? ` · ${s.error_code}` : ''}</span>
              </li>
            );
          })}
        </ol>
      </Panel>

      {pipeline}

      <div className="nx-cols">
        <Panel title="Problemas por cliente" meta={<span className="nx-meta">{matrix.length} clientes</span>} flush>
          {!matrix.length ? <div className="nx-empty">Nenhum problema ativo.</div> :
            <table className="nx-table nx-dense nx-matrix">
              <thead><tr><th>Cliente</th>{SEV.map(l => <th key={l}>{sevLabel(l)}</th>)}<th>Total</th></tr></thead>
              <tbody>{matrix.map(([c, r]) => (
                <tr key={c}>
                  <td><button type="button" className="nx-btn nx-link" onClick={() => go('monitoring', `&cliente=${encodeURIComponent(c)}`)}>{c}</button></td>
                  {SEV.map(l => <td key={l} className={`nx-mono ${l >= 4 && r[l] ? 'nx-bad' : r[l] ? '' : 'nx-muted'}`}>{r[l] || '·'}</td>)}
                  <td className="nx-mono">{r.reduce((a, b) => a + b, 0)}</td>
                </tr>
              ))}</tbody>
            </table>}
        </Panel>
        <Panel title="Hosts com mais problemas" flush>
          {!topHosts.length ? <div className="nx-empty">Nenhum problema ativo.</div> :
            <table className="nx-table nx-dense">
              <thead><tr><th>Host</th><th>Problemas</th></tr></thead>
              <tbody>{topHosts.map(([h, n]) => (
                <tr key={h}><td><button type="button" className="nx-btn nx-link nx-mono" onClick={() => go('monitoring', `&host=${encodeURIComponent(h)}`)}>{h}</button></td><td className="nx-mono">{n}</td></tr>
              ))}</tbody>
            </table>}
        </Panel>
      </div>

      <Panel title="Incidentes das últimas 24h" meta={<span className="nx-actions"><span className="nx-meta">mais graves primeiro</span><button type="button" className="nx-btn nx-link" onClick={() => go('incidents')}>Ver todos</button></span>} flush>
        {!recent.length ? <div className="nx-empty">Nenhum incidente nas últimas 24h.</div> :
          <table className="nx-table nx-dense">
            <thead><tr><th>Severidade</th><th>Cliente</th><th>Host</th><th>Incidente</th><th>Chamado</th><th>Último</th></tr></thead>
            <tbody>{recent.map(i => {
              const s = SEVERITIES.find(x => x.level === i.severity_level) ?? SEVERITIES[5];
              return (
                <tr key={i.id}>
                  <td><Badge tone={s.tone}>{s.label}</Badge></td>
                  <td>{i.client || '—'}</td>
                  <td className="nx-mono">{i.host_name}</td>
                  <td>{i.title}</td>
                  <td className="nx-mono">{i.ticket_id ? `#${i.ticket_id}` : '—'}</td>
                  <td className="nx-mono">{timeAgo(i.last_seen)}</td>
                </tr>
              );
            })}</tbody>
          </table>}
      </Panel>
    </Screen>
  );
}
