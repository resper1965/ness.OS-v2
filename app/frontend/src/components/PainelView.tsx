import { useEffect, useState } from 'react';
import { asApiError, request, type ApiError } from '../http';
import { timeAgo } from '../access';
import { Badge, Empty, ErrorState, Panel, Screen, Skeleton } from './ui/kit';

interface Painel {
  customer: string; generated_at: string;
  agora: { noc: number; soc: number; criticos: number };
  disponibilidade: { fora_do_ar: number; itens: { id: number; host: string; titulo: string; severidade: number; desde: string }[] };
  seguranca: { periodo_dias: number; total: number; por_classe: Record<string, number>; top_regras: { regra: string; total: number }[] };
  exposicao: { por_severidade: Record<string, number>; maquinas: number; maquinas_criticas: number; maquinas_sem_suporte: number; coleta: string | null };
  cobertura: { inventario: number; por_tipo: Record<string, number>; maquinas_varridas: number };
}

const n = (v: number) => v.toLocaleString('pt-BR');
const SEV: [string, string][] = [['Critical', 'Crítica'], ['High', 'Alta'], ['Medium', 'Média'], ['Low', 'Baixa']];
const TIPO: Record<string, string> = { windows: 'Windows', linux: 'Linux', network_device: 'Rede', unknown: 'Outros' };

// O escopo do cliente quem fixa é a API; o operador escolhe aqui, a partir do cadastro de clientes.
export const painelQuery = (tenant: string | null) => (tenant ? `?customer_id=${encodeURIComponent(tenant)}` : '');

export default function PainelView({ isOperator, refreshKey = 0 }: { isOperator: boolean; refreshKey?: number }) {
  const [clientes, setClientes] = useState<{ key: string; nome: string }[]>([]);
  const [tenant, setTenant] = useState<string | null>(null);
  const [tentativa, setTentativa] = useState(0);
  const [data, setData] = useState<Painel | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const needsPick = isOperator && !tenant;

  useEffect(() => {
    if (isOperator) request<{ key: string; nome: string }[]>('/api/painel/clientes').then(setClientes, e => setError(asApiError(e)));
  }, [isOperator]);

  // Resposta de um cliente já trocado não pode sobrescrever o atual.
  useEffect(() => {
    if (needsPick) return;
    let atual = true;
    request<Painel>(`/api/painel${painelQuery(tenant)}`).then(
      d => { if (atual) { setData(d); setError(null); } },
      e => { if (atual) setError(asApiError(e)); },
    );
    return () => { atual = false; setData(null); };
  }, [tenant, needsPick, refreshKey, tentativa]);

  const seletor = isOperator && (
    <label className="nx-field nx-inline">Cliente
      <select value={tenant ?? ''} onChange={e => { setTenant(e.target.value || null); setError(null); }}>
        <option value="">Escolha…</option>
        {clientes.map(c => <option key={c.key} value={c.key}>{c.nome}</option>)}
      </select>
    </label>
  );

  if (needsPick) return <Screen>{seletor}{error ? <ErrorState error={error} onRetry={() => setError(null)} /> : <Empty title="Escolha um cliente." />}</Screen>;
  if (error) return <Screen>{seletor}<ErrorState error={error} onRetry={() => setTentativa(t => t + 1)} /></Screen>;
  if (!data) return <Screen>{seletor}<Skeleton rows={6} /></Screen>;

  const { agora, disponibilidade: disp, seguranca: seg, exposicao: exp, cobertura: cob } = data;
  return (
    <Screen>
      {seletor}
      <Panel title="Agora" meta={<span className="nx-meta">atualizado {timeAgo(data.generated_at)}</span>}>
        <dl className="nx-kpis">
          <div><dt>Chamados NOC</dt><dd>{n(agora.noc)}</dd></div>
          <div><dt>Chamados SOC</dt><dd>{n(agora.soc)}</dd></div>
          <div><dt>Críticos abertos</dt><dd className={agora.criticos ? 'bad' : ''}>{n(agora.criticos)}</dd></div>
        </dl>
      </Panel>

      <div className="nx-cols">
        <Panel title="Disponibilidade" flush meta={<Badge tone={disp.fora_do_ar ? 'bad' : 'ok'}>{disp.fora_do_ar ? `${n(disp.fora_do_ar)} com problema` : 'Sem problema ativo'}</Badge>}>
          {!disp.itens.length ? <Empty title="Nada fora do ar." /> : (
            <table className="nx-table nx-dense"><tbody>
              {disp.itens.map(i => <tr key={i.id}><td>{i.host}</td><td>{i.titulo}</td><td className="nx-mono">{timeAgo(i.desde)}</td></tr>)}
            </tbody></table>
          )}
        </Panel>

        <Panel title="Segurança" flush meta={<span className="nx-meta">{n(seg.total)} triados em {seg.periodo_dias} dias</span>}>
          {!seg.top_regras.length ? <Empty title="Sem alertas no período." /> : (
            <table className="nx-table nx-dense"><tbody>
              {seg.top_regras.map(r => <tr key={r.regra}><td>{r.regra}</td><td className="nx-mono" style={{ textAlign: 'right' }}>{n(r.total)}</td></tr>)}
            </tbody></table>
          )}
        </Panel>
      </div>

      <Panel title="Exposição" meta={<span className="nx-meta">{exp.coleta ? `coleta de ${new Date(exp.coleta).toLocaleDateString('pt-BR')}` : 'sem coleta'}</span>}>
        <dl className="nx-kpis">
          {SEV.map(([k, label]) => <div key={k}><dt>{label}</dt><dd className={k === 'Critical' && exp.por_severidade[k] ? 'bad' : ''}>{n(exp.por_severidade[k] ?? 0)}</dd></div>)}
          <div><dt>Máquinas com crítica</dt><dd className={exp.maquinas_criticas ? 'bad' : ''}>{n(exp.maquinas_criticas)}</dd></div>
          <div><dt>Sistema sem suporte</dt><dd className={exp.maquinas_sem_suporte ? 'bad' : ''}>{n(exp.maquinas_sem_suporte)}</dd></div>
        </dl>
      </Panel>

      <Panel title="Cobertura">
        <dl className="nx-kpis">
          <div><dt>No inventário</dt><dd>{n(cob.inventario)}</dd></div>
          {Object.entries(cob.por_tipo).map(([k, v]) => <div key={k}><dt>{TIPO[k] ?? k}</dt><dd>{n(v)}</dd></div>)}
          <div><dt>Varridas por vulnerabilidade</dt><dd>{n(cob.maquinas_varridas)}</dd></div>
        </dl>
      </Panel>
    </Screen>
  );
}
