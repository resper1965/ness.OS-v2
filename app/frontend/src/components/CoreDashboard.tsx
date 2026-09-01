import React, { useCallback, useEffect, useState } from 'react';
import { ArrowUpRight, Check, CircleAlert, Database, RefreshCw, Server, Shield, Ticket } from 'lucide-react';

const API_BASE = import.meta.env.VITE_API_URL ?? '';
type ModuleStatus = 'ok' | 'degraded' | 'not_configured' | 'unknown';

interface Overview {
  modules: {
    infraops: { status: ModuleStatus; metrics: Record<string, number> };
    secops: { status: ModuleStatus; metrics: Record<string, number> };
  };
}
interface KPI {
  id: string; label: string; value: number; unit: string;
  status: 'ok' | 'partial' | 'provisional' | 'unavailable';
}

function state(status: ModuleStatus) {
  if (status === 'ok') return { label: 'conectado', tone: 'text-emerald-300', dot: 'bg-emerald-400' };
  if (status === 'degraded') return { label: 'degradado', tone: 'text-amber-300', dot: 'bg-amber-400' };
  if (status === 'not_configured') return { label: 'não integrado', tone: 'text-white/40', dot: 'bg-white/30' };
  return { label: 'em verificação', tone: 'text-white/40', dot: 'bg-white/30' };
}

function Metric({ kpi }: { kpi: KPI }) {
  const unavailable = kpi.status === 'unavailable';
  return <div className="border-l border-white/[0.10] px-4 first:border-l-0 first:pl-0">
    <p className="text-[10px] font-medium uppercase tracking-[0.12em] text-white/40">{kpi.label}</p>
    <div className="mt-1 flex items-baseline gap-1.5">
      <span className="text-2xl font-semibold tabular-nums text-white">{unavailable ? '—' : kpi.value}</span>
      <span className="text-[11px] text-white/35">{kpi.unit}</span>
    </div>
    <span className={`mt-1.5 inline-flex text-[10px] ${unavailable ? 'text-amber-200/70' : 'text-white/35'}`}>
      {unavailable ? 'fonte indisponível' : kpi.status === 'provisional' ? 'fonte em homologação' : 'fonte conectada'}
    </span>
  </div>;
}

function SourceLine({ icon: Icon, title, detail, status, onOpen }: {
  icon: React.ElementType; title: string; detail: string; status: ModuleStatus; onOpen?: () => void;
}) {
  const current = state(status);
  return <div className="grid grid-cols-[28px_1fr_auto] items-center gap-3 border-b border-white/[0.06] py-4 last:border-b-0">
    <div className="flex h-7 w-7 items-center justify-center rounded-md bg-white/[0.05] text-[#00ADE8]"><Icon size={14} strokeWidth={1.8} /></div>
    <div className="min-w-0"><p className="text-sm font-medium text-white">{title}</p><p className="mt-0.5 truncate text-xs text-white/40">{detail}</p></div>
    <div className="flex items-center gap-3">
      <span className={`hidden items-center gap-1.5 text-[11px] sm:flex ${current.tone}`}><span className={`h-1.5 w-1.5 rounded-full ${current.dot}`} />{current.label}</span>
      {onOpen && <button onClick={onOpen} className="rounded-md p-1.5 text-white/35 transition-colors hover:bg-white/[0.06] hover:text-white" aria-label={`Abrir ${title}`}><ArrowUpRight size={14} /></button>}
    </div>
  </div>;
}

export default function CoreDashboard({ authHeader, onModuleSwitch }: {
  authHeader: Record<string, string>; onModuleSwitch: (module: 'infraops' | 'secops') => void;
}) {
  const [overview, setOverview] = useState<Overview | null>(null);
  const [kpis, setKpis] = useState<KPI[]>([]);
  const [loading, setLoading] = useState(true);
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null);
  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const [overviewResponse, kpisResponse] = await Promise.all([
        fetch(`${API_BASE}/api/core/overview`, { headers: authHeader }),
        fetch(`${API_BASE}/api/core/kpis`, { headers: authHeader }),
      ]);
      if (overviewResponse.ok) setOverview(await overviewResponse.json());
      if (kpisResponse.ok) setKpis((await kpisResponse.json()).kpis ?? []);
      setUpdatedAt(new Date());
    } finally { setLoading(false); }
  }, [authHeader]);
  useEffect(() => { refresh(); }, [refresh]);
  useEffect(() => { const interval = window.setInterval(refresh, 60_000); return () => window.clearInterval(interval); }, [refresh]);
  const infra = overview?.modules.infraops;
  const secops = overview?.modules.secops;

  return <div className="min-h-full bg-[#090c13] px-5 py-6 text-white sm:px-8 lg:px-10"><div className="w-full">
    <header className="flex flex-wrap items-end justify-between gap-4 border-b border-white/[0.08] pb-5">
      <div><h1 className="text-2xl font-semibold tracking-[-0.02em]">Visão geral</h1><p className="mt-1 text-sm text-white/45">Fontes, capacidade e pendências da operação.</p></div>
      <button onClick={refresh} disabled={loading} className="inline-flex items-center gap-2 rounded-md border border-white/[0.10] px-3 py-2 text-xs font-medium text-white/70 transition-colors hover:border-[#00ADE8]/50 hover:text-white disabled:opacity-50"><RefreshCw size={13} className={loading ? 'animate-spin' : ''} />Atualizar</button>
    </header>

    <section className="mt-7 grid items-stretch gap-6 xl:grid-cols-[minmax(0,2.7fr)_minmax(19rem,0.7fr)]">
      <div className="min-h-[23rem] border border-white/[0.09] bg-white/[0.02] p-5 sm:p-6">
        <div className="flex items-start justify-between gap-4 border-b border-white/[0.07] pb-4"><div><h2 className="text-sm font-semibold">Pulso operacional</h2><p className="mt-1 text-xs text-white/40">Estado das fontes que formam o painel.</p></div><span className="flex shrink-0 items-center gap-1.5 text-[11px] text-white/40"><span className="h-1.5 w-1.5 rounded-full bg-[#00ADE8]" />{updatedAt ? `atualizado ${updatedAt.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })}` : 'carregando'}</span></div>
        <SourceLine icon={Server} title="InfraOps" detail="Zabbix, capacidade e eventos de infraestrutura" status={infra?.status ?? 'unknown'} onOpen={() => onModuleSwitch('infraops')} />
        <SourceLine icon={Shield} title="SecOps" detail="Curadoria de vulnerabilidades e incidentes de segurança" status={secops?.status ?? 'not_configured'} onOpen={() => onModuleSwitch('secops')} />
        <SourceLine icon={Ticket} title="ITSM e inventário" detail="GLPI em estruturação; catálogo e SLA ainda não publicados" status="not_configured" />
        <SourceLine icon={Database} title="Histórico e indicadores" detail="Score executivo depende da homologação de serviços e metas" status="not_configured" />
      </div>
      <aside className="flex min-h-[23rem] flex-col justify-between border border-[#00ADE8]/25 bg-[#00ADE8]/[0.045] p-5 sm:p-6"><div><p className="text-[11px] font-medium uppercase tracking-[0.14em] text-[#00ADE8]">Integridade da visão</p><p className="mt-3 text-xl font-semibold tracking-[-0.02em]">Sem score sintético.</p><p className="mt-2 text-sm leading-6 text-white/55">A saúde executiva só será calculada quando catálogo, SLOs, fontes e regras de correlação estiverem homologados.</p></div><div className="border-t border-[#00ADE8]/20 pt-4 text-xs leading-5 text-white/55"><span className="mr-2 inline-flex h-5 w-5 items-center justify-center rounded-full bg-[#00ADE8]/15 text-[#00ADE8]"><Check size={12} /></span>O painel prioriza evidência sobre aparência.</div></aside>
    </section>

    <section className="mt-6 border border-white/[0.09] bg-white/[0.02] p-5 sm:p-6"><div className="mb-5 flex items-center justify-between gap-4"><div><h2 className="text-sm font-semibold">Leituras disponíveis</h2><p className="mt-1 text-xs text-white/40">Indicadores apresentados com o estado da respectiva fonte.</p></div><CircleAlert size={16} className="text-amber-300/80" aria-label="Dados em homologação" /></div><div className="grid gap-y-6 sm:grid-cols-2 lg:grid-cols-4">{loading && !kpis.length ? Array.from({ length: 4 }).map((_, index) => <div key={index} className="h-16 animate-pulse border-l border-white/[0.08] bg-white/[0.03] first:border-l-0" />) : kpis.map((kpi) => <Metric key={kpi.id} kpi={kpi} />)}</div></section>

    <section className="mt-6 grid gap-3 md:grid-cols-3">{[['Zabbix', 'Dados são de uma cópia restaurada em UAT; a coleta de produção permanece protegida.'], ['GLPI', 'Inventário, catálogo e SLA aguardam a fonte canônica e a homologação do processo.'], ['SecOps', 'A base de CVEs é referência estática até a coleta e a curadoria entrarem em operação.']].map(([title, body]) => <div key={title} className="border-t border-white/[0.12] pt-3"><h3 className="text-xs font-semibold text-white/80">{title}</h3><p className="mt-1.5 text-xs leading-5 text-white/40">{body}</p></div>)}</section>
  </div></div>;
}
