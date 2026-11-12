type StackState = 'ok' | 'degraded' | 'down' | 'planned' | 'unavailable';

interface StackDomain {
  status: StackState;
  error_code?: string | null;
  provider_status?: string | null;
}

interface StackItem {
  name: string;
  status: StackState;
  cause?: string | null;
  domains: Record<string, StackDomain>;
}

interface StackFinding {
  stack: string;
  code: string;
  message: string;
}

interface StackSummary {
  total: number;
  ok: number;
  degraded: number;
  down: number;
}

export interface StackHealthData {
  summary: StackSummary;
  stacks: StackItem[];
  findings: StackFinding[];
}

function statusLabel(status: StackState): string {
  if (status === 'ok') return 'ok';
  if (status === 'degraded') return 'degradado';
  if (status === 'down') return 'indisponível';
  if (status === 'planned') return 'planejado';
  return 'não disponível';
}

function statusTone(status: StackState): string {
  if (status === 'ok') return 'text-emerald-300';
  if (status === 'degraded') return 'text-amber-300';
  if (status === 'down') return 'text-rose-300';
  return 'text-white/45';
}

function stackFinding(name: string, findings: StackFinding[]): string | null {
  return findings.find(item => item.stack === name)?.message ?? null;
}

export default function StackHealthPanel({ data }: { data: StackHealthData | null }) {
  if (!data) {
    return (
      <section className="mt-6 border border-white/[0.09] bg-white/[0.02] p-5 sm:p-6" aria-label="Saúde das stacks">
        <h2 className="text-sm font-semibold">Saúde das stacks</h2>
        <p className="mt-2 text-xs text-white/45">Sem coleta consolidada disponível.</p>
      </section>
    );
  }

  return (
    <section className="mt-6 border border-white/[0.09] bg-white/[0.02] p-5 sm:p-6" aria-label="Saúde das stacks">
      <div className="flex flex-wrap items-center gap-3">
        <h2 className="text-sm font-semibold">Saúde das stacks</h2>
        <span className="text-xs text-white/45">
          {data.summary.ok} ok · {data.summary.degraded} degradado · {data.summary.down} indisponível
        </span>
      </div>

      <div className="mt-4 space-y-3">
        {data.stacks.map(stack => {
          const finding = stackFinding(stack.name, data.findings);
          return (
            <article key={stack.name} className="border border-white/[0.08] bg-white/[0.01] p-3">
              <div className="flex items-center justify-between gap-3">
                <h3 className="text-sm font-medium text-white">{stack.name}</h3>
                <span className={`text-xs ${statusTone(stack.status)}`}>{statusLabel(stack.status)}</span>
              </div>
              {finding ? <p className="mt-2 text-xs text-amber-200">{finding}</p> : null}
              {stack.cause ? <p className="mt-1 text-xs text-white/45">Causa: {stack.cause}</p> : null}
            </article>
          );
        })}
      </div>
    </section>
  );
}
