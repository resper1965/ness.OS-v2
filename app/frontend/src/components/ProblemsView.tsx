import { useEffect, useMemo, useState, type ReactNode } from 'react';
import { Search } from 'lucide-react';
import { Badge, ICON, Panel, Screen, type Tone } from './ui/kit';
import { timeAgo } from '../access';

export interface Problem {
  id: string; title: string; severity: string;
  severity_level: number; host: string; clock: number; acknowledged: boolean;
  customer?: string | null; incident_id?: string | null; ticket_id?: string | null;
}

export const SEVERITIES = [
  { level: 5, label: 'Desastre', tone: 'bad' },
  { level: 4, label: 'Alta', tone: 'bad' },
  { level: 3, label: 'Média', tone: 'warn' },
  { level: 2, label: 'Atenção', tone: 'warn' },
  { level: 1, label: 'Info', tone: 'info' },
  { level: 0, label: 'N/C', tone: 'neutral' },
] as const satisfies readonly { level: number; label: string; tone: Tone }[];

export interface ProblemFilter { sev: number[]; ack: '' | 'yes' | 'no'; q: string; group: '' | 'host' | 'customer'; customer: string }

export function readFilter(search: string): ProblemFilter {
  const p = new URLSearchParams(search);
  const ack = p.get('ack');
  return {
    sev: (p.get('sev') ?? '').split(',').filter(Boolean).map(Number).filter(n => n >= 0 && n <= 5),
    ack: ack === 'yes' || ack === 'no' ? ack : '',
    q: p.get('q') ?? '',
    group: p.get('group') === 'host' || p.get('group') === 'customer' ? (p.get('group') as 'host' | 'customer') : '',
    customer: p.get('cliente') ?? '',
  };
}

function writeFilter(f: ProblemFilter) {
  const url = new URL(window.location.href);
  const set = (k: string, v: string) => (v ? url.searchParams.set(k, v) : url.searchParams.delete(k));
  set('sev', f.sev.join(',')); set('ack', f.ack); set('q', f.q); set('group', f.group); set('cliente', f.customer);
  window.history.replaceState(null, '', url);
}

/** Aplica ack e busca; a severidade fica fora para as contagens dos chips refletirem os outros filtros. */
export function applyFilter(list: Problem[], f: ProblemFilter) {
  const q = f.q.trim().toLowerCase();
  const base = list.filter(p =>
    (!f.ack || p.acknowledged === (f.ack === 'yes')) &&
    (!f.customer || (p.customer ?? NO_CUSTOMER) === f.customer) &&
    (!q || p.title.toLowerCase().includes(q) || p.host.toLowerCase().includes(q)));
  const counts = new Map<number, number>();
  for (const p of base) counts.set(p.severity_level, (counts.get(p.severity_level) ?? 0) + 1);
  const rows = base
    .filter(p => !f.sev.length || f.sev.includes(p.severity_level))
    .sort((a, b) => b.severity_level - a.severity_level || a.clock - b.clock);
  return { rows, counts };
}

export const NO_CUSTOMER = 'Sem cliente';
const customerOf = (p: Problem) => p.customer ?? NO_CUSTOMER;
const GLPI = 'https://n-ticket.ness.com.br/front/ticket.form.php?id=';

const sevOf = (level: number) => SEVERITIES.find(s => s.level === level) ?? SEVERITIES[5];

function Row({ p, hide }: { p: Problem; hide: ProblemFilter['group'] }) {
  const s = sevOf(p.severity_level);
  return (
    <tr>
      <td><Badge tone={s.tone}>{s.label}</Badge></td>
      {hide !== 'customer' && <td>{customerOf(p)}</td>}
      {hide !== 'host' && <td className="nx-mono">{p.host}</td>}
      <td>{p.title}</td>
      <td className="nx-mono" title={new Date(p.clock * 1000).toLocaleString('pt-BR')}>{timeAgo(p.clock)}</td>
      <td>{p.acknowledged ? <Badge tone="ok">Sim</Badge> : <span className="nx-muted">Não</span>}</td>
      <td className="nx-mono">{p.ticket_id
        ? <a className="nx-btn nx-link" href={GLPI + encodeURIComponent(p.ticket_id)} target="_blank" rel="noopener noreferrer">#{p.ticket_id}<span className="sr-only"> (abre em nova aba)</span></a>
        : <span className="nx-muted">—</span>}</td>
    </tr>
  );
}

export default function ProblemsView({ problems, loading, error, observedAt, hosts, items, pipeline }: {
  problems: Problem[]; loading: boolean; error: string | null; observedAt: Date | null;
  hosts?: number; items?: number; pipeline?: ReactNode;
}) {
  const [f, setF] = useState<ProblemFilter>(() => readFilter(window.location.search));
  useEffect(() => { writeFilter(f); }, [f]);
  const { rows, counts } = useMemo(() => applyFilter(problems, f), [problems, f]);
  const groups = useMemo(() => {
    if (!f.group) return null;
    const key = f.group === 'host' ? (p: Problem) => p.host : customerOf;
    const m = new Map<string, Problem[]>();
    for (const p of rows) m.set(key(p), [...(m.get(key(p)) ?? []), p]);
    return [...m.entries()];
  }, [rows, f.group]);
  const toggleSev = (l: number) => setF(x => ({ ...x, sev: x.sev.includes(l) ? x.sev.filter(v => v !== l) : [...x.sev, l] }));
  const customers = useMemo(() => [...new Set(problems.map(customerOf))].sort(), [problems]);
  const rowHosts = new Set(rows.map(p => p.host)).size;

  return (
    <Screen fill>
      <dl className="nx-kpis">
        <div><dt>Problemas ativos</dt><dd>{problems.length}</dd></div>
        <div><dt>Desastre + alta</dt><dd className={problems.some(p => p.severity_level >= 4) ? 'bad' : ''}>{problems.filter(p => p.severity_level >= 4).length}</dd></div>
        <div><dt>Clientes afetados</dt><dd>{new Set(problems.flatMap(p => p.customer ? [p.customer] : [])).size}</dd></div>
        <div><dt>Hosts com problema</dt><dd>{new Set(problems.map(p => p.host)).size}</dd></div>
        <div><dt>Hosts monitorados</dt><dd>{hosts?.toLocaleString('pt-BR') ?? '—'}</dd></div>
        <div><dt>Itens monitorados</dt><dd>{items?.toLocaleString('pt-BR') ?? '—'}</dd></div>
      </dl>
      {pipeline}
      <div className="nx-filters" role="search" aria-label="Filtrar problemas">
        <label className="nx-search">
          <Search {...ICON} />
          <span className="sr-only">Buscar host ou problema</span>
          <input type="search" placeholder="Host ou problema" value={f.q} onChange={e => setF(x => ({ ...x, q: e.target.value }))} />
        </label>
        <div className="nx-actions" role="group" aria-label="Severidade">
          {SEVERITIES.filter(s => s.level > 0 || counts.get(0)).map(s => (
            <button key={s.level} type="button" className="nx-btn nx-toggle" aria-pressed={f.sev.includes(s.level)} onClick={() => toggleSev(s.level)}>
              {s.label} <span className="nx-mono">{counts.get(s.level) ?? 0}</span>
            </button>
          ))}
        </div>
        <label className="nx-field nx-inline">Cliente
          <select value={f.customer} onChange={e => setF(x => ({ ...x, customer: e.target.value }))}>
            <option value="">Todos</option>
            {customers.map(c => <option key={c}>{c}</option>)}
          </select>
        </label>
        <label className="nx-field nx-inline">Reconhecido
          <select value={f.ack} onChange={e => setF(x => ({ ...x, ack: e.target.value as ProblemFilter['ack'] }))}>
            <option value="">Todos</option><option value="no">Não</option><option value="yes">Sim</option>
          </select>
        </label>
        <label className="nx-field nx-inline">Agrupar
          <select value={f.group} onChange={e => setF(x => ({ ...x, group: e.target.value as ProblemFilter['group'] }))}>
            <option value="">Nenhum</option><option value="customer">Cliente</option><option value="host">Host</option>
          </select>
        </label>
      </div>

      {error && <div className="nx-alert warn" role="alert">{error}. {problems.length ? 'Exibindo a última leitura válida.' : ''}</div>}

      <Panel
        title="Problemas ativos"
        meta={<span className="nx-meta">{rows.length} problemas · {rowHosts} hosts · Zabbix {observedAt ? timeAgo(observedAt.toISOString()) : 'sem leitura'}</span>}
        flush
      >
        {loading && !problems.length ? <div className="nx-skel" aria-label="Carregando" /> :
          !rows.length ? <div className="nx-empty">{problems.length ? 'Nenhum problema com esses filtros.' : 'Nenhum problema ativo.'}</div> :
          <table className="nx-table nx-dense">
            <thead><tr><th>Severidade</th>{f.group !== 'customer' && <th>Cliente</th>}{f.group !== 'host' && <th>Host</th>}<th>Problema</th><th>Desde</th><th>Reconhecido</th><th>Chamado</th></tr></thead>
            {groups ? groups.map(([host, list]) => (
              <tbody key={host}>
                <tr className="nx-group"><th colSpan={6} scope="rowgroup">{host} <span className="nx-muted">· {list.length}</span></th></tr>
                {list.map(p => <Row key={p.id} p={p} hide={f.group} />)}
              </tbody>
            )) : <tbody>{rows.map(p => <Row key={p.id} p={p} hide="" />)}</tbody>}
          </table>}
      </Panel>
    </Screen>
  );
}
