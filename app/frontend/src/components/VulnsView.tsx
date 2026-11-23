import { useCallback, useEffect, useState } from 'react';
import { Download } from 'lucide-react';
import { asApiError, request, type ApiError } from '../http';
import { Badge, Empty, ErrorState, ICON, Panel, Screen, Skeleton, type Tone } from './ui/kit';

const API_BASE = import.meta.env.VITE_API_URL ?? '';
type Sev = 'Critical' | 'High' | 'Medium' | 'Low';
interface Ranked { key: string | null; count: number }
interface Row {
  customer_id: string; agent: string; os: string | null; package: string | null; version: string | null;
  cve: string; severity: Sev; cvss: number | null; eol: boolean; detected_at: string | null;
}
interface Page {
  total: number; by_severity: Record<Sev, number>; agents: number; eol_agents: number; loaded_at: string | null;
  top_agents: Ranked[]; top_packages: Ranked[]; rows: Row[];
}

export const SEVS: [Sev, string, Tone][] = [['Critical', 'Crítica', 'bad'], ['High', 'Alta', 'bad'], ['Medium', 'Média', 'warn'], ['Low', 'Baixa', 'neutral']];
const PAGE = 100;
const FIELDS = [['agent', 'Máquina'], ['cve', 'CVE'], ['package', 'Pacote'], ['os', 'Sistema'], ['customer_id', 'Cliente']] as const;
type Filters = Partial<Record<(typeof FIELDS)[number][0] | 'severity' | 'eol', string>>;

// Filtros vazios não vão à URL; o escopo do cliente quem fixa é a API.
export const vulnQuery = (f: Filters, tenant: string | null, offset = 0) => {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries({ ...f, ...(tenant && { customer_id: tenant }) })) if (v?.trim()) qs.set(k, v.trim());
  if (offset) qs.set('offset', String(offset));
  return qs;
};
const n = (v: number) => v.toLocaleString('pt-BR');

function Top({ title, items }: { title: string; items: Ranked[] }) {
  return (
    <Panel title={title} flush>
      {!items.length ? <Empty title="Sem dados." /> : (
        <table className="nx-table nx-dense"><tbody>
          {items.map(t => <tr key={t.key ?? '—'}><td>{t.key ?? '—'}</td><td className="nx-mono" style={{ textAlign: 'right' }}>{n(t.count)}</td></tr>)}
        </tbody></table>
      )}
    </Panel>
  );
}

export default function VulnsView({ tenant, isOperator, refreshKey = 0 }: { tenant: string | null; isOperator: boolean; refreshKey?: number }) {
  const [draft, setDraft] = useState<Filters>({});
  const [filters, setFilters] = useState<Filters>({});
  const [offset, setOffset] = useState(0);
  const [data, setData] = useState<Page | null>(null);
  const [error, setError] = useState<ApiError | null>(null);

  const load = useCallback(async () => {
    try {
      setData(await request<Page>(`/api/secops/vulnerabilities?${vulnQuery(filters, tenant, offset)}`));
      setError(null);
    } catch (e) { setError(asApiError(e)); }
  }, [filters, tenant, offset, refreshKey]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { void load(); }, [load]);

  const apply = (f: Filters) => { setFilters(f); setOffset(0); };
  const qs = vulnQuery(filters, tenant).toString();

  return (
    <Screen>
      <form className="nx-filters" role="search" aria-label="Filtrar vulnerabilidades" onSubmit={e => { e.preventDefault(); apply(draft); }}>
        {FIELDS.filter(([k]) => k !== 'customer_id' || (isOperator && !tenant)).map(([k, label]) => (
          <label key={k} className="nx-field nx-inline">{label}
            <input value={draft[k] ?? ''} maxLength={128} onChange={e => setDraft(d => ({ ...d, [k]: e.target.value }))} />
          </label>
        ))}
        <label className="nx-field nx-inline">Severidade
          <select value={draft.severity ?? ''} onChange={e => { const d = { ...draft, severity: e.target.value }; setDraft(d); apply(d); }}>
            <option value="">Todas</option>
            {SEVS.map(([k, label]) => <option key={k} value={k}>{label}</option>)}
          </select>
        </label>
        <label className="nx-field nx-inline">Sistema sem suporte
          <select value={draft.eol ?? ''} onChange={e => { const d = { ...draft, eol: e.target.value }; setDraft(d); apply(d); }}>
            <option value="">Todos</option><option value="true">Só sem suporte</option><option value="false">Sem os sem suporte</option>
          </select>
        </label>
        <button type="submit" className="nx-btn">Filtrar</button>
        <a className="nx-btn" href={`${API_BASE}/api/secops/vulnerabilities/export${qs ? `?${qs}` : ''}`} download><Download {...ICON} />Exportar planilha</a>
      </form>

      {error && <ErrorState error={error} onRetry={() => void load()} />}
      {!data && !error && <Skeleton rows={6} />}

      {data && <>
        <dl className="nx-kpis">
          {SEVS.map(([k, label]) => <div key={k}><dt>{label}</dt><dd className={k === 'Critical' && data.by_severity[k] ? 'bad' : ''}>{n(data.by_severity[k])}</dd></div>)}
          <div><dt>Máquinas</dt><dd>{n(data.agents)}</dd></div>
          <div><dt>Sistema sem suporte</dt><dd className={data.eol_agents ? 'bad' : ''}>{n(data.eol_agents)}</dd></div>
        </dl>
        <div className="nx-cols"><Top title="10 máquinas mais expostas" items={data.top_agents} /><Top title="10 pacotes mais vulneráveis" items={data.top_packages} /></div>

        <Panel title="Vulnerabilidades" flush
          meta={<span className="nx-meta">{n(data.total)} no filtro{data.loaded_at && ` · coleta de ${new Date(data.loaded_at).toLocaleDateString('pt-BR')}`}</span>}
          actions={data.total > PAGE && <div className="nx-actions">
            <button type="button" className="nx-btn" disabled={!offset} onClick={() => setOffset(o => Math.max(0, o - PAGE))}>Anterior</button>
            <span className="nx-meta">{n(offset + 1)}–{n(Math.min(offset + PAGE, data.total))}</span>
            <button type="button" className="nx-btn" disabled={offset + PAGE >= data.total} onClick={() => setOffset(o => o + PAGE)}>Próxima</button>
          </div>}>
          {!data.rows.length ? <Empty title="Nenhuma vulnerabilidade no filtro." hint="A coleta é mensal, no dia 1º." /> : (
            <table className="nx-table nx-dense nx-cards">
              <thead><tr>{isOperator && <th>Cliente</th>}<th>Máquina</th><th>Sistema</th><th>Pacote</th><th>CVE</th><th>Severidade</th><th>CVSS</th></tr></thead>
              <tbody>{data.rows.map((r, i) => {
                const sev = SEVS.find(([k]) => k === r.severity);
                return (
                  <tr key={`${r.agent}-${r.cve}-${r.package}-${i}`}>
                    {isOperator && <td>{r.customer_id}</td>}
                    <td className="nx-mono">{r.agent}</td>
                    <td>{r.os ?? '—'}</td>
                    <td>{r.package ?? '—'} <span className="nx-muted">{r.version}</span></td>
                    <td className="nx-mono">{r.eol ? 'Sistema sem suporte' : r.cve}</td>
                    <td><Badge tone={sev?.[2] ?? 'neutral'}>{sev?.[1] ?? r.severity}</Badge></td>
                    <td className="nx-mono">{r.cvss ?? '—'}</td>
                  </tr>
                );
              })}</tbody>
            </table>
          )}
        </Panel>
      </>}
    </Screen>
  );
}
