/**
 * ness.OS — Core Dashboard
 * Visão global executiva: todos os módulos consolidados em uma tela.
 * Módulo: core — cor índigo #6366F1
 */
import React, { useState, useEffect, useCallback } from 'react';
import {
  Globe, Server, Shield, Activity, AlertTriangle,
  CheckCircle, RefreshCw, TrendingUp, Cpu, Users,
} from 'lucide-react';

const API_BASE = import.meta.env.VITE_API_URL ?? '';

interface ModuleStatus {
  id: string; label: string; description: string;
  color: string; configured: boolean; route: string;
}

interface KPI {
  id: string; label: string; value: number; unit: string;
  module: string; color: string; alert?: boolean;
}

interface Overview {
  health_score: number;
  modules: {
    infraops: { status: string; metrics: Record<string, number> };
    secops:   { status: string; metrics: Record<string, number> };
  };
}

// ── Score Ring ──────────────────────────────────────────────────────────────
function HealthRing({ score }: { score: number }) {
  const r = 52;
  const circ = 2 * Math.PI * r;
  const filled = (score / 100) * circ;
  const color = score >= 80 ? '#10B981' : score >= 60 ? '#F59E0B' : '#EF4444';

  return (
    <div className="relative flex items-center justify-center" style={{ width: 140, height: 140 }}>
      <svg width={140} height={140} style={{ transform: 'rotate(-90deg)' }}>
        <circle cx={70} cy={70} r={r} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth={10} />
        <circle
          cx={70} cy={70} r={r} fill="none"
          stroke={color} strokeWidth={10}
          strokeDasharray={`${filled} ${circ}`}
          strokeLinecap="round"
          style={{ filter: `drop-shadow(0 0 8px ${color}99)`, transition: 'stroke-dasharray 1s ease' }}
        />
      </svg>
      <div className="absolute flex flex-col items-center">
        <span className="text-3xl font-bold text-white tabular-nums" style={{ color }}>{score}</span>
        <span className="text-[10px] text-white/40 uppercase tracking-widest mt-0.5">health</span>
      </div>
    </div>
  );
}

// ── Module Status Card ───────────────────────────────────────────────────────
function ModuleCard({
  mod, metrics, status, onClick,
}: {
  mod: { id: string; label: string; color: string; description: string };
  metrics: Record<string, number>;
  status: string;
  onClick: () => void;
}) {
  const isOk = status === 'ok';
  const metricEntries = Object.entries(metrics).slice(0, 3);

  return (
    <button
      onClick={onClick}
      className="text-left w-full rounded-2xl p-5 border transition-all duration-300 group"
      style={{
        background: `linear-gradient(135deg, ${mod.color}12 0%, ${mod.color}06 100%)`,
        borderColor: `${mod.color}30`,
      }}
    >
      <div className="flex items-start justify-between mb-4">
        <div>
          <div className="text-xs font-mono uppercase tracking-widest mb-1" style={{ color: mod.color }}>
            {mod.id === 'infraops' ? 'n.infraops' : mod.id === 'secops' ? 'n.secops' : 'core'}
          </div>
          <div className="text-white font-semibold text-base">{mod.description}</div>
        </div>
        <div
          className="w-2.5 h-2.5 rounded-full mt-1"
          style={{
            background: isOk ? '#10B981' : '#EF4444',
            boxShadow: `0 0 8px ${isOk ? '#10B98180' : '#EF444480'}`,
          }}
        />
      </div>
      <div className="grid grid-cols-3 gap-2">
        {metricEntries.map(([key, val]) => (
          <div key={key} className="rounded-lg p-2.5" style={{ background: 'rgba(255,255,255,0.04)' }}>
            <div className="text-lg font-bold text-white tabular-nums">{val}</div>
            <div className="text-[10px] text-white/40 capitalize mt-0.5 leading-tight">
              {key.replace(/_/g, ' ')}
            </div>
          </div>
        ))}
      </div>
      <div
        className="mt-4 text-xs font-medium flex items-center gap-1.5 opacity-0 group-hover:opacity-100 transition-opacity"
        style={{ color: mod.color }}
      >
        Abrir módulo →
      </div>
    </button>
  );
}

// ── KPI Bar ─────────────────────────────────────────────────────────────────
function KpiCard({ kpi }: { kpi: KPI }) {
  return (
    <div
      className="rounded-xl p-4 border flex items-center gap-4 transition-all duration-200"
      style={{
        background: kpi.alert ? 'rgba(239,68,68,0.08)' : 'rgba(255,255,255,0.03)',
        borderColor: kpi.alert ? 'rgba(239,68,68,0.3)' : 'rgba(255,255,255,0.07)',
      }}
    >
      <div
        className="w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0"
        style={{ background: `${kpi.color}20` }}
      >
        <Activity size={18} style={{ color: kpi.color }} />
      </div>
      <div className="flex-1 min-w-0">
        <div className="text-xs text-white/40 truncate">{kpi.label}</div>
        <div className="flex items-baseline gap-1.5">
          <span className="text-2xl font-bold text-white tabular-nums">{kpi.value}</span>
          <span className="text-xs text-white/30">{kpi.unit}</span>
        </div>
      </div>
      {kpi.alert && (
        <AlertTriangle size={16} className="text-red-400 flex-shrink-0 animate-pulse" />
      )}
    </div>
  );
}

// ── Core Dashboard ───────────────────────────────────────────────────────────
export default function CoreDashboard({
  authHeader,
  onModuleSwitch,
}: {
  authHeader: Record<string, string>;
  onModuleSwitch: (module: 'infraops' | 'secops') => void;
}) {
  const [overview, setOverview] = useState<Overview | null>(null);
  const [kpis, setKpis] = useState<KPI[]>([]);
  const [loading, setLoading] = useState(true);
  const [lastRefresh, setLastRefresh] = useState<Date>(new Date());

  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      const [ovRes, kpiRes] = await Promise.all([
        fetch(`${API_BASE}/api/core/overview`, { headers: authHeader }),
        fetch(`${API_BASE}/api/core/kpis`, { headers: authHeader }),
      ]);
      if (ovRes.ok) setOverview(await ovRes.json());
      if (kpiRes.ok) {
        const data = await kpiRes.json();
        setKpis(data.kpis ?? []);
      }
      setLastRefresh(new Date());
    } finally {
      setLoading(false);
    }
  }, [authHeader]);

  useEffect(() => { fetchAll(); }, [fetchAll]);
  useEffect(() => {
    const t = setInterval(fetchAll, 60_000);
    return () => clearInterval(t);
  }, [fetchAll]);

  const MODULES = [
    {
      id: 'infraops', label: 'n.infraops', color: '#3B82F6',
      description: 'Operação de Infraestrutura e NOC',
    },
    {
      id: 'secops', label: 'n.secops', color: '#EF4444',
      description: 'Operação de Segurança e SOC',
    },
  ];

  return (
    <div className="flex-1 overflow-y-auto p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-tight">
            ness<span style={{ color: '#6366F1' }}>.</span>OS
          </h1>
          <p className="text-sm text-white/40 mt-0.5">
            Visão global consolidada · {lastRefresh.toLocaleTimeString('pt-BR')}
          </p>
        </div>
        <button
          onClick={fetchAll}
          disabled={loading}
          className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium text-white/60 hover:text-white border border-white/10 hover:border-white/20 transition-all"
        >
          <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
          Atualizar
        </button>
      </div>

      {/* Health Score + KPIs */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Score */}
        <div
          className="rounded-2xl p-6 border flex flex-col items-center justify-center gap-3"
          style={{
            background: 'linear-gradient(135deg, rgba(99,102,241,0.12) 0%, rgba(99,102,241,0.04) 100%)',
            borderColor: 'rgba(99,102,241,0.25)',
          }}
        >
          <HealthRing score={overview?.health_score ?? 0} />
          <div className="text-center">
            <div className="text-sm font-medium text-white/70">Score Global</div>
            <div className="text-xs text-white/30 mt-0.5">Infraestrutura + Segurança</div>
          </div>
        </div>

        {/* KPIs */}
        <div className="lg:col-span-2 grid grid-cols-2 gap-3">
          {loading
            ? Array.from({ length: 4 }).map((_, i) => (
                <div key={i} className="rounded-xl p-4 border border-white/5 bg-white/[0.02] animate-pulse h-20" />
              ))
            : kpis.map(kpi => <KpiCard key={kpi.id} kpi={kpi} />)
          }
        </div>
      </div>

      {/* Module Cards */}
      <div>
        <h2 className="text-xs font-semibold uppercase tracking-widest text-white/30 mb-3">
          Módulos Operacionais
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {MODULES.map(mod => {
            const modData = overview?.modules?.[mod.id as keyof typeof overview.modules];
            return (
              <ModuleCard
                key={mod.id}
                mod={mod}
                metrics={modData?.metrics ?? {}}
                status={modData?.status ?? 'unknown'}
                onClick={() => onModuleSwitch(mod.id as 'infraops' | 'secops')}
              />
            );
          })}
        </div>
      </div>
    </div>
  );
}
