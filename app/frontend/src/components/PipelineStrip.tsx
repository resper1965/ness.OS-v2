import { timeAgo } from '../access';
import { Badge, Panel, type Tone } from './ui/kit';

interface NodeStatus {
  status?: 'ok' | 'error' | 'unconfigured' | 'degraded' | 'disabled';
  detail?: string;
  last_success_at?: string | null;
  workers_seen?: number;
  failed_tasks?: number;
  retrying_tasks?: number;
  queues?: Record<string, number>;
  incidents_without_ticket?: number;
  resolutions_pending?: number;
}
type PipelineData = Partial<Record<'zabbix' | 'workers' | 'delivery' | 'glpi', NodeStatus>>;

const STATUS: Record<string, [Tone, string]> = {
  ok: ['ok', 'Normal'], degraded: ['warn', 'Degradado'], error: ['bad', 'Falha'],
};

// O que cada etapa faz e o que está acontecendo nela agora, em texto (sem tooltip).
export function describe(key: keyof PipelineData, n: NodeStatus | undefined): string {
  if (!n?.status || n.status === 'unconfigured' || n.status === 'disabled') return 'Não configurado';
  if (key === 'workers') {
    const queued = Object.values(n.queues ?? {}).reduce((a, b) => a + b, 0);
    const parts = [`${n.workers_seen ?? 0} workers`, `${queued} na fila`];
    if (n.failed_tasks) parts.push(`${n.failed_tasks} alertas recusados nos últimos 15 min (ver logs do worker)`);
    if (n.retrying_tasks) parts.push(`${n.retrying_tasks} em nova tentativa`);
    return parts.join(' · ');
  }
  if (key === 'delivery') return `${n.incidents_without_ticket ?? 0} incidentes sem chamado · ${n.resolutions_pending ?? 0} resoluções pendentes`;
  return n.status === 'ok' ? `Respondeu ${timeAgo(n.last_success_at)}` : `Última resposta válida ${timeAgo(n.last_success_at)}`;
}

const NODES = [
  ['zabbix', 'Coleta', 'Zabbix envia o alerta'],
  ['workers', 'Processamento', 'Cria ou atualiza o incidente'],
  ['delivery', 'Entrega', 'Abre e fecha o chamado'],
  ['glpi', 'Helpdesk', 'GLPI recebe o chamado'],
] as const;

export default function PipelineStrip({ data, loading }: { data: PipelineData | null; loading: boolean }) {
  return (
    <Panel title="Fluxo de incidentes" meta={loading && !data ? <span className="nx-meta">Consultando…</span> : undefined} flush>
      <ol className="nx-flow">
        {NODES.map(([key, label, role]) => {
          const n = data?.[key];
          const [tone, text] = STATUS[n?.status ?? ''] ?? ['neutral', 'N/C'];
          return (
            <li key={key}>
              <div className="nx-actions"><strong>{label}</strong><Badge tone={tone}>{text}</Badge></div>
              <span className="nx-muted">{role}</span>
              <span>{data ? describe(key, n) : '—'}</span>
            </li>
          );
        })}
      </ol>
    </Panel>
  );
}
