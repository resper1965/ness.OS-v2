import React from 'react';
import { ShieldAlert, CheckCircle, Clock, Server, AlertTriangle, RefreshCw } from 'lucide-react';

const SEVERITY_CONFIG: Record<string, { badge: string; dot: string; label: string }> = {
  disaster:       { badge: 'bg-red-500/15 border-red-500/40 text-red-400',     dot: 'bg-red-500 shadow-[0_0_8px_rgba(239,68,68,0.9)]',         label: 'Desastre' },
  high:           { badge: 'bg-red-400/10 border-red-400/30 text-red-400',     dot: 'bg-red-400 shadow-[0_0_6px_rgba(248,113,113,0.7)]',        label: 'Alta' },
  average:        { badge: 'bg-orange-400/10 border-orange-400/25 text-orange-400', dot: 'bg-orange-400 shadow-[0_0_6px_rgba(251,146,60,0.6)]', label: 'Média' },
  warning:        { badge: 'bg-yellow-400/10 border-yellow-400/25 text-yellow-400', dot: 'bg-yellow-400 shadow-[0_0_5px_rgba(250,204,21,0.5)]', label: 'Aviso' },
  info:           { badge: 'bg-blue-400/10 border-blue-400/20 text-blue-400',  dot: 'bg-blue-400',                                              label: 'Info' },
  not_classified: { badge: 'bg-white/5 border-white/10 text-white/30',         dot: 'bg-white/20',                                              label: 'N/C' },
};

const STATUS_CONFIG: Record<string, { label: string; style: string }> = {
  open:     { label: 'Aberto',    style: 'bg-red-500/10 text-red-400 border-red-500/20' },
  acknowledged: { label: 'Reconhecido', style: 'bg-amber-500/10 text-amber-300 border-amber-500/20' },
  resolved: { label: 'Resolvido', style: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' },
  closed:   { label: 'Fechado',   style: 'bg-white/5 text-white/30 border-white/10' },
};

const STAGES = [
  { key: 'detected',         label: 'Detectado',  shortLabel: 'D' },
  { key: 'incident_created', label: 'Incidente',  shortLabel: 'I' },
  { key: 'ticket_opened',    label: 'Ticket',     shortLabel: 'T' },
  { key: 'resolved',        label: 'Resolvido',  shortLabel: 'R' },
];
const STAGE_ORDER = STAGES.map(s => s.key);

function IncidentTimeline({ stage }: { stage: string }) {
  const currentIdx = Math.max(0, STAGE_ORDER.indexOf(stage));
  return (
    <div className="flex items-center mt-3 pt-3 border-t border-white/[0.04]">
      <span className="text-[9px] text-white/25 uppercase tracking-wider mr-3 shrink-0">Fluxo</span>
      <div className="flex items-center flex-1">
        {STAGES.map((s, i) => {
          const done    = i <= currentIdx;
          const current = i === currentIdx;
          return (
            <React.Fragment key={s.key}>
              <div className="flex flex-col items-center group relative">
                <div className={`
                  w-5 h-5 rounded-full flex items-center justify-center text-[8px] font-bold
                  transition-all duration-300
                  ${done
                    ? current
                      ? 'bg-[var(--color-brand-primary)] text-white ring-2 ring-[var(--color-brand-primary)]/40 ring-offset-1 ring-offset-[var(--color-brand-surface)]'
                      : 'bg-[var(--color-brand-primary)]/20 border border-[var(--color-brand-primary)]/40 text-[var(--color-brand-primary)]'
                    : 'bg-white/[0.04] border border-white/10 text-white/20'
                  }
                `}>
                  {i < currentIdx ? '✓' : s.shortLabel}
                </div>
                {/* Tooltip */}
                <div className="absolute bottom-full mb-1.5 hidden group-hover:block z-50 pointer-events-none">
                  <div className="bg-[#0c0c18] border border-white/10 rounded px-2 py-1 text-[9px] text-white/60 whitespace-nowrap shadow-xl">
                    {s.label}
                  </div>
                </div>
              </div>
              {i < STAGES.length - 1 && (
                <div className={`flex-1 h-px mx-0.5 transition-colors duration-300
                  ${i < currentIdx ? 'bg-[var(--color-brand-primary)]/30' : 'bg-white/[0.06]'}`}
                />
              )}
            </React.Fragment>
          );
        })}
      </div>
    </div>
  );
}

function timeAgo(iso: string | null): string {
  if (!iso) return '—';
  const s = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 60)    return `${s}s`;
  if (s < 3600)  return `${Math.floor(s / 60)}min`;
  if (s < 86400) return `${Math.floor(s / 3600)}h`;
  return `${Math.floor(s / 86400)}d`;
}

interface Incident {
  id: string; title: string; severity: string;
  severity_level: number; host_name: string; status: string;
  alert_count: number; first_seen: string | null;
  last_seen: string | null; pipeline_stage: string;
  client?: string; ticket_id?: string | null;
  solution?: string | null;
  source_status?: string;
  source_recovered_at?: string | null;
  assigned_user_id?: number | null;
  asset?: { name: string; glpi_itemtype?: string; glpi_item_id?: number; owner?: string; owner_group_id?: number } | null;
}

interface IncidentDetail extends Incident {
  host_id: string;
  trigger_id: string;
  source_event_id: string | null;
  source_url: string | null;
  description: string | null;
  resolution_sync_status: string | null;
  actions: Array<{
    id: string;
    actor_user_id: number | null;
    actor_source: string;
    action: string;
    previous_status: string | null;
    new_status: string | null;
    note: string | null;
    created_at: string;
  }>;
}

type Action = 'acknowledge' | 'assign_self' | 'comment' | 'resolve' | 'close';
const ACTION_LABEL: Record<Action, string> = {
  acknowledge: 'Reconheceu',
  assign_self: 'Assumiu',
  comment: 'Comentou',
  resolve: 'Resolveu',
  close: 'Encerrou',
};
interface Props { incidents: Incident[]; total: number; loading: boolean; loadingMore: boolean; error: string | null; canAct: boolean; onChanged: () => void | Promise<void>; onLoadMore: () => void | Promise<void>; }

export default function IncidentsPage({ incidents, total, loading, loadingMore, error, canAct, onChanged, onLoadMore }: Props) {
  const openCount = incidents.filter(i => i.status === 'open').length;
  const [activeId, setActiveId] = React.useState<string | null>(null);
  const [detail, setDetail] = React.useState<IncidentDetail | null>(null);
  const [detailLoading, setDetailLoading] = React.useState(false);
  const [detailError, setDetailError] = React.useState<string | null>(null);
  const [reloadKey, setReloadKey] = React.useState(0);
  const [note, setNote] = React.useState('');
  const [acting, setActing] = React.useState(false);

  React.useEffect(() => {
    if (!activeId) return;
    const controller = new AbortController();
    setDetail(null);
    setDetailError(null);
    setDetailLoading(true);
    fetch(`${import.meta.env.VITE_API_URL ?? ''}/api/incidents/${encodeURIComponent(activeId)}`, {
      credentials: 'include',
      signal: controller.signal,
    })
      .then(async response => {
        if (!response.ok) throw new Error('Não foi possível carregar o detalhe do incidente');
        return response.json() as Promise<IncidentDetail>;
      })
      .then(setDetail)
      .catch(err => {
        if (!controller.signal.aborted) setDetailError(err.message);
      })
      .finally(() => {
        if (!controller.signal.aborted) setDetailLoading(false);
      });
    return () => controller.abort();
  }, [activeId, reloadKey]);

  const submitAction = async (action: Action) => {
    if (!activeId) return;
    setActing(true);
    setDetailError(null);
    try {
      const response = await fetch(`${import.meta.env.VITE_API_URL ?? ''}/api/incidents/${encodeURIComponent(activeId)}/actions`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action, note: note.trim() || null }),
      });
      if (!response.ok) throw new Error('A ação não pôde ser registrada. Atualize o incidente e tente novamente.');
      setNote('');
      setReloadKey(key => key + 1);
      void onChanged();
    } catch (err) {
      setDetailError(err instanceof Error ? err.message : 'Falha ao registrar ação');
    } finally {
      setActing(false);
    }
  };

  return (
    <div className="space-y-4 animate-fade-in">
      {/* Page subtitle / stats bar */}
      {!loading && !error && (
        <div className="flex items-center gap-4 px-1">
          <div className="flex items-center gap-1.5 text-xs text-[var(--color-brand-muted)]">
            <ShieldAlert size={13} />
            <span className="font-medium text-white">{incidents.length}</span> de {total} incidente{total !== 1 ? 's' : ''}
          </div>
          {openCount > 0 && (
            <div className="flex items-center gap-1.5 text-xs text-red-400">
              <AlertTriangle size={11} />
              <span className="font-medium">{openCount}</span> aberto{openCount !== 1 ? 's' : ''} nesta lista
            </div>
          )}
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="flex items-center gap-2 text-red-400 text-sm p-4 rounded-xl bg-red-500/10 border border-red-500/20">
          <AlertTriangle size={16} /> {error}
        </div>
      )}

      {/* Loading skeleton */}
      {loading && (
        <div className="space-y-3">
          {[1,2,3].map(i => (
            <div key={i} className="h-28 bg-white/[0.03] rounded-xl border border-white/[0.05] animate-pulse" />
          ))}
        </div>
      )}

      {/* Empty state */}
      {!loading && !error && incidents.length === 0 && (
        <div className="flex flex-col items-center justify-center py-20 gap-3">
          <div className="w-14 h-14 rounded-2xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center">
            <CheckCircle size={26} className="text-emerald-400" />
          </div>
          <p className="font-medium text-white/70">Nenhum incidente registrado</p>
          <p className="text-xs text-[var(--color-brand-muted)] text-center max-w-xs">
            Quando alertas do monitoramento forem processados pelo pipeline AIOps, aparecerão aqui.
          </p>
        </div>
      )}

      {/* Incident cards */}
      {!loading && incidents.map((inc, idx) => {
        const sev   = SEVERITY_CONFIG[inc.severity] ?? SEVERITY_CONFIG.not_classified;
        const stCfg = STATUS_CONFIG[inc.status] ?? STATUS_CONFIG.open;
        return (
          <div
            key={inc.id}
            className="
              bg-[var(--color-brand-surface)] border border-white/[0.06]
              rounded-xl p-4 hover:border-white/[0.10]
              hover:shadow-[0_4px_24px_rgba(0,0,0,0.3)]
              transition-all duration-300 hover:-translate-y-0.5
              animate-fade-in
            "
            style={{ animationDelay: `${idx * 40}ms` }}
          >
            <div className="flex items-start justify-between gap-4">
              {/* Left */}
              <div className="flex items-start gap-3 min-w-0">
                <div className={`mt-1 w-2.5 h-2.5 rounded-full shrink-0 ${sev.dot}`} />
                <div className="min-w-0">
                  <p className="font-semibold text-sm text-white/90 leading-snug">{inc.title}</p>
                  <div className="flex items-center gap-3 mt-1.5">
                    <span className="flex items-center gap-1 text-[11px] text-[var(--color-brand-muted)]">
                      <Server size={10} /> {inc.host_name}
                    </span>
                    {inc.alert_count > 1 && (
                      <span className="flex items-center gap-1 text-[11px] text-[var(--color-brand-muted)]">
                        <RefreshCw size={9} /> {inc.alert_count}×
                      </span>
                    )}
                  </div>
                  {inc.client && <p className="mt-1 text-[11px] text-[var(--color-brand-muted)]">{inc.client}</p>}
                  {inc.asset && <p className="mt-1 text-[11px] text-[var(--color-brand-muted)]">Ativo: {inc.asset.name} · Responsável: {inc.asset.owner || (inc.asset.owner_group_id ? `Equipe GLPI #${inc.asset.owner_group_id}` : 'Não cadastrado')}</p>}
                  {inc.solution && <p className="mt-2 whitespace-pre-wrap text-xs text-white/70">Solução: {inc.solution}</p>}
                  {inc.ticket_id && (
                    <a
                      href={`https://n-ticket.ness.com.br/front/ticket.form.php?id=${encodeURIComponent(inc.ticket_id)}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="mt-2 inline-block text-xs text-[var(--color-brand-primary)] hover:underline"
                    >
                      Abrir chamado GLPI #{inc.ticket_id}
                    </a>
                  )}
                </div>
              </div>

              {/* Right meta */}
              <div className="flex flex-col items-end gap-2 shrink-0">
                <div className="flex items-center gap-2">
                  <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full border ${sev.badge}`}>
                    {sev.label}
                  </span>
                  <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full border ${stCfg.style}`}>
                    {stCfg.label}
                  </span>
                </div>
                <div className="flex items-center gap-1 text-[11px] text-[var(--color-brand-muted)]">
                  <Clock size={10} /> {timeAgo(inc.last_seen)}
                </div>
              </div>
            </div>

            {/* Pipeline timeline */}
            <IncidentTimeline stage={inc.pipeline_stage} />
            <button
              type="button"
              className="mt-3 text-xs text-[var(--color-brand-primary)] hover:underline"
              aria-expanded={activeId === inc.id}
              aria-controls={`incident-detail-${inc.id}`}
              onClick={() => { setNote(''); setActiveId(activeId === inc.id ? null : inc.id); }}
            >
              {activeId === inc.id ? 'Ocultar detalhes' : 'Ver detalhes'}
            </button>
            {activeId === inc.id && (
              <div id={`incident-detail-${inc.id}`} className="mt-3 border-t border-white/[0.06] pt-3 space-y-2 text-xs text-white/70">
                {detailLoading && <p role="status">Carregando detalhes...</p>}
                {detailError && <p role="alert" className="text-red-400">{detailError}</p>}
                {detail && (
                  <>
                    <p className="whitespace-pre-wrap">{detail.description || 'Sem descrição da origem.'}</p>
                    <p>Host Zabbix #{detail.host_id} · Trigger #{detail.trigger_id} · Evento #{detail.source_event_id || 'indisponível'}</p>
                    {detail.source_url && (
                      <a href={detail.source_url} target="_blank" rel="noopener noreferrer" className="inline-block text-[var(--color-brand-primary)] hover:underline">
                        Abrir evento no Zabbix
                      </a>
                    )}
                    <p>Sincronização da resolução: {detail.resolution_sync_status || 'sem atualização registrada'}</p>
                    <p>Estado Zabbix: {detail.source_status === 'resolved' ? `sinal recuperado em ${detail.source_recovered_at || 'horário indisponível'}` : detail.source_status === 'problem' ? 'problema ativo' : 'não registrado'}</p>
                    <p>Responsável no Hub: {detail.assigned_user_id ? `usuário #${detail.assigned_user_id}` : 'não atribuído'}</p>
                    {canAct && (
                      <div className="space-y-2 border-t border-white/[0.06] pt-3">
                        <label htmlFor={`incident-note-${inc.id}`} className="block">Comentário ou justificativa</label>
                        <textarea
                          id={`incident-note-${inc.id}`}
                          value={note}
                          onChange={event => setNote(event.target.value)}
                          maxLength={2000}
                          rows={2}
                          className="w-full rounded-md border border-white/15 bg-black/20 p-2 text-white"
                        />
                        <div className="flex flex-wrap gap-2">
                          {detail.status === 'open' && <button type="button" disabled={acting} onClick={() => void submitAction('acknowledge')} className="rounded border border-white/20 px-2 py-1 disabled:opacity-50">Reconhecer</button>}
                          {detail.status !== 'closed' && <button type="button" disabled={acting} onClick={() => void submitAction('assign_self')} className="rounded border border-white/20 px-2 py-1 disabled:opacity-50">Assumir</button>}
                          <button type="button" disabled={acting || !note.trim()} onClick={() => void submitAction('comment')} className="rounded border border-white/20 px-2 py-1 disabled:opacity-50">Registrar comentário</button>
                          {!detail.ticket_id && ['open', 'acknowledged'].includes(detail.status) && <button type="button" disabled={acting || !note.trim()} onClick={() => void submitAction('resolve')} className="rounded border border-white/20 px-2 py-1 disabled:opacity-50">Resolver</button>}
                          {detail.status === 'resolved' && (!detail.ticket_id || detail.resolution_sync_status === 'synced') && <button type="button" disabled={acting} onClick={() => void submitAction('close')} className="rounded border border-white/20 px-2 py-1 disabled:opacity-50">Encerrar</button>}
                        </div>
                      </div>
                    )}
                    <div className="border-t border-white/[0.06] pt-3">
                      <p className="font-semibold text-white/80">Ações registradas</p>
                      {detail.actions.length === 0 && <p className="mt-1">Nenhuma ação registrada.</p>}
                      <ol className="mt-2 space-y-2">
                        {detail.actions.map(action => (
                          <li key={action.id} className="border-l border-white/15 pl-3">
                            <span className="font-medium text-white/80">{ACTION_LABEL[action.action as Action] ?? action.action}</span>
                            <span> · {action.actor_user_id ? `usuário #${action.actor_user_id}` : action.actor_source} · {new Date(action.created_at).toLocaleString('pt-BR')}</span>
                            {action.note && <p className="whitespace-pre-wrap">{action.note}</p>}
                          </li>
                        ))}
                      </ol>
                    </div>
                  </>
                )}
              </div>
            )}
          </div>
        );
      })}
      {!loading && incidents.length < total && (
        <button type="button" disabled={loadingMore} onClick={() => void onLoadMore()} className="w-full rounded-xl border border-white/15 px-4 py-3 text-sm text-white/80 hover:border-white/30 disabled:opacity-50">
          {loadingMore ? 'Carregando...' : 'Carregar mais incidentes'}
        </button>
      )}
    </div>
  );
}
