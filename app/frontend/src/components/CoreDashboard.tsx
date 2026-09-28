import { useCallback, useEffect, useState, type ElementType } from 'react';
import { ArrowUpRight, Database, RefreshCw, Server, Shield, Ticket } from 'lucide-react';

const API_BASE = import.meta.env.VITE_API_URL ?? '';

type SourceState = 'ok' | 'degraded' | 'down' | 'planned' | 'unavailable';

interface SourceStatus {
  status: SourceState;
  source: string;
  observed_at: string;
  last_success_at: string | null;
  freshness_seconds: number | null;
  stale: boolean;
  error_code: string | null;
  data: Record<string, unknown> | null;
}

type Sources = Record<'zabbix' | 'atera' | 'glpi' | 'wazuh', SourceStatus>;

function sourceLabel(source: SourceStatus | undefined): string {
  if (!source) return 'sem coleta';
  if (source.status === 'unavailable') return 'não configurada';
  if (source.status === 'down') return 'indisponível';
  if (source.status === 'degraded') return source.stale ? 'Dados desatualizados' : 'coleta sem histórico';
  if (source.status === 'planned') return 'planejada';
  if (source.status === 'ok') return 'conectada';
  return 'estado desconhecido';
}

function lastSuccess(source: SourceStatus | undefined): string {
  if (!source?.last_success_at) return 'Nenhuma coleta válida registrada';
  const date = new Date(source.last_success_at);
  if (Number.isNaN(date.getTime())) return 'Horário da coleta indisponível';
  return `Última coleta válida: ${date.toLocaleString('pt-BR')}`;
}

function metric(source: SourceStatus | undefined, key: string): string {
  const value = source?.data?.[key];
  return typeof value === 'number' ? value.toLocaleString('pt-BR') : '—';
}

function SourceLine({ icon: Icon, title, source, onOpen }: {
  icon: ElementType;
  title: string;
  source?: SourceStatus;
  onOpen?: () => void;
}) {
  const tone = source?.status === 'ok' ? 'text-emerald-300' : source?.status === 'degraded' ? 'text-amber-300' : 'text-white/45';
  return <div className="flex items-center gap-3 border-b border-white/[0.06] py-4 last:border-b-0">
    <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-white/[0.05] text-[#00ADE8]"><Icon size={16} /></div>
    <div className="min-w-0 flex-1">
      <p className="text-sm font-medium text-white">{title}</p>
      <p className="mt-1 text-xs text-white/45">{lastSuccess(source)}</p>
      {source?.error_code && ['degraded', 'down'].includes(source.status) && <p className="mt-1 text-xs text-amber-300">Falha: {source.error_code}</p>}
    </div>
    <span className={`text-right text-xs ${tone}`}>{sourceLabel(source)}</span>
    {onOpen && <button type="button" onClick={onOpen} className="rounded-md p-2 text-white/55 hover:text-white" aria-label={`Abrir ${title}`}><ArrowUpRight size={15} /></button>}
  </div>;
}

export default function CoreDashboard({ authHeader, onModuleSwitch }: {
  authHeader: Record<string, string>;
  onModuleSwitch: (module: 'infraops' | 'secops') => void;
}) {
  const [sources, setSources] = useState<Sources | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE}/api/dashboard/sources`, { headers: authHeader });
      if (response.status === 401 || response.status === 403) {
        setSources(null);
        throw new Error('Sessão sem acesso às fontes operacionais');
      }
      if (!response.ok) throw new Error('Falha ao consultar as fontes operacionais');
      const payload = await response.json() as { sources: Sources };
      if (!payload.sources) throw new Error('Resposta de fontes inválida');
      setSources(payload.sources);
      setError(null);
    } catch (cause) {
      setSources(previous => previous && Object.fromEntries(
        Object.entries(previous).map(([key, source]) => [
          key,
          source.status === 'ok' ? { ...source, status: 'degraded', stale: true, error_code: 'dashboard_unreachable' } : source,
        ]),
      ) as Sources);
      setError(cause instanceof Error ? cause.message : 'Falha ao consultar as fontes operacionais');
    } finally {
      setLoading(false);
    }
  }, [authHeader]);

  useEffect(() => { void refresh(); }, [refresh]);
  useEffect(() => {
    const interval = window.setInterval(() => { void refresh(); }, 60_000);
    return () => window.clearInterval(interval);
  }, [refresh]);

  const zabbix = sources?.zabbix;
  const atera = sources?.atera;
  const glpi = sources?.glpi;
  const readings = [
    { label: 'Hosts Zabbix', value: metric(zabbix, 'hosts_active'), source: zabbix },
    { label: 'Problemas críticos', value: metric(zabbix, 'problems_critical'), source: zabbix },
    { label: 'Agentes Atera', value: metric(atera, 'agents_total'), source: atera },
    { label: 'Entidades GLPI', value: metric(glpi, 'entity_count'), source: glpi },
  ];

  return <div className="min-h-full bg-[#090c13] px-5 py-6 text-white sm:px-8 lg:px-10">
    <header className="flex flex-wrap items-end justify-between gap-4 border-b border-white/[0.08] pb-5">
      <div><h1 className="text-2xl font-semibold">Visão geral</h1><p className="mt-1 text-sm text-white/45">Valores e última coleta válida de cada fonte.</p></div>
      <button type="button" onClick={() => { void refresh(); }} disabled={loading} className="inline-flex items-center gap-2 rounded-md border border-white/[0.10] px-3 py-2 text-xs text-white/70 disabled:opacity-50"><RefreshCw size={13} className={loading ? 'animate-spin' : ''} />Tentar novamente</button>
    </header>

    {error && <p role="alert" className="mt-5 border border-amber-400/30 bg-amber-400/10 p-3 text-sm text-amber-200">{error}. {sources ? 'Dados desatualizados exibidos abaixo.' : 'Nenhum dado válido disponível.'}</p>}
    <section className="mt-7 border border-white/[0.09] bg-white/[0.02] p-5 sm:p-6" aria-label="Estado das fontes">
      <div className="mb-3 flex items-center justify-between"><h2 className="text-sm font-semibold">Fontes operacionais</h2>{loading && <span role="status" className="text-xs text-white/45">Consultando fontes…</span>}</div>
      <SourceLine icon={Server} title="Zabbix" source={zabbix} onOpen={() => onModuleSwitch('infraops')} />
      <SourceLine icon={Database} title="Atera" source={atera} onOpen={() => onModuleSwitch('infraops')} />
      <SourceLine icon={Ticket} title="GLPI" source={glpi} />
      <SourceLine icon={Shield} title="SecOps / Wazuh" source={sources?.wazuh} onOpen={() => onModuleSwitch('secops')} />
    </section>

    <section className="mt-6 border border-white/[0.09] bg-white/[0.02] p-5 sm:p-6" aria-label="Leituras operacionais">
      <h2 className="text-sm font-semibold">Leituras disponíveis</h2>
      <div className="mt-5 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">{readings.map(item => <div key={item.label} className="border-l border-white/[0.12] pl-4"><p className="text-xs text-white/45">{item.label}</p><p className="mt-2 text-2xl font-semibold tabular-nums">{item.value}</p><p className={`mt-1 text-xs ${item.source?.stale ? 'text-amber-300' : 'text-white/45'}`}>{sourceLabel(item.source)}</p></div>)}</div>
    </section>
  </div>;
}
