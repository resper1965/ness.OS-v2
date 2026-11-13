import { useCallback, useEffect, useMemo, useState } from 'react';
import { RefreshCw } from 'lucide-react';
import { fmtDate, fmtDateTime } from '../format';
import { asApiError, request, type ApiError } from '../http';
import { Badge, Button, Empty, ErrorState, PageHeader, Panel, Screen, Skeleton, type Tone } from './ui/kit';

interface Risk { level: 'bad' | 'warn'; kind: string; target: string; detail: string }
interface Instance {
  id: number; name: string; status: string; product: string | null; region: string | null; ipv4: string | null;
  cpu: number | null; ram_gb: number; disk_gb: number; cancel_date: string | null; error: string | null;
  firewalls: string[]; networks: string[]; snapshots: number | null; snapshot_age_days: number | null;
}
interface Storage { id: string; name: string; status: string; region: string | null; total_tb: number | null; used_tb: number | null; used_pct: number | null; objects: number | null }
interface Event { at: string | null; kind: string; action: string; target: string; by: string | null; fields: string[] }
export interface Overview {
  observed_at: string;
  fleet: { instances: number; statuses: Record<string, number>; cpu: number; ram_gb: number; disk_gb: number; regions: string[]; firewalls: number; networks: number };
  risks: Risk[]; instances: Instance[]; storages: Storage[]; events: Event[];
}

const STATUS_TONE: Record<string, Tone> = { running: 'ok', stopped: 'warn', error: 'bad', rescue: 'warn' };
const ACTION: Record<string, string> = { CREATED: 'criou', UPDATED: 'alterou', DELETED: 'removeu' };
const RISK: Record<string, string> = { cancel: 'Cancelamento', error: 'Erro', status: 'Parada', firewall: 'Sem firewall', snapshot: 'Snapshot', storage: 'Armazenamento' };
const num = (n: number) => n.toLocaleString('pt-BR');

function Stat({ label, value }: { label: string; value: string }) {
  return <div><div className="nx-meta">{label}</div><div style={{ font: '600 22px/1.2 var(--nx-head)', marginTop: 6 }}>{value}</div></div>;
}

export default function CloudManagement({ refreshKey }: { refreshKey?: number }) {
  const [data, setData] = useState<Overview | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    try { setData(await request<Overview>('/api/contabo/overview')); setError(null); }
    catch (e) { setError(asApiError(e)); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { void load(); }, [load, refreshKey]);

  const rows = useMemo(() => {
    const q = query.trim().toLowerCase();
    return (data?.instances ?? []).filter((i) => !q || i.name.toLowerCase().includes(q) || (i.ipv4 ?? '').includes(q));
  }, [data, query]);

  const f = data?.fleet;
  const bad = data?.risks.filter((r) => r.level === 'bad').length ?? 0;

  return (
    <Screen>
      <PageHeader title="Nuvem" kicker="provedor de nuvem · somente leitura"
        actions={<>
          {data && <span className="nx-muted">Atualizado {fmtDateTime(data.observed_at)}</span>}
          <Button icon={RefreshCw} onClick={() => void load()} disabled={loading}>Atualizar</Button>
        </>} />

      {error && <ErrorState error={error} onRetry={() => void load()} />}
      {loading && !data && <Skeleton rows={6} />}

      {data && f && <>
        <Panel title="Frota">
          <div className="nx-grid">
            <Stat label="Servidores" value={num(f.instances)} />
            <Stat label="vCPU" value={num(f.cpu)} />
            <Stat label="RAM" value={`${num(f.ram_gb)} GB`} />
            <Stat label="Disco" value={`${num(f.disk_gb)} GB`} />
          </div>
          <div className="nx-actions" style={{ marginTop: 16 }}>
            {Object.entries(f.statuses).map(([s, n]) => <Badge key={s} tone={STATUS_TONE[s] ?? 'neutral'}>{s}: {n}</Badge>)}
            <span className="nx-muted">{f.firewalls} firewalls · {f.networks} redes privadas · {f.regions.join(', ') || 'sem região'}</span>
          </div>
        </Panel>

        <Panel title="Riscos" meta={<Badge tone={bad ? 'bad' : data.risks.length ? 'warn' : 'ok'}>{data.risks.length}</Badge>} flush>
          {data.risks.length === 0 ? <Empty title="Nenhum risco encontrado." hint="Snapshots, firewall, cancelamentos e armazenamento em dia." /> : (
            <table className="nx-table">
              <thead><tr><th scope="col">Tipo</th><th scope="col">Recurso</th><th scope="col">Detalhe</th></tr></thead>
              <tbody>{data.risks.map((r, i) => (
                <tr key={i}><td><Badge tone={r.level}>{RISK[r.kind] ?? r.kind}</Badge></td><td>{r.target}</td><td className="nx-muted">{r.detail}</td></tr>
              ))}</tbody>
            </table>
          )}
        </Panel>

        <Panel title="Servidores" meta={<Badge>{rows.length}</Badge>} flush
          actions={<label className="nx-field" style={{ minWidth: 220 }}>
            <span className="sr-only">Buscar servidor</span>
            <input type="search" placeholder="Nome ou IP…" value={query} onChange={(e) => setQuery(e.target.value)} autoComplete="off" spellCheck={false} />
          </label>}>
          {rows.length === 0 ? <Empty title="Nenhum servidor." /> : (
            <div style={{ overflowX: 'auto' }}>
              <table className="nx-table">
                <thead><tr><th scope="col">Servidor</th><th scope="col">Estado</th><th scope="col">Plano</th><th scope="col">Recursos</th><th scope="col">Firewall</th><th scope="col">Snapshot</th></tr></thead>
                <tbody>{rows.map((i) => (
                  <tr key={i.id}>
                    <td><strong>{i.name}</strong><div className="nx-mono nx-muted">{i.ipv4 ?? '—'} · {i.region ?? '—'}</div></td>
                    <td><Badge tone={STATUS_TONE[i.status] ?? 'neutral'}>{i.status}</Badge>{i.cancel_date && <div className="nx-muted">cancela {fmtDate(i.cancel_date)}</div>}</td>
                    <td>{i.product ?? '—'}</td>
                    <td className="nx-mono" style={{ fontVariantNumeric: 'tabular-nums' }}>{i.cpu ?? '—'} vCPU · {i.ram_gb} GB · {i.disk_gb} GB</td>
                    <td>{i.firewalls.length ? i.firewalls.join(', ') : <Badge tone="warn">nenhum</Badge>}</td>
                    <td>{i.snapshots === null ? '—' : i.snapshot_age_days === null ? <Badge tone="warn">nenhum</Badge>
                      : <Badge tone={i.snapshot_age_days > 7 ? 'warn' : 'ok'}>há {i.snapshot_age_days} d</Badge>}</td>
                  </tr>
                ))}</tbody>
              </table>
            </div>
          )}
        </Panel>

        {data.storages.length > 0 && (
          <Panel title="Object Storage" flush>
            <table className="nx-table">
              <thead><tr><th scope="col">Nome</th><th scope="col">Estado</th><th scope="col">Uso</th><th scope="col">Objetos</th></tr></thead>
              <tbody>{data.storages.map((s) => (
                <tr key={s.id}>
                  <td>{s.name}<div className="nx-muted">{s.region ?? '—'}</div></td>
                  <td><Badge>{s.status}</Badge></td>
                  <td>{s.used_pct == null ? `${s.total_tb ?? '—'} TB contratados`
                    : <Badge tone={s.used_pct >= 80 ? 'warn' : 'ok'}>{s.used_pct.toFixed(0)}% de {s.total_tb} TB</Badge>}</td>
                  <td className="nx-mono">{s.objects == null ? '—' : num(s.objects)}</td>
                </tr>
              ))}</tbody>
            </table>
          </Panel>
        )}

        <Panel title="Mudanças nos últimos 7 dias" meta={<Badge>{data.events.length}</Badge>} flush>
          {data.events.length === 0 ? <Empty title="Nenhuma mudança registrada." /> : (
            <table className="nx-table">
              <thead><tr><th scope="col">Quando</th><th scope="col">Quem</th><th scope="col">O quê</th></tr></thead>
              <tbody>{data.events.map((e, i) => (
                <tr key={i}>
                  <td className="nx-mono">{fmtDateTime(e.at)}</td>
                  <td>{e.by ?? '—'}</td>
                  <td>{ACTION[e.action] ?? e.action} {e.kind} <strong>{e.target}</strong>{e.fields.length > 0 && <span className="nx-muted"> ({e.fields.join(', ')})</span>}</td>
                </tr>
              ))}</tbody>
            </table>
          )}
        </Panel>
      </>}
    </Screen>
  );
}
