import { Activity, ShieldAlert, Users, Server, Settings, Cloud, RefreshCw,
         Wifi, WifiOff, Monitor, AlertTriangle, CheckCircle, BarChart3,
         Layers, Cpu, LogOut, Globe, Shield } from 'lucide-react';
import React, { useState, useEffect, useCallback } from 'react';
import CloudManagement from './components/CloudManagement';
import PipelineStrip from './components/PipelineStrip';
import IncidentsPage from './components/IncidentsPage';
import TenantSelector from './components/TenantSelector';
import SecurityAlerts from './components/SecurityAlerts';
import LoginPage from './components/LoginPage';
import ModuleSwitcher, { type NessModule } from './components/ModuleSwitcher';
import CoreDashboard from './components/CoreDashboard';
import { useAuth } from './hooks/useAuth';

const API_BASE = import.meta.env.VITE_API_URL ?? '';

const PAGE_TITLES: Record<string, string> = {
  dashboard: 'Dashboard',
  cloud: 'Nuvem',
  infrastructure: 'Infraestrutura',
  incidents: 'Incidentes',
  tenants: 'Clientes',
  settings: 'Configurações',
};

const SEVERITY_BG: Record<string, string> = {
  disaster:       'bg-red-500/15 border-red-500/30 text-red-400',
  high:           'bg-red-400/10 border-red-400/25 text-red-400',
  average:        'bg-orange-400/10 border-orange-400/25 text-orange-400',
  warning:        'bg-yellow-400/10 border-yellow-400/25 text-yellow-400',
  info:           'bg-blue-400/10 border-blue-400/25 text-blue-400',
  not_classified: 'bg-white/5 border-white/10 text-white/40',
};

const SEVERITY_DOT: Record<string, string> = {
  disaster:       'bg-red-500 shadow-[0_0_6px_rgba(239,68,68,0.8)]',
  high:           'bg-red-400 shadow-[0_0_5px_rgba(248,113,113,0.6)]',
  average:        'bg-orange-400 shadow-[0_0_5px_rgba(251,146,60,0.6)]',
  warning:        'bg-yellow-400 shadow-[0_0_4px_rgba(250,204,21,0.5)]',
  info:           'bg-blue-400',
  not_classified: 'bg-white/30',
};

const SEVERITY_LABEL: Record<string, string> = {
  disaster: 'Desastre', high: 'Alta', average: 'Média',
  warning: 'Aviso', info: 'Info', not_classified: 'N/C',
};

type View = 'dashboard' | 'cloud' | 'incidents';

interface Summary {
  hosts_active: number;
  items_total: number;
  problems_critical: number;
  problems_warning: number;
  problems_total: number;
}

interface Problem {
  id: string; title: string; severity: string;
  severity_level: number; host: string; clock: number; acknowledged: boolean;
}

// ─── Helpers ───────────────────────────────────────────────────────────────
function timeAgo(clock: number): string {
  const s = Math.floor(Date.now() / 1000) - clock;
  if (s < 60) return `há ${s}s`;
  if (s < 3600) return `há ${Math.floor(s / 60)}min`;
  if (s < 86400) return `há ${Math.floor(s / 3600)}h`;
  return `há ${Math.floor(s / 86400)}d`;
}
function formatNumber(n: number): string {
  if (n >= 1000000) return `${(n / 1000000).toFixed(1)}M`;
  if (n >= 1000) return `${(n / 1000).toFixed(0)}k`;
  return String(n);
}

// ── Brand Logo ───────────────────────────────────────────────────────────────────────
function BrandLogo({ activeModule }: { activeModule: NessModule }) {
  const MODULE_COLOR: Record<NessModule, string> = {
    core: '#6366F1',
    infraops: '#3B82F6',
    secops: '#EF4444',
  };
  const MODULE_SUB: Record<NessModule, string> = {
    core: 'core',
    infraops: 'n.infraops',
    secops: 'n.secops',
  };
  const color = MODULE_COLOR[activeModule];
  return (
    <div className="flex flex-col items-start px-1">
      <div
        style={{ fontFamily: "'Montserrat', sans-serif", fontWeight: 500 }}
        className="text-[24px] tracking-tight text-white leading-none select-none"
      >
        ness<span style={{ color, textShadow: `0 0 12px ${color}99` }}>.</span>OS
      </div>
      <div
        style={{ fontFamily: "'Fira Code', monospace", fontWeight: 500, color }}
        className="text-[10px] tracking-[0.1em] lowercase leading-none mt-1 opacity-90 select-none transition-colors duration-300"
      >
        {MODULE_SUB[activeModule]}
      </div>
    </div>
  );
}

// ─── Sidebar Item ────────────────────────────────────────────────────────────
function SidebarItem({
  icon: Icon, label, active = false, onClick, disabled = false,
}: {
  icon: React.ElementType; label: string; active?: boolean;
  onClick?: () => void; disabled?: boolean;
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled || !onClick}
      aria-current={active ? 'page' : undefined}
      aria-disabled={disabled ? 'true' : undefined}
      title={disabled ? 'Em breve' : undefined}
      className={`
        w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-left
        transition-all duration-200 relative group select-none
        ${active
          ? 'text-white'
          : disabled || !onClick
            ? 'text-white/20 cursor-not-allowed'
            : 'text-[var(--color-brand-muted)] hover:text-white/90 hover:bg-white/[0.04]'
        }
      `}
      style={active ? {
        background: 'linear-gradient(90deg, rgba(0,173,232,0.14) 0%, rgba(0,173,232,0.04) 100%)',
      } : {}}
    >
      {active && (
        <span
          className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-6 rounded-r-full"
          style={{ background: '#00ADE8', boxShadow: '0 0 8px rgba(0,173,232,0.7)' }}
        />
      )}
      <Icon size={18} className={active ? 'text-[#00ADE8]' : ''} />
      <span className={`font-medium text-sm ${active ? 'text-white' : 'text-slate-400'}`}>{label}</span>
      {disabled && (
        <span className="ml-auto text-[9px] font-medium px-1.5 py-0.5 rounded bg-white/[0.04] text-white/20 leading-none">
          breve
        </span>
      )}
    </button>
  );
}

// ─── Metric Card ─────────────────────────────────────────────────────────────
function MetricCard({
  title, value, status = 'neutral', loading = false, icon: Icon, suffix = '',
}: {
  title: string; value: string | number; suffix?: string;
  status?: 'success' | 'danger' | 'warning' | 'neutral';
  loading?: boolean; icon?: React.ElementType;
}) {
  const colors = {
    success: { text: 'text-emerald-400', glow: 'rgba(16,185,129,0.15)', border: 'border-emerald-500/15' },
    danger:  { text: 'text-red-400',     glow: 'rgba(239,68,68,0.15)',  border: 'border-red-500/15'     },
    warning: { text: 'text-yellow-400',  glow: 'rgba(245,158,11,0.12)', border: 'border-yellow-500/15'  },
    neutral: { text: 'text-white',       glow: 'transparent',           border: 'border-transparent'    },
  }[status];

  return (
    <div
      className={`
        relative bg-[var(--color-brand-surface)] border border-white/[0.06]
        ${colors.border} rounded-xl p-5 flex flex-col gap-3 overflow-hidden
        hover:border-white/10 transition-all duration-300 hover:-translate-y-0.5
        hover:shadow-[0_8px_30px_rgba(0,0,0,0.3)] group
      `}
      style={status !== 'neutral' ? {
        boxShadow: `inset 0 1px 0 rgba(255,255,255,0.04), 0 0 0 1px rgba(255,255,255,0.03)`,
      } : {}}
    >
      {/* Top glow */}
      {status !== 'neutral' && (
        <div
          className="absolute top-0 inset-x-0 h-px rounded-t-xl"
          style={{ background: `linear-gradient(90deg, transparent, ${colors.glow.replace('0.15', '0.5')}, transparent)` }}
        />
      )}

      {/* Header row */}
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-[var(--color-brand-muted)] uppercase tracking-wider">
          {title}
        </span>
        {Icon && (
          <div className={`p-1.5 rounded-md bg-white/[0.04] ${colors.text} opacity-60 group-hover:opacity-100 transition-opacity`}>
            <Icon size={13} />
          </div>
        )}
      </div>

      {/* Value */}
      {loading ? (
        <div className="h-9 w-20 bg-white/[0.06] rounded-lg animate-pulse" />
      ) : (
        <div className={`text-3xl font-bold tracking-tight ${colors.text} tabular-nums`}>
          {value}<span className="text-base font-medium opacity-60 ml-1">{suffix}</span>
        </div>
      )}
    </div>
  );
}

// ─── Problem Row ─────────────────────────────────────────────────────────────
function ProblemRow({ p }: { p: Problem }) {
  return (
    <div
      role="article"
      aria-label={`Alerta: ${p.title}`}
      className="
        flex items-center justify-between px-3 py-2.5 rounded-lg
        border border-transparent hover:border-white/[0.06] hover:bg-white/[0.025]
        transition-all duration-200 group
      "
    >
      <div className="flex items-center gap-3 min-w-0">
        <div className={`w-2 h-2 rounded-full shrink-0 ${SEVERITY_DOT[p.severity] || 'bg-gray-500'}`} />
        <div className="min-w-0">
          <p className="font-medium text-sm truncate text-white/90 group-hover:text-white transition-colors">
            {p.title}
          </p>
          <p className="text-[11px] text-[var(--color-brand-muted)] mt-0.5 truncate">{p.host}</p>
        </div>
      </div>

      <div className="flex items-center gap-2.5 shrink-0 ml-4">
        <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full border ${SEVERITY_BG[p.severity] || ''}`}>
          {SEVERITY_LABEL[p.severity] || p.severity}
        </span>
        <span className="text-[11px] text-[var(--color-brand-muted)] tabular-nums w-8 text-right">
          {timeAgo(p.clock)}
        </span>
      </div>
    </div>
  );
}

// ─── Section Card ─────────────────────────────────────────────────────────────
function SectionCard({ title, count, children, loading }: {
  title: string; count?: number; children: React.ReactNode; loading?: boolean;
}) {
  return (
    <div className="bg-[var(--color-brand-surface)] border border-white/[0.06] rounded-xl overflow-hidden">
      <div className="flex items-center justify-between px-5 py-3.5 border-b border-white/[0.04]">
        <span className="text-[11px] font-semibold text-[var(--color-brand-muted)] uppercase tracking-[0.12em]">
          {title}
        </span>
        {count !== undefined && (
          <span className="text-[11px] font-medium px-2 py-0.5 rounded-full bg-white/[0.05] text-[var(--color-brand-muted)]">
            {count}
          </span>
        )}
      </div>
      <div className="p-3">
        {loading ? (
          <div className="space-y-2 p-2">
            {[1,2,3].map(i => <div key={i} className="h-11 bg-white/[0.04] rounded-lg animate-pulse" />)}
          </div>
        ) : children}
      </div>
    </div>
  );
}

// ─── App Shell Body ──────────────────────────────────────────────────────────
function AppShellBody({ AUTH, logout, user }: {
  AUTH: Record<string, string>;
  logout: () => void;
  user: import('./hooks/useAuth').User | null;
}) {
  const [activeModule, setActiveModule] = useState<NessModule>('core');
  const [currentView, setCurrentView] = useState<View>('dashboard');
  const [selectedTenant, setSelectedTenant] = useState<string | null>(null);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [problems, setProblems] = useState<Problem[]>([]);
  const [pipeline, setPipeline] = useState<any>(null);
  const [pipelineLoading, setPipelineLoading] = useState(true);
  const [incidents, setIncidents] = useState<any[]>([]);
  const [incidentsLoading, setIncidentsLoading] = useState(false);
  const [incidentsError, setIncidentsError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);

  const fetchData = useCallback(async () => {
    try {
      const query = selectedTenant ? `?customer_id=${selectedTenant}` : '';
      const [summaryRes, problemsRes, pipelineRes] = await Promise.all([
        fetch(`${API_BASE}/api/dashboard/summary${query}`, { headers: AUTH }),
        fetch(`${API_BASE}/api/dashboard/problems${selectedTenant ? query + '&' : '?'}limit=15`, { headers: AUTH }),
        fetch(`${API_BASE}/api/dashboard/pipeline-status${query}`, { headers: AUTH }),
      ]);
      if (!summaryRes.ok || !problemsRes.ok) throw new Error('API error');
      setSummary(await summaryRes.json());
      setProblems((await problemsRes.json()).problems || []);
      if (pipelineRes.ok) setPipeline(await pipelineRes.json());
      setError(null);
      setLastUpdate(new Date());
    } catch {
      setError('Não foi possível conectar à API');
    } finally {
      setLoading(false);
      setPipelineLoading(false);
    }
  }, []);

  const fetchIncidents = useCallback(async () => {
    setIncidentsLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/incidents?limit=20`, { headers: AUTH });
      if (!res.ok) throw new Error();
      setIncidents((await res.json()).incidents || []);
      setIncidentsError(null);
    } catch {
      setIncidentsError('Não foi possível carregar incidentes');
    } finally {
      setIncidentsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
    const t = setInterval(fetchData, 30000);
    return () => clearInterval(t);
  }, [fetchData, selectedTenant]);

  useEffect(() => {
    if (currentView === 'incidents') fetchIncidents();
  }, [currentView, fetchIncidents]);

  const hasCritical = summary && summary.problems_critical > 0;

  return (
    <div className="min-h-screen bg-[var(--color-brand-base)] text-[var(--color-brand-text)] flex">

      {/* ══ Sidebar ══ */}
      <aside className="w-60 border-r border-white/[0.05] bg-[var(--color-brand-base)] flex flex-col py-5 px-3 gap-6 shrink-0 relative z-10">
        <div className="absolute top-0 left-0 right-0 h-40 bg-[var(--color-brand-primary)] opacity-[0.03] blur-3xl pointer-events-none" />

        <div className="px-2 py-1">
          <BrandLogo activeModule={activeModule} />
        </div>

        <div className="px-2">
          <TenantSelector selectedTenant={selectedTenant} onSelect={setSelectedTenant} />
        </div>

        <nav className="flex flex-col gap-1 flex-1" aria-label="Navegação principal">
          {/* Grupo principal */}
          <p className="px-3 mb-1 text-[9px] font-semibold uppercase tracking-[0.15em] text-white/20 select-none">
            Principal
          </p>
          <SidebarItem icon={Activity}    label="Dashboard"       active={currentView === 'dashboard'} onClick={() => setCurrentView('dashboard')} />
          <SidebarItem icon={Cloud}       label="Nuvem"          active={currentView === 'cloud'}     onClick={() => setCurrentView('cloud')} />
          <SidebarItem icon={Layers}      label="Infraestrutura"  disabled />
          <SidebarItem icon={ShieldAlert} label="Incidentes"      active={currentView === 'incidents'} onClick={() => setCurrentView('incidents')} />
          <SidebarItem icon={Users}       label="Clientes"        disabled />

          <div className="my-3 border-t border-white/[0.04]" />

          {/* Grupo sistema */}
          <p className="px-3 mb-1 text-[9px] font-semibold uppercase tracking-[0.15em] text-white/20 select-none">
            Sistema
          </p>
          <SidebarItem icon={Settings} label="Configurações" disabled />
        </nav>

        {/* ── User card + Logout ── */}
        <div className="px-2 space-y-2">
          {/* Status de conexão */}
          <div role="status" aria-live="polite">
            <div className={`flex items-center gap-2 px-3 py-2 rounded-lg text-xs
              ${error ? 'bg-red-500/10 text-red-400' : 'bg-white/[0.03] text-[var(--color-brand-muted)]'}`}
            >
              {error
                ? <><WifiOff size={11} /> Sem conexão</>
                : <><div className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                    {lastUpdate
                      ? `Sincronizado ${lastUpdate.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })}`
                      : 'Conectando à API...'}</>
              }
            </div>
          </div>

          {/* User info + logout */}
          {user && (
            <div className="flex items-center gap-2 px-2 py-2 rounded-xl bg-white/[0.04] border border-white/[0.06]">
              {/* Avatar */}
              <div className="w-7 h-7 rounded-full bg-[#00ADE8]/20 border border-[#00ADE8]/30 flex items-center justify-center shrink-0">
                <span className="text-[10px] font-bold text-[#00ADE8] uppercase">
                  {user.full_name?.charAt(0) ?? user.email.charAt(0)}
                </span>
              </div>
              {/* Info */}
              <div className="flex-1 min-w-0">
                <p className="text-[11px] font-medium text-white/80 truncate">
                  {user.full_name ?? user.email}
                </p>
                <span className={`text-[9px] font-semibold uppercase tracking-wide px-1.5 py-0.5 rounded-full ${
                  user.role === 'admin' ? 'bg-[#00ADE8]/15 text-[#00ADE8]'
                  : user.role === 'noc' ? 'bg-emerald-500/15 text-emerald-400'
                  : 'bg-white/10 text-white/40'
                }`}>{user.role}</span>
              </div>
              {/* Logout */}
              <button
                onClick={logout}
                title="Sair"
                aria-label="Sair da conta"
                className="p-1.5 rounded-lg text-white/30 hover:text-red-400 hover:bg-red-500/10 transition-all duration-200 shrink-0"
              >
                <LogOut size={13} />
              </button>
            </div>
          )}
        </div>
      </aside>

      {/* ══ Main ══ */}
      <main className="flex-1 flex flex-col h-screen overflow-hidden relative">
        {/* Background glow — muda por módulo */}
        <div className="absolute top-0 inset-x-0 h-64 pointer-events-none"
          style={{ background: `radial-gradient(ellipse at 50% -20%, ${
            activeModule === 'core'     ? 'rgba(99,102,241,0.07)' :
            activeModule === 'infraops' ? 'rgba(59,130,246,0.06)' :
                                          'rgba(239,68,68,0.06)'
          } 0%, transparent 70%)` }} />

        {/* ── Header ── */}
        <header className="h-14 border-b border-white/[0.05] flex items-center justify-between px-8 z-10 shrink-0"
          style={{ background: 'rgba(8,8,16,0.7)', backdropFilter: 'blur(12px)' }}>
          <div className="flex items-center gap-3">
            <ModuleSwitcher active={activeModule} onChange={setActiveModule} />
            {activeModule !== 'core' && hasCritical && activeModule === 'infraops' && (
              <span className="flex items-center gap-1 text-[10px] font-semibold px-2 py-0.5 rounded-full bg-red-500/15 border border-red-500/30 text-red-400">
                <AlertTriangle size={9} /> {summary!.problems_critical} {summary!.problems_critical === 1 ? 'alerta crítico' : 'alertas críticos'}
              </span>
            )}
          </div>

          <button
            onClick={fetchData}
            aria-label="Atualizar dados"
            className="p-1.5 rounded-lg hover:bg-white/[0.06] text-[var(--color-brand-muted)] hover:text-white transition-all duration-200"
            style={{ transitionProperty: 'color, background, transform', transitionDuration: '300ms' }}
          >
            <RefreshCw size={14} />
          </button>
        </header>

        {/* ── Content ── */}
        <div className="flex-1 overflow-auto z-10">

          {/* ── ness.OS Core ── */}
          {activeModule === 'core' && (
            <CoreDashboard
              authHeader={AUTH}
              onModuleSwitch={(mod) => setActiveModule(mod)}
            />
          )}

          {/* ── n.infraops ── */}
          {activeModule === 'infraops' && (
          <div className="p-8 max-w-6xl space-y-5 animate-fade-in">

            {currentView === 'dashboard' && (
              <>
                {/* Alertas de Segurança e Desatualização do Ambiente */}
                <SecurityAlerts />

                {/* Pipeline Strip */}
                <PipelineStrip data={pipeline} loading={pipelineLoading} />

                {/* Metric Cards */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <MetricCard
                    icon={Monitor}
                    title="Hosts Ativos"
                    value={summary ? formatNumber(summary.hosts_active) : '—'}
                    loading={loading}
                  />
                  <MetricCard
                    icon={Cpu}
                    title="Itens Monitorados"
                    value={summary ? formatNumber(summary.items_total) : '—'}
                    loading={loading}
                  />
                  <MetricCard
                    icon={AlertTriangle}
                    title="Críticos"
                    value={summary ? summary.problems_critical : '—'}
                    status={summary && summary.problems_critical > 0 ? 'danger' : 'success'}
                    loading={loading}
                  />
                  <MetricCard
                    icon={BarChart3}
                    title="Alertas Totais"
                    value={summary ? summary.problems_total : '—'}
                    status={summary && summary.problems_total > 5 ? 'warning' : 'neutral'}
                    loading={loading}
                  />
                </div>

                {/* Alertas */}
                <SectionCard
                  title="Alertas Ativos"
                  count={summary?.problems_total}
                  loading={loading && !error}
                >
                  {error && (
                    <div className="flex items-center gap-2 text-red-400 text-sm p-3 m-1 rounded-lg bg-red-500/10 border border-red-500/20">
                      <WifiOff size={14} /> {error}
                    </div>
                  )}
                  {!loading && !error && problems.length === 0 && (
                    <div className="flex flex-col items-center justify-center py-10 gap-2">
                      <CheckCircle size={28} className="text-emerald-400 opacity-60" />
                      <p className="text-sm text-[var(--color-brand-muted)]">Nenhum problema ativo</p>
                    </div>
                  )}
                  {problems.map(p => <ProblemRow key={p.id} p={p} />)}
                </SectionCard>
              </>
            )}

            {currentView === 'incidents' && (
              <IncidentsPage
                incidents={incidents}
                loading={incidentsLoading}
                error={incidentsError}
              />
            )}

            {currentView === 'cloud' && <CloudManagement selectedTenant={selectedTenant} />}

          </div>
          )} {/* /infraops */}

          {/* ── n.secops ── */}
          {activeModule === 'secops' && (
            <div className="p-8 flex items-center justify-center h-full">
              <div className="text-center space-y-3">
                <div className="w-16 h-16 rounded-2xl mx-auto flex items-center justify-center"
                  style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.2)' }}>
                  <Shield size={28} style={{ color: '#EF4444' }} />
                </div>
                <p className="text-white font-semibold text-lg">n.secops</p>
                <p className="text-white/40 text-sm max-w-xs">
                  Integração Wazuh + RocketCyber em desenvolvimento.
                  <br />Disponível na Fase 3 do ness.OS.
                </p>
              </div>
            </div>
          )}

        </div>
      </main>
    </div>
  );
}

export default function App() {
  const { isAuthenticated, loading: authLoading, authHeader, logout, user } = useAuth();

  // Enquanto valida token salvo, mostrar loading minimal
  if (authLoading) {
    return (
      <div className="min-h-screen bg-[#08111f] flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 border-2 border-[#00ADE8]/30 border-t-[#00ADE8] rounded-full animate-spin" />
          <span className="text-white/30 text-sm">ness.OS</span>
        </div>
      </div>
    );
  }

  // Não autenticado → tela de login
  if (!isAuthenticated) return <LoginPage />;

  // Autenticado → app completo
  return <AppShell authHeader={authHeader} logout={logout} user={user} />;
}

function AppShell({
  authHeader,
  logout,
  user,
}: {
  authHeader: () => Record<string, string>;
  logout: () => void;
  user: import('./hooks/useAuth').User | null;
}) {
  const AUTH = authHeader();
  return <AppShellBody AUTH={AUTH} logout={logout} user={user} />;
}
