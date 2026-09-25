import React from 'react';
import { Zap, Cpu, GitBranch, Ticket, MessageCircle, CheckCircle2, AlertCircle, Minus } from 'lucide-react';

interface NodeStatus {
  status: 'ok' | 'error' | 'unconfigured' | 'degraded' | 'disabled';
  detail?: string;
}

interface PipelineData {
  zabbix?:      NodeStatus;
  workers?:     NodeStatus;
  delivery?:    NodeStatus;
  deskmanager?: NodeStatus;
  whatsapp?:    NodeStatus;
}

const NODES: {
  key: keyof PipelineData;
  label: string;
  icon: React.ElementType;
  description: string;
}[] = [
  { key: 'zabbix',      label: 'Monitoramento', icon: Zap,           description: 'Coleta de alertas' },
  { key: 'workers',     label: 'Processamento',  icon: Cpu,           description: 'Workers e filas de incidentes' },
  { key: 'delivery',    label: 'Entregas',       icon: GitBranch,     description: 'Tickets e resoluções pendentes' },
  { key: 'deskmanager', label: 'Helpdesk',        icon: Ticket,        description: 'Abertura de ticket' },
  { key: 'whatsapp',    label: 'Mensageria',      icon: MessageCircle, description: 'Notificação' },
];

function StatusIcon({ status }: { status: string }) {
  if (status === 'ok')           return <CheckCircle2 size={11} className="text-emerald-400" />;
  if (status === 'error')        return <AlertCircle  size={11} className="text-red-400" />;
  return <Minus size={10} className="text-white/20" />;
}

function PipelineNode({
  label, description, icon: Icon, data, isLast,
}: {
  label: string; description: string; icon: React.ElementType;
  data?: NodeStatus; isLast: boolean;
}) {
  const rawStatus = data?.status ?? 'unconfigured';
  const st = rawStatus === 'disabled' ? 'unconfigured' : rawStatus === 'degraded' ? 'error' : rawStatus;

  const styles = {
    ok:           { ring: 'ring-emerald-500/30', bg: 'bg-emerald-500/10', icon: 'text-emerald-400', text: 'text-emerald-400', dot: 'bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.8)]' },
    error:        { ring: 'ring-red-500/30',     bg: 'bg-red-500/10',     icon: 'text-red-400',     text: 'text-red-400',     dot: 'bg-red-400 shadow-[0_0_8px_rgba(239,68,68,0.8)]' },
    unconfigured: { ring: 'ring-white/5',         bg: 'bg-white/[0.03]',   icon: 'text-white/20',    text: 'text-white/25',    dot: 'bg-white/15' },
  }[st];

  return (
    <div className="flex items-center">
      {/* Node card */}
      <div className={`
        group relative flex flex-col items-center gap-2 px-4 py-3 rounded-xl
        ring-1 ${styles.ring} ${styles.bg}
        transition-all duration-300 hover:scale-105 hover:ring-2
        min-w-[80px] cursor-default
      `}>
        {/* Status dot */}
        <div className={`absolute -top-1 -right-1 w-2.5 h-2.5 rounded-full ${styles.dot} ring-2 ring-[var(--color-brand-base)]`} />

        {/* Icon */}
        <div className={`p-2 rounded-lg bg-white/[0.05] ${styles.icon}`}>
          <Icon size={14} />
        </div>

        {/* Label */}
        <div className="text-center">
          <p className={`text-[11px] font-semibold ${styles.text} leading-tight`}>{label}</p>
          <p className="text-[9px] text-white/20 mt-0.5 leading-tight">{description}</p>
        </div>

        {/* Status row */}
        <div className="flex items-center gap-1">
          <StatusIcon status={st} />
          <span className={`text-[9px] font-medium ${styles.text} capitalize`}>
            {st === 'unconfigured' ? 'N/C' : st === 'ok' ? 'Online' : 'Erro'}
          </span>
        </div>

        {/* Tooltip */}
        {data?.detail && (
          <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 hidden group-hover:block z-50 pointer-events-none">
            <div className="bg-[#0c0c18] border border-white/10 rounded-lg px-3 py-1.5 text-[10px] text-white/70 whitespace-nowrap shadow-2xl">
              {data.detail}
              <div className="absolute top-full left-1/2 -translate-x-1/2 w-0 h-0 border-x-4 border-x-transparent border-t-4 border-t-white/10" />
            </div>
          </div>
        )}
      </div>

      {/* Connector */}
      {!isLast && (
        <div className="flex items-center gap-0 mx-1.5">
          <div className={`h-px w-6 ${st === 'ok' ? 'bg-emerald-500/40' : 'bg-white/10'}`} />
          <div className={`w-0 h-0 border-y-[3px] border-y-transparent border-l-[4px]
            ${st === 'ok' ? 'border-l-emerald-500/40' : 'border-l-white/10'}`} />
        </div>
      )}
    </div>
  );
}

export default function PipelineStrip({
  data, loading,
}: { data: PipelineData | null; loading: boolean }) {

  const allOk = data && NODES.every(n => ['ok', 'disabled'].includes(data[n.key]?.status ?? ''));
  const hasError = data && NODES.some(n => ['error', 'degraded'].includes(data[n.key]?.status ?? ''));

  return (
    <div className="
      relative flex flex-col gap-3 px-5 py-4
      bg-[var(--color-brand-surface)] border border-white/[0.06] rounded-xl overflow-hidden
    ">
      {/* Header row */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-[10px] font-semibold uppercase tracking-[0.15em] text-[var(--color-brand-muted)]">
            Fluxo de incidentes
          </span>
          {!loading && data && (
            <span className={`text-[9px] font-semibold px-2 py-0.5 rounded-full
              ${allOk
                ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                : hasError
                  ? 'bg-red-500/10 text-red-400 border border-red-500/20'
                  : 'bg-yellow-500/10 text-yellow-400 border border-yellow-500/20'
              }`}
            >
              {allOk ? '● Todos online' : hasError ? '● Degradado' : '● Parcial'}
            </span>
          )}
        </div>

        {/* Background radial glow */}
        <div
          className="absolute inset-0 pointer-events-none"
          style={{
            background: allOk
              ? 'radial-gradient(ellipse at 50% 50%, rgba(16,185,129,0.03) 0%, transparent 70%)'
              : 'transparent'
          }}
        />
      </div>

      {/* Nodes */}
      {loading ? (
        <div className="flex items-center gap-2">
          {NODES.map(n => (
            <div key={n.key} className="flex items-center">
              <div className="flex flex-col items-center gap-2 px-4 py-3 rounded-xl bg-white/[0.03] ring-1 ring-white/5 min-w-[80px]">
                <div className="w-8 h-8 rounded-lg bg-white/[0.04] animate-pulse" />
                <div className="w-12 h-2 bg-white/[0.04] rounded animate-pulse" />
                <div className="w-8 h-1.5 bg-white/[0.03] rounded animate-pulse" />
              </div>
              {n.key !== 'whatsapp' && <div className="w-8 h-px bg-white/5 mx-1.5" />}
            </div>
          ))}
        </div>
      ) : (
        <div className="flex items-center">
          {NODES.map((n, i) => (
            <PipelineNode
              key={n.key}
              label={n.label}
              description={n.description}
              icon={n.icon}
              data={data?.[n.key]}
              isLast={i === NODES.length - 1}
            />
          ))}
        </div>
      )}
    </div>
  );
}
