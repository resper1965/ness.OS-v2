import React, { useState, useEffect, useCallback } from 'react';
import {
  Shield, ShieldAlert, ShieldCheck, ShieldX,
  AlertTriangle, CheckCircle2, XCircle, Clock,
  Zap, Activity, ChevronDown, ChevronUp,
  ExternalLink, RefreshCw, Bug, Eye, Globe,
} from 'lucide-react';

const API_BASE = import.meta.env.VITE_API_URL ?? '';

// ── Types ────────────────────────────────────────────────────────────────────

interface CveItem {
  id: string;
  title: string;
  severity: 'critical' | 'high' | 'medium';
  cvss: number;
  affected_tech: string;
  affected_clients: string[];
  exploited_wild: boolean;
  patch_available: boolean;
  patch_version: string;
  description: string;
  action: string;
  published: string;
  references: string[];
}

interface CveIntel {
  updated_at: string;
  source: string;
  summary: { total: number; critical: number; high: number; exploited_in_wild: number };
  items: CveItem[];
}

interface ZabbixCheck {
  check: string;
  status: 'secure' | 'warning' | 'danger' | 'unknown';
  value: string;
  message: string;
  details: string[];
}

interface ZabbixHealth {
  timestamp: string;
  score: number;
  overall: 'secure' | 'warning' | 'danger' | 'unknown';
  checks: ZabbixCheck[];
  zabbix_url: string;
  error?: string;
}

// ── Helpers ──────────────────────────────────────────────────────────────────

const SEV_CONFIG = {
  critical: { label: 'Crítico', color: 'text-red-400', bg: 'bg-red-500/10', border: 'border-red-500/25', dot: 'bg-red-500' },
  high:     { label: 'Alto',    color: 'text-orange-400', bg: 'bg-orange-500/10', border: 'border-orange-500/25', dot: 'bg-orange-400' },
  medium:   { label: 'Médio',   color: 'text-yellow-400', bg: 'bg-yellow-500/10', border: 'border-yellow-500/25', dot: 'bg-yellow-400' },
};

const STATUS_CONFIG = {
  secure:  { icon: CheckCircle2, color: 'text-emerald-400', bg: 'bg-emerald-500/10', border: 'border-emerald-500/20', label: 'OK' },
  warning: { icon: AlertTriangle, color: 'text-orange-400', bg: 'bg-orange-500/10', border: 'border-orange-500/20', label: 'Atenção' },
  danger:  { icon: XCircle,      color: 'text-red-400',    bg: 'bg-red-500/10',    border: 'border-red-500/20',    label: 'Crítico' },
  unknown: { icon: Clock,        color: 'text-white/30',   bg: 'bg-white/5',       border: 'border-white/10',      label: '?' },
};

const CLIENT_COLORS: Record<string, string> = {
  Alupar:       '#3B82F6', TBE: '#8B5CF6', TNE: '#10B981',
  Target:       '#F59E0B', Cavan: '#EC4899', LTB: '#06B6D4',
  NumenIT:      '#F97316', 'Nova Energia': '#84CC16', Bichara: '#A78BFA',
  'ness. (infraestrutura própria)': '#00ADE8',
};

function ScoreRing({ score }: { score: number }) {
  const r = 28;
  const circ = 2 * Math.PI * r;
  const fill = circ * (score / 100);
  const color = score >= 80 ? '#10B981' : score >= 50 ? '#F59E0B' : '#EF4444';

  return (
    <div className="relative w-20 h-20 flex items-center justify-center">
      <svg className="absolute inset-0 w-full h-full -rotate-90">
        <circle cx="40" cy="40" r={r} fill="none" stroke="rgba(255,255,255,0.05)" strokeWidth="5" />
        <circle
          cx="40" cy="40" r={r} fill="none"
          stroke={color} strokeWidth="5"
          strokeDasharray={`${fill} ${circ}`}
          strokeLinecap="round"
          style={{ transition: 'stroke-dasharray 1s ease' }}
        />
      </svg>
      <div className="text-center">
        <p className="text-lg font-black" style={{ color }}>{score}</p>
        <p className="text-[9px] text-white/30 uppercase tracking-wider">score</p>
      </div>
    </div>
  );
}

// ── CVE Card ─────────────────────────────────────────────────────────────────

function CveCard({ cve }: { cve: CveItem }) {
  const [expanded, setExpanded] = useState(false);
  const sev = SEV_CONFIG[cve.severity] ?? SEV_CONFIG.medium;

  return (
    <div className={`rounded-xl border ${sev.border} ${sev.bg} overflow-hidden transition-all duration-200`}>
      {/* Header */}
      <button
        onClick={() => setExpanded(e => !e)}
        className="w-full flex items-start gap-3 p-4 text-left hover:bg-white/[0.02] transition-colors"
      >
        {/* CVSS badge */}
        <div className={`shrink-0 mt-0.5 px-2 py-1 rounded-lg text-[11px] font-black ${sev.color} bg-black/20 min-w-[42px] text-center`}>
          {cve.cvss > 0 ? cve.cvss.toFixed(1) : 'N/A'}
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap mb-1">
            <span className={`text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full ${sev.bg} ${sev.color} border ${sev.border}`}>
              {sev.label}
            </span>
            <span className="text-[10px] font-mono text-white/40">{cve.id}</span>
            {cve.exploited_wild && (
              <span className="flex items-center gap-1 text-[10px] font-bold px-2 py-0.5 rounded-full bg-red-500 text-white uppercase tracking-wider animate-pulse">
                <Zap size={8} /> Exploração ativa
              </span>
            )}
          </div>
          <p className="text-sm font-semibold text-white/90 leading-snug">{cve.title}</p>
          <p className="text-[11px] text-white/40 mt-1">{cve.affected_tech}</p>
        </div>

        <div className="shrink-0 text-white/20">
          {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
        </div>
      </button>

      {/* Expanded */}
      {expanded && (
        <div className="px-4 pb-4 space-y-3 border-t border-white/[0.05] pt-3">
          {/* Clientes afetados */}
          <div>
            <p className="text-[10px] text-white/30 uppercase tracking-wider mb-1.5">Clientes afetados</p>
            <div className="flex flex-wrap gap-1.5">
              {cve.affected_clients.map(c => (
                <span key={c} className="text-[10px] font-semibold px-2 py-0.5 rounded-full text-white/80"
                  style={{ background: (CLIENT_COLORS[c] ?? '#6B7280') + '25', border: `1px solid ${(CLIENT_COLORS[c] ?? '#6B7280')}40` }}>
                  {c}
                </span>
              ))}
            </div>
          </div>

          {/* Descrição */}
          <div>
            <p className="text-[10px] text-white/30 uppercase tracking-wider mb-1">Descrição</p>
            <p className="text-xs text-white/60 leading-relaxed">{cve.description}</p>
          </div>

          {/* Ação */}
          <div className="flex items-start gap-2 p-3 rounded-lg bg-black/20 border border-white/[0.06]">
            <AlertTriangle size={13} className="text-orange-400 shrink-0 mt-0.5" />
            <div>
              <p className="text-[10px] font-bold text-orange-400 uppercase tracking-wider mb-0.5">Ação Recomendada</p>
              <p className="text-xs text-white/70">{cve.action}</p>
            </div>
          </div>

          {/* Patch */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              {cve.patch_available
                ? <><CheckCircle2 size={12} className="text-emerald-400" /><span className="text-[11px] text-emerald-400 font-medium">Patch disponível</span></>
                : <><XCircle size={12} className="text-red-400" /><span className="text-[11px] text-red-400 font-medium">Sem patch — mitigação manual</span></>
              }
            </div>
            {cve.references[0] && (
              <a href={cve.references[0]} target="_blank" rel="noreferrer"
                className="flex items-center gap-1 text-[10px] text-white/30 hover:text-white/60 transition-colors">
                <ExternalLink size={10} /> Referência
              </a>
            )}
          </div>

          <p className="text-[10px] text-white/40 font-mono">{cve.patch_version}</p>
        </div>
      )}
    </div>
  );
}

// ── Zabbix Health Panel ───────────────────────────────────────────────────────

function ZabbixHealthPanel({ health, loading }: { health: ZabbixHealth | null; loading: boolean }) {
  if (loading) {
    return (
      <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-6 flex items-center justify-center gap-3">
        <div className="w-5 h-5 border-2 border-[#00ADE8]/30 border-t-[#00ADE8] rounded-full animate-spin" />
        <span className="text-sm text-white/30">Verificando Zabbix em tempo real...</span>
      </div>
    );
  }

  if (!health) return null;

  const overall = STATUS_CONFIG[health.overall] ?? STATUS_CONFIG.unknown;
  const OverallIcon = overall.icon;

  return (
    <div className={`rounded-xl border ${overall.border} ${overall.bg} overflow-hidden`}>
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-4 border-b border-white/[0.05]">
        <div className="flex items-center gap-3">
          <div className={`p-2 rounded-lg ${overall.bg} border ${overall.border}`}>
            <OverallIcon size={16} className={overall.color} />
          </div>
          <div>
            <p className="text-sm font-bold text-white">Zabbix — Saúde do Ambiente</p>
            <p className="text-[11px] text-white/30">zabbix.ness.com.br · atualizado agora</p>
          </div>
        </div>
        <div className="flex items-center gap-4">
          <ScoreRing score={health.score} />
          <a href={health.zabbix_url} target="_blank" rel="noreferrer"
            className="flex items-center gap-1.5 text-[11px] text-white/30 hover:text-[#00ADE8] transition-colors">
            <ExternalLink size={11} /> Abrir Zabbix
          </a>
        </div>
      </div>

      {/* Checks grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-px bg-white/[0.04]">
        {health.checks.map((chk) => {
          const cfg = STATUS_CONFIG[chk.status] ?? STATUS_CONFIG.unknown;
          const Icon = cfg.icon;
          return (
            <div key={chk.check} className={`flex items-start gap-3 p-4 ${cfg.bg}`}>
              <Icon size={15} className={`${cfg.color} shrink-0 mt-0.5`} />
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between gap-2 mb-0.5">
                  <p className="text-[11px] font-bold text-white/80">{chk.check}</p>
                  <span className={`text-[10px] font-mono ${cfg.color} shrink-0`}>{chk.value}</span>
                </div>
                <p className="text-[11px] text-white/40 leading-snug">{chk.message}</p>
                {chk.details.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-1">
                    {chk.details.slice(0, 5).map(d => (
                      <span key={d} className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-black/20 text-white/30">{d}</span>
                    ))}
                    {chk.details.length > 5 && (
                      <span className="text-[9px] text-white/20">+{chk.details.length - 5} mais</span>
                    )}
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {health.error && (
        <div className="px-5 py-3 text-xs text-red-400/60 font-mono border-t border-white/[0.04]">
          ⚠ {health.error}
        </div>
      )}
    </div>
  );
}

// ── Client Risk Matrix ────────────────────────────────────────────────────────

function ClientRiskMatrix({ cves }: { cves: CveItem[] }) {
  const clientMap: Record<string, { critical: number; high: number; exploited: number }> = {};

  cves.forEach(cve => {
    cve.affected_clients.forEach(c => {
      if (!clientMap[c]) clientMap[c] = { critical: 0, high: 0, exploited: 0 };
      if (cve.severity === 'critical') clientMap[c].critical++;
      if (cve.severity === 'high') clientMap[c].high++;
      if (cve.exploited_wild) clientMap[c].exploited++;
    });
  });

  const sorted = Object.entries(clientMap)
    .sort((a, b) => (b[1].critical * 3 + b[1].high) - (a[1].critical * 3 + a[1].high));

  return (
    <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] overflow-hidden">
      <div className="px-5 py-3 border-b border-white/[0.05] flex items-center gap-2">
        <Globe size={14} className="text-white/30" />
        <p className="text-sm font-bold text-white/80">Matriz de Risco por Cliente</p>
      </div>
      <div className="divide-y divide-white/[0.04]">
        {sorted.map(([client, stats]) => {
          const color = CLIENT_COLORS[client] ?? '#6B7280';
          const riskScore = stats.critical * 3 + stats.high;
          const riskLabel = riskScore >= 9 ? 'CRÍTICO' : riskScore >= 6 ? 'ALTO' : riskScore >= 3 ? 'MÉDIO' : 'BAIXO';
          const riskColor = riskScore >= 9 ? 'text-red-400' : riskScore >= 6 ? 'text-orange-400' : riskScore >= 3 ? 'text-yellow-400' : 'text-emerald-400';

          return (
            <div key={client} className="flex items-center gap-4 px-5 py-3 hover:bg-white/[0.02] transition-colors">
              <div className="w-2 h-2 rounded-full shrink-0" style={{ background: color }} />
              <p className="text-[12px] font-semibold text-white/80 flex-1 truncate">{client}</p>
              <div className="flex items-center gap-3">
                {stats.critical > 0 && (
                  <span className="text-[11px] text-red-400 font-mono">{stats.critical}×crítico</span>
                )}
                {stats.high > 0 && (
                  <span className="text-[11px] text-orange-400 font-mono">{stats.high}×alto</span>
                )}
                {stats.exploited > 0 && (
                  <span className="flex items-center gap-0.5 text-[10px] font-bold text-red-300 bg-red-500/10 px-1.5 py-0.5 rounded-full">
                    <Zap size={8} /> {stats.exploited}
                  </span>
                )}
                <span className={`text-[10px] font-black uppercase tracking-wider ${riskColor} min-w-[40px] text-right`}>{riskLabel}</span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── Main SecopsModule ─────────────────────────────────────────────────────────

type FilterSev = 'all' | 'critical' | 'high';

export default function SecopsModule() {
  const [cveIntel, setCveIntel] = useState<CveIntel | null>(null);
  const [health, setHealth]     = useState<ZabbixHealth | null>(null);
  const [cveLoading, setCveLoading]       = useState(true);
  const [healthLoading, setHealthLoading] = useState(true);
  const [filter, setFilter]     = useState<FilterSev>('all');
  const [searchTerm, setSearchTerm] = useState('');
  const [exploitedOnly, setExploitedOnly] = useState(false);
  const [lastRefresh, setLastRefresh] = useState<Date>(new Date());

  const fetchAll = useCallback(async () => {
    setCveLoading(true);
    setHealthLoading(true);

    try {
      const res = await fetch(`${API_BASE}/api/secops/cve-intel`);
      if (res.ok) setCveIntel(await res.json());
    } catch (e) { console.error('CVE intel:', e); }
    finally { setCveLoading(false); }

    try {
      const res = await fetch(`${API_BASE}/api/secops/zabbix-health`);
      if (res.ok) setHealth(await res.json());
    } catch (e) { console.error('Zabbix health:', e); }
    finally { setHealthLoading(false); }

    setLastRefresh(new Date());
  }, []);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  // Filter CVEs
  const filteredCves = (cveIntel?.items ?? []).filter(cve => {
    if (filter !== 'all' && cve.severity !== filter) return false;
    if (exploitedOnly && !cve.exploited_wild) return false;
    if (searchTerm) {
      const q = searchTerm.toLowerCase();
      return (
        cve.id.toLowerCase().includes(q) ||
        cve.title.toLowerCase().includes(q) ||
        cve.affected_tech.toLowerCase().includes(q) ||
        cve.affected_clients.some(c => c.toLowerCase().includes(q))
      );
    }
    return true;
  });

  const summary = cveIntel?.summary;

  return (
    <div className="p-8 max-w-6xl space-y-6 animate-fade-in">

      {/* ── Header ─────────────────────────────────────────────────────────── */}
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-red-500/10 border border-red-500/20">
            <ShieldAlert size={20} className="text-red-400" />
          </div>
          <div>
            <h1 className="text-lg font-semibold text-white">Segurança</h1>
            <p className="text-[11px] text-white/40">Vulnerabilidades, monitoramento e risco</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <p className="text-[10px] text-white/20">
            {lastRefresh.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
          </p>
          <button
            onClick={fetchAll}
            className="flex items-center gap-1.5 text-[11px] px-3 py-1.5 rounded-lg bg-white/[0.04] border border-white/[0.08] text-white/50 hover:text-white hover:bg-white/[0.08] transition-all"
          >
            <RefreshCw size={11} /> Atualizar
          </button>
        </div>
      </div>

      {/* ── Summary Cards ──────────────────────────────────────────────────── */}
      {!cveLoading && summary && (
        <div>
          <div className="mb-3 flex items-center gap-2 text-[11px] text-amber-200/80">
            <span className="h-1.5 w-1.5 rounded-full bg-amber-300" />
            Base de referência estática — atualização e aplicabilidade por cliente pendentes.
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {[
            { icon: Bug,         label: 'CVEs Mapeados',    value: summary.total,              color: 'text-white/60',   bg: 'bg-white/[0.04]',     border: 'border-white/[0.06]' },
            { icon: ShieldX,     label: 'Críticos',         value: summary.critical,           color: 'text-red-400',    bg: 'bg-red-500/10',        border: 'border-red-500/20' },
            { icon: AlertTriangle, label: 'Altos',          value: summary.high,               color: 'text-orange-400', bg: 'bg-orange-500/10',     border: 'border-orange-500/20' },
            { icon: Zap,         label: 'Exploração Ativa', value: summary.exploited_in_wild,  color: 'text-red-300',    bg: 'bg-red-500/15',        border: 'border-red-400/30' },
          ].map(({ icon: Icon, label, value, color, bg, border }) => (
            <div key={label} className={`rounded-xl border ${border} ${bg} p-4 flex items-center gap-3`}>
              <Icon size={18} className={color} />
              <div>
                <p className="text-[10px] text-white/30 uppercase tracking-wider">{label}</p>
                <p className={`text-xl font-black ${color}`}>{value}</p>
              </div>
            </div>
          ))}
          </div>
        </div>
      )}

      {/* ── Zabbix Health ──────────────────────────────────────────────────── */}
      <div>
        <div className="flex items-center gap-2 mb-3">
          <Activity size={13} className="text-[#00ADE8]" />
          <p className="text-xs font-bold text-white/50 uppercase tracking-wider">Saúde do Zabbix</p>
        </div>
        <ZabbixHealthPanel health={health} loading={healthLoading} />
      </div>

      {/* ── Client Risk Matrix ──────────────────────────────────────────────── */}
      {cveIntel && (
        <div>
          <div className="flex items-center gap-2 mb-3">
            <Eye size={13} className="text-[#00ADE8]" />
          <p className="text-xs font-bold text-white/50 uppercase tracking-wider">Matriz de referência por cliente</p>
          </div>
          <ClientRiskMatrix cves={cveIntel.items} />
        </div>
      )}

      {/* ── CVE Feed ──────────────────────────────────────────────────────── */}
      <div>
        {/* Filters */}
        <div className="flex items-center gap-3 mb-4 flex-wrap">
          <div className="flex items-center gap-2 mr-2">
            <Shield size={13} className="text-[#00ADE8]" />
            <p className="text-xs font-bold text-white/50 uppercase tracking-wider">CVE Intelligence Feed</p>
          </div>

          <div className="flex items-center bg-white/[0.04] border border-white/[0.08] rounded-lg overflow-hidden">
            {(['all', 'critical', 'high'] as FilterSev[]).map(f => (
              <button key={f} onClick={() => setFilter(f)}
                className={`px-3 py-1.5 text-[11px] font-semibold transition-colors ${
                  filter === f
                    ? 'bg-[#00ADE8]/20 text-[#00ADE8]'
                    : 'text-white/30 hover:text-white/60'
                }`}>
                {f === 'all' ? 'Todos' : f === 'critical' ? 'Crítico' : 'Alto'}
              </button>
            ))}
          </div>

          <button onClick={() => setExploitedOnly(e => !e)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[11px] font-semibold border transition-all ${
              exploitedOnly
                ? 'bg-red-500/20 border-red-500/30 text-red-400'
                : 'bg-white/[0.04] border-white/[0.08] text-white/30 hover:text-white/60'
            }`}>
            <Zap size={10} /> Exploração ativa
          </button>

          <input
            type="text"
            placeholder="Buscar CVE, tech, cliente..."
            value={searchTerm}
            onChange={e => setSearchTerm(e.target.value)}
            className="ml-auto bg-white/[0.04] border border-white/[0.08] rounded-lg px-3 py-1.5 text-[11px] text-white/60 placeholder-white/20 outline-none focus:border-[#00ADE8]/40 transition-colors w-48"
          />
        </div>

        {/* CVE List */}
        {cveLoading ? (
          <div className="space-y-3">
            {[1,2,3].map(i => (
              <div key={i} className="h-16 rounded-xl bg-white/[0.03] border border-white/[0.05] animate-pulse" />
            ))}
          </div>
        ) : (
          <div className="space-y-2">
            {filteredCves.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-12 gap-2">
                <ShieldCheck size={28} className="text-emerald-400 opacity-50" />
                <p className="text-sm text-white/30">Nenhum CVE encontrado com os filtros selecionados</p>
              </div>
            ) : (
              filteredCves.map(cve => <CveCard key={cve.id} cve={cve} />)
            )}
          </div>
        )}

        {/* Footer */}
        {cveIntel && (
          <div className="mt-4 flex items-center justify-between text-[10px] text-white/20">
            <span>Fonte: {cveIntel.source}</span>
            <span>Atualizado em: {new Date(cveIntel.updated_at).toLocaleDateString('pt-BR')}</span>
          </div>
        )}
      </div>

    </div>
  );
}
