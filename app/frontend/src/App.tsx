import { Activity, ShieldAlert, Cloud, RefreshCw, LayoutDashboard, Shield,
         WifiOff, AlertTriangle, LogOut, FileText, Users, Menu } from 'lucide-react';
import React, { useState, useEffect, useCallback, useRef } from 'react';
import CloudManagement from './components/CloudManagement';
import PipelineStrip from './components/PipelineStrip';
import IncidentsPage, { incidentQuery, readIncidentFilter, writeIncidentFilter } from './components/IncidentsPage';
import TenantSelector from './components/TenantSelector';
import SecurityAlerts from './components/SecurityAlerts';
import ProblemsView, { type Problem } from './components/ProblemsView';
import LoginPage from './components/LoginPage';
import SecopsModule from './components/SecopsModule';
import CoreDashboard from './components/CoreDashboard';
import { debounce } from './debounce';
import { useAuth } from './hooks/useAuth';
import PushNotificationToggle from './components/PushNotificationToggle';
import NotificationInbox from './components/NotificationInbox';
import * as access from './access';
import BrandMark from './components/BrandMark';
import ContractsScreen from './components/ContractsScreen';
import CustomersScreen from './components/CustomersScreen';


const API_BASE = import.meta.env.VITE_API_URL ?? '';

type View = 'overview' | 'monitoring' | 'cloud' | 'incidents' | 'secops' | 'contracts' | 'customers';

const TITLES: Record<View, string> = {
  overview: 'Visão geral', monitoring: 'Monitoramento', cloud: 'Nuvem', incidents: 'Incidentes',
  secops: 'Segurança', contracts: 'Contratos', customers: 'Clientes',
};

// A tela vive na URL (?view=) para recarregar, voltar e compartilhar link; papel decide o que pode abrir.
export function allowedView(v: string | null, isOperator: boolean, canCadastros: boolean): View {
  if (v === 'incidents') return v;
  if ((v === 'contracts' || v === 'customers') && canCadastros) return v;
  if (isOperator && (v === 'overview' || v === 'monitoring' || v === 'cloud' || v === 'secops')) return v;
  return isOperator ? 'overview' : 'incidents';
}

interface Summary {
  hosts_active: number;
  items_total: number;
  problems_critical: number;
  problems_warning: number;
  problems_total: number;
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
      className={`
        w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-left
        transition-all duration-200 relative group select-none
        ${active
          ? 'text-white'
          : disabled || !onClick
            ? 'text-brand-muted cursor-not-allowed'
            : 'text-[var(--color-brand-muted)] hover:text-white/90 hover:bg-white/[0.04]'
        }
      `}
      style={active ? {
        background: 'rgba(0,173,232,0.12)',
      } : {}}
    >
      {active && (
        <span
          className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-6 rounded-r-full"
          style={{ background: '#00ADE8' }}
        />
      )}
      <Icon size={18} className={active ? 'text-[#00ADE8]' : ''} />
      <span className={`font-medium text-sm ${active ? 'text-white' : 'text-slate-400'}`}>{label}</span>
    </button>
  );
}

// ─── App Shell Body ──────────────────────────────────────────────────────────
function AppShellBody({ AUTH, logout, user }: {
  AUTH: Record<string, string>;
  logout: () => Promise<void>;
  user: import('./hooks/useAuth').User | null;
}) {
  const isOperator = access.isOperator(user?.role);
  const canActOnIncidents = access.canActOnIncidents(user?.role);
  // Link da notificação push: /?view=incidents&id=N abre o caso (o backend revalida o acesso).
  const linkParams = new URLSearchParams(window.location.search);
  const linkedIncident = linkParams.get('view') === 'incidents' ? linkParams.get('id') : null;
  const canReadCadastros = access.canReadCadastros(user?.role);
  const [currentView, setView] = useState<View>(() => allowedView(linkParams.get('view'), isOperator, canReadCadastros));
  const setCurrentView = useCallback((v: View) => {
    setView(v);
    const url = new URL(window.location.href);
    if (url.searchParams.get('view') === v) return;
    url.search = `?view=${v}`;
    window.history.pushState(null, '', url);
  }, []);
  useEffect(() => {
    const onPop = () => setView(allowedView(new URLSearchParams(window.location.search).get('view'), isOperator, canReadCadastros));
    window.addEventListener('popstate', onPop);
    return () => window.removeEventListener('popstate', onPop);
  }, [isOperator, canReadCadastros]);
  useEffect(() => { document.title = `${TITLES[currentView]} · ness.OS`; }, [currentView]);
  const [selectedTenant, setSelectedTenant] = useState<string | null>(null);
  const [incidentFilter, setIncidentFilter] = useState(() => readIncidentFilter(window.location.search));
  const [navOpen, setNavOpen] = useState(false);
  // Recarrega a caixa de avisos: evento SSE de incidente ou ação no caso.
  const [inboxVersion, setInboxVersion] = useState(0);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [problems, setProblems] = useState<Problem[]>([]);
  const [pipeline, setPipeline] = useState<any>(null);
  const [pipelineLoading, setPipelineLoading] = useState(true);
  const [incidents, setIncidents] = useState<any[]>([]);
  const [incidentsTotal, setIncidentsTotal] = useState(0);
  const [incidentsLoading, setIncidentsLoading] = useState(false);
  const [incidentsMoreLoading, setIncidentsMoreLoading] = useState(false);
  const [incidentsError, setIncidentsError] = useState<string | null>(null);
  const incidentsRequest = useRef(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [cadastrosTick, setCadastrosTick] = useState(0);
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);

  const fetchData = useCallback(async () => {
    if (!isOperator) {
      setLoading(false);
      setPipelineLoading(false);
      return;
    }
    try {
      const [summaryRes, problemsRes, pipelineRes] = await Promise.all([
        fetch(`${API_BASE}/api/dashboard/summary`, { credentials: 'include', headers: AUTH }),
        fetch(`${API_BASE}/api/dashboard/problems?limit=2000`, { credentials: 'include', headers: AUTH }),
        fetch(`${API_BASE}/api/dashboard/pipeline-status`, { credentials: 'include', headers: AUTH }),
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
  }, [AUTH, isOperator]);

  const fetchIncidents = useCallback(async (offset = 0) => {
    const requestId = ++incidentsRequest.current;
    if (offset === 0) setIncidentsLoading(true);
    else setIncidentsMoreLoading(true);
    try {
      const tenant = access.tenantScope(user?.role, selectedTenant);
      const scope = tenant ? `&tenant_id=${encodeURIComponent(tenant)}` : '';
      const res = await fetch(`${API_BASE}/api/incidents?limit=20&offset=${offset}${scope}${incidentQuery(incidentFilter)}`, { credentials: 'include', headers: AUTH });
      if (!res.ok) throw new Error();
      const data = await res.json();
      if (requestId !== incidentsRequest.current) return;
      setIncidents(previous => offset === 0 ? data.incidents || [] : [...previous, ...(data.incidents || [])]);
      setIncidentsTotal(data.total || 0);
      setIncidentsError(null);
      if (!isOperator) setLastUpdate(new Date());
    } catch {
      if (requestId === incidentsRequest.current) setIncidentsError('Não foi possível carregar incidentes');
    } finally {
      if (requestId === incidentsRequest.current) {
        setIncidentsLoading(false);
        setIncidentsMoreLoading(false);
      }
    }
  }, [AUTH, selectedTenant, isOperator, incidentFilter]);

  useEffect(() => {
    fetchData();
    const t = setInterval(fetchData, 30000);
    return () => clearInterval(t);
  }, [fetchData]);

  useEffect(() => {
    if (currentView === 'incidents') fetchIncidents();
  }, [currentView, fetchIncidents]);

  // Rajada de alertas (dezenas de eventos SSE) vira uma recarga só: sem isso cada evento
  // refazia 3 chamadas do dashboard e a API esgotou o Postgres em 10/11 (#231).
  // Escuta SSE para incidentes em tempo real
  useEffect(() => {
    if (!user) return;

    const sseUrl = `${API_BASE}/api/incidents/stream`;
    const eventSource = new EventSource(sseUrl, { withCredentials: true });
    const scheduleReload = debounce(() => {
      if (currentView === 'incidents') void fetchIncidents();
      if (isOperator) void fetchData();
      setInboxVersion(v => v + 1);
    }, 2000);

    eventSource.addEventListener('incident', (event) => {
      try {
        const eventData = JSON.parse(event.data);
        if (!access.matchesTenant(selectedTenant, eventData.tenant_id)) return;
        scheduleReload();
      } catch (err) {
        console.error('Erro ao analisar dados do SSE:', err);
      }
    });

    eventSource.addEventListener('ping', () => {
      // Keep alive
    });

    eventSource.addEventListener('auth', () => {
      eventSource.close();
      void logout();
    });

    eventSource.onerror = (err) => {
      console.warn('Conexão SSE com aviso ou reconectando:', err);
    };

    return () => {
      scheduleReload.cancel();
      eventSource.close();
    };
  }, [user, fetchData, fetchIncidents, selectedTenant, currentView, isOperator, logout]);

  // Gaveta mobile: fecha ao trocar de tela e com Esc.
  useEffect(() => { setNavOpen(false); }, [currentView]);
  useEffect(() => {
    if (!navOpen) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setNavOpen(false); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [navOpen]);

  const hasCritical = summary && summary.problems_critical > 0;
  const connectionError = isOperator ? error : incidentsError;

  return (
    <div className="min-h-screen bg-[var(--color-brand-base)] text-[var(--color-brand-text)] flex">

      {navOpen && <div className="fixed inset-0 z-30 bg-black/60 md:hidden" onClick={() => setNavOpen(false)} aria-hidden="true" />}

      {/* ══ Sidebar (gaveta no mobile) ══ */}
      <aside id="main-nav" className={`w-60 border-r border-white/[0.05] bg-[var(--color-brand-base)] flex flex-col py-5 px-3 gap-6 shrink-0 overflow-y-auto
        fixed inset-y-0 left-0 z-40 transition-[transform,visibility] duration-200 pt-[max(1.25rem,env(safe-area-inset-top))]
        md:static md:z-10 md:translate-x-0 ${navOpen ? 'translate-x-0' : '-translate-x-full max-md:invisible'}`}>

        <div className="px-2 py-1">
          <BrandMark size="md" />
          <p className="mt-1 text-xs font-medium tracking-wide text-brand-muted">operações de tecnologia</p>
        </div>

        <div className="px-2">
          {isOperator && currentView === 'incidents' ? (
            <TenantSelector selectedTenant={selectedTenant} onSelect={setSelectedTenant} />
          ) : (
            <p className="text-xs text-white/60">{isOperator ? 'Operação global' : 'Minha empresa'}</p>
          )}
        </div>

        <nav className="flex flex-col gap-1 flex-1" aria-label="Navegação principal">
          {isOperator && <SidebarItem icon={LayoutDashboard} label="Visão geral" active={currentView === 'overview'} onClick={() => setCurrentView('overview')} />}
          <p className="px-3 mt-3 mb-1 text-[10px] font-semibold uppercase tracking-[0.15em] text-brand-muted select-none">Operação</p>
          {isOperator && <SidebarItem icon={Activity} label="Monitoramento" active={currentView === 'monitoring'} onClick={() => setCurrentView('monitoring')} />}
          <SidebarItem icon={ShieldAlert} label="Incidentes" active={currentView === 'incidents'} onClick={() => setCurrentView('incidents')} />
          {isOperator && <SidebarItem icon={Cloud} label="Nuvem" active={currentView === 'cloud'} onClick={() => setCurrentView('cloud')} />}
          {isOperator && <SidebarItem icon={Shield} label="Segurança" active={currentView === 'secops'} onClick={() => setCurrentView('secops')} />}
          {canReadCadastros && <>
          <p className="px-3 mt-3 mb-1 text-[10px] font-semibold uppercase tracking-[0.15em] text-brand-muted select-none">Cadastros</p>
          <SidebarItem icon={FileText} label="Contratos" active={currentView === 'contracts'} onClick={() => setCurrentView('contracts')} />
          <SidebarItem icon={Users} label="Clientes" active={currentView === 'customers'} onClick={() => setCurrentView('customers')} />
          </>}
        </nav>

        {/* ── User card + Logout ── */}
        <div className="px-2 space-y-2">
          {/* Ativação do Web Push */}
          {user && <PushNotificationToggle />}
          {user && canActOnIncidents && <NotificationInbox version={inboxVersion} />}

          {/* Status de conexão */}
          <div role="status" aria-live="polite">
            <div className={`flex items-center gap-2 px-3 py-2 rounded-lg text-xs
              ${connectionError ? 'bg-red-500/10 text-red-400' : 'bg-white/[0.03] text-[var(--color-brand-muted)]'}`}
            >
              {connectionError
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
                <p className="text-xs font-medium text-white/80 truncate">
                  {user.full_name ?? user.email}
                </p>
                <span className={`text-[10px] font-semibold uppercase tracking-wide px-1.5 py-0.5 ${
                  user.role === 'admin' ? 'bg-[#00ADE8]/15 text-[#00ADE8]'
                  : user.role === 'noc' ? 'bg-emerald-500/15 text-emerald-400'
                  : user.role === 'soc' ? 'bg-amber-500/15 text-amber-400'
                  : 'bg-white/10 text-brand-muted'
                }`}>{user.role}</span>
              </div>
              {/* Logout */}
              <button
                onClick={logout}
                title="Sair"
                aria-label="Sair da conta"
                className="p-1.5 rounded-lg text-brand-muted hover:text-red-400 hover:bg-red-500/10 transition-all duration-200 shrink-0"
              >
                <LogOut size={13} />
              </button>
            </div>
          )}
        </div>
      </aside>

      {/* ══ Main ══ */}
      <main className="flex-1 min-w-0 flex flex-col h-dvh overflow-hidden relative">

        {/* ── Header ── */}
        <header className="h-16 box-content pt-[env(safe-area-inset-top)] border-b border-white/[0.05] flex items-center justify-between gap-2 px-3 md:px-8 z-10 shrink-0"
          style={{ background: 'var(--color-brand-base)' }}>
          <div className="flex items-center gap-2 md:gap-3 min-w-0">
            <button
              onClick={() => setNavOpen(true)}
              aria-label="Abrir menu"
              aria-controls="main-nav"
              aria-expanded={navOpen}
              className="md:hidden p-2.5 -ml-1 rounded-lg text-white/70 hover:bg-white/[0.06]"
            >
              <Menu size={18} />
            </button>
            <h1 className="text-xl font-semibold tracking-[-0.02em] truncate">{TITLES[currentView]}</h1>
            {hasCritical && (currentView === 'overview' || currentView === 'monitoring') && (
              <span role="status" aria-label={`${summary!.problems_critical} alertas críticos`} className="flex shrink-0 items-center gap-1 text-xs font-semibold px-2 py-0.5 bg-red-500/15 border border-red-500/30 text-red-400">
                <AlertTriangle size={9} /> {summary!.problems_critical}<span className="hidden sm:inline">{summary!.problems_critical === 1 ? ' alerta crítico' : ' alertas críticos'}</span>
              </span>
            )}
          </div>

          <button
            onClick={() => {
              if (currentView === 'contracts' || currentView === 'customers') setCadastrosTick(t => t + 1);
              else if (currentView === 'incidents') void fetchIncidents();
              else void fetchData();
            }}
            aria-label="Atualizar dados"
            className="p-2.5 md:p-1.5 shrink-0 rounded-lg hover:bg-white/[0.06] text-[var(--color-brand-muted)] hover:text-white transition-all duration-200"
            style={{ transitionProperty: 'color, background, transform', transitionDuration: '300ms' }}
          >
            <RefreshCw size={14} />
          </button>
        </header>

        {/* ── Content ── */}
        <div className="flex-1 overflow-auto z-10">

          {/* ── ness.OS Core ── */}
          {currentView === 'overview' && (
            <CoreDashboard
              authHeader={AUTH}
              onModuleSwitch={(mod) => setCurrentView(mod === 'secops' ? 'secops' : 'monitoring')}
            />
          )}

          {/* ── n.infraops ── */}
          {currentView === 'monitoring' && <ProblemsView problems={problems} loading={loading} error={error} observedAt={lastUpdate}
            hosts={summary?.hosts_active} items={summary?.items_total} pipeline={<PipelineStrip data={pipeline} loading={pipelineLoading} />} />}
          {(currentView === 'incidents' || currentView === 'cloud') && (
          <div className="p-4 md:p-8 max-w-6xl space-y-5 animate-fade-in">

            {currentView === 'incidents' && (
              <IncidentsPage
                incidents={incidents}
                total={incidentsTotal}
                loading={incidentsLoading}
                loadingMore={incidentsMoreLoading}
                error={incidentsError}
                canAct={canActOnIncidents}
                initialActiveId={linkedIncident}
                onChanged={() => { setInboxVersion(v => v + 1); return fetchIncidents(); }}
                onLoadMore={() => fetchIncidents(incidents.length)}
                filter={incidentFilter}
                onFilter={f => { setIncidentFilter(f); writeIncidentFilter(f); }}
              />
            )}

            {currentView === 'cloud' && <CloudManagement />}

          </div>
          )} {/* /infraops */}
          {currentView === 'contracts' && <ContractsScreen role={user?.role} refreshKey={cadastrosTick} />}
          {currentView === 'customers' && <CustomersScreen role={user?.role} refreshKey={cadastrosTick} />}

          {/* ── n.secops ── */}
          {currentView === 'secops' && (
            <><div className="px-4 pt-4 md:px-8"><SecurityAlerts /></div><SecopsModule /></>
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
      <div className="min-h-screen bg-[var(--color-brand-base)] flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 border-2 border-[#00ADE8]/30 border-t-[#00ADE8] rounded-full animate-spin" />
          <BrandMark size="sm" className="opacity-60" />
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
  logout: () => Promise<void>;
  user: import('./hooks/useAuth').User | null;
}) {
  const AUTH = React.useMemo(() => authHeader(), [authHeader]);
  return <AppShellBody AUTH={AUTH} logout={logout} user={user} />;
}
