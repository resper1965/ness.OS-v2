import {
  Activity, Bot, BriefcaseBusiness, Calculator, Check, ChevronDown,
  CircleDollarSign, Clock3, Copy, Cpu, Database, Download, Gauge,
  HardDrive, Info, Network, RotateCcw, Server, Shield, Sparkles,
  TriangleAlert, Users, Wifi,
} from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';

type AssetKey = 'endpoints' | 'servers' | 'firewalls' | 'switches' | 'accessPoints' |
  'cloudWorkloads' | 'criticalApps' | 'm365Tenants' | 'identities';

type Scenario = {
  name: string;
  assets: Record<AssetKey, number>;
  weights: Record<AssetKey, number>;
  commercial: {
    tenantBase: number;
    uamPrice: number;
    includedHumanHours: number;
    extraHourPrice: number;
  };
  rmm: {
    currentFleet: number;
    blockCapacity: number;
    blockCostUsd: number;
    usdBrl: number;
    safeOccupancy: number;
  };
  human: {
    governanceHours: number;
    platformHours: number;
    exceptionsPerMonth: number;
    minutesPerException: number;
    internalHourlyCost: number;
  };
  infrastructure: {
    sharedMonthlyCost: number;
    currentSharedUam: number;
    agenticCostPerUam: number;
    clientFixedCost: number;
  };
  pentest: {
    included: boolean;
    testsPerYear: number;
    internalCostPerTest: number;
    sellPricePerTest: number;
  };
  economics: {
    taxes: number;
    commission: number;
    contingency: number;
    targetMargin: number;
  };
  setup: {
    hours: number;
    variableCostPerEndpoint: number;
  };
};

const ASSETS: Array<{ key: AssetKey; label: string; hint: string; icon: typeof Server }> = [
  { key: 'endpoints', label: 'Endpoints e PDVs', hint: 'Desktop, notebook ou caixa', icon: HardDrive },
  { key: 'servers', label: 'Servidores e VMs', hint: 'Físico ou virtual', icon: Server },
  { key: 'firewalls', label: 'Firewalls / UTM', hint: 'Borda e filiais', icon: Shield },
  { key: 'switches', label: 'Switches e roteadores', hint: 'Rede gerenciável', icon: Network },
  { key: 'accessPoints', label: 'Access points', hint: 'Wi-Fi monitorado', icon: Wifi },
  { key: 'cloudWorkloads', label: 'Workloads em nuvem', hint: 'VM, container ou serviço', icon: Cpu },
  { key: 'criticalApps', label: 'Aplicações críticas', hint: 'ERP, e-commerce e APIs', icon: Activity },
  { key: 'm365Tenants', label: 'Tenants M365', hint: 'Entra ID e Microsoft 365', icon: Database },
  { key: 'identities', label: 'Identidades', hint: 'Usuários efetivamente monitorados', icon: Users },
];

const DEFAULT_SCENARIO: Scenario = {
  name: 'Supermercado Violeta',
  assets: {
    endpoints: 200, servers: 0, firewalls: 12, switches: 0, accessPoints: 0,
    cloudWorkloads: 0, criticalApps: 0, m365Tenants: 1, identities: 0,
  },
  weights: {
    endpoints: 1, servers: 3, firewalls: 5, switches: 1.5, accessPoints: 0.5,
    cloudWorkloads: 2, criticalApps: 3, m365Tenants: 10, identities: 0.1,
  },
  commercial: { tenantBase: 3000, uamPrice: 25, includedHumanHours: 8, extraHourPrice: 350 },
  rmm: { currentFleet: 1637, blockCapacity: 1000, blockCostUsd: 200, usdBrl: 6.5, safeOccupancy: 80 },
  human: { governanceHours: 2, platformHours: 2, exceptionsPerMonth: 4, minutesPerException: 45, internalHourlyCost: 180 },
  infrastructure: { sharedMonthlyCost: 4000, currentSharedUam: 1637, agenticCostPerUam: 2.5, clientFixedCost: 500 },
  pentest: { included: true, testsPerYear: 2, internalCostPerTest: 15000, sellPricePerTest: 25000 },
  economics: { taxes: 8, commission: 5, contingency: 10, targetMargin: 45 },
  setup: { hours: 40, variableCostPerEndpoint: 10 },
};

const STORAGE_KEY = 'ness_os_pricing_scenario_v1'; // gitleaks:allow -- public browser storage key

function loadScenario(): Scenario {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    return saved ? { ...DEFAULT_SCENARIO, ...JSON.parse(saved) } : DEFAULT_SCENARIO;
  } catch {
    return DEFAULT_SCENARIO;
  }
}

const brl = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL', maximumFractionDigits: 0 });
const number = new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 1 });
const pct = (value: number) => `${number.format(value)}%`;
const clamp = (value: number, min = 0, max = Number.POSITIVE_INFINITY) => Math.min(max, Math.max(min, value || 0));
const roundUp = (value: number, step = 100) => Math.ceil(value / step) * step;

function Field({ label, value, onChange, suffix, hint, min = 0, max, step = 1 }: {
  label: string; value: number; onChange: (value: number) => void; suffix?: string;
  hint?: string; min?: number; max?: number; step?: number;
}) {
  return (
    <label className="block group">
      <span className="flex items-center justify-between gap-2 text-[11px] font-semibold uppercase tracking-[0.11em] text-slate-500 mb-1.5">
        {label}
        {hint && <span title={hint}><Info size={12} className="text-slate-600 group-hover:text-cyan-400 transition-colors" /></span>}
      </span>
      <span className="flex items-center rounded-lg border border-white/[0.08] bg-black/20 focus-within:border-cyan-400/50 focus-within:ring-2 focus-within:ring-cyan-400/10 transition-all overflow-hidden">
        <input
          type="number"
          value={value}
          min={min}
          max={max}
          step={step}
          onChange={(event) => onChange(clamp(Number(event.currentTarget.value), min, max))}
          className="w-full bg-transparent px-3 py-2.5 text-sm font-semibold text-slate-100 tabular-nums outline-none"
        />
        {suffix && <span className="pr-3 text-[11px] font-semibold text-slate-500 whitespace-nowrap">{suffix}</span>}
      </span>
    </label>
  );
}

function Panel({ title, kicker, icon: Icon, children, accent = 'cyan' }: {
  title: string; kicker: string; icon: typeof Server; children: React.ReactNode; accent?: 'cyan' | 'amber' | 'emerald';
}) {
  const colors = {
    cyan: 'text-cyan-400 bg-cyan-400/10 border-cyan-400/15',
    amber: 'text-amber-400 bg-amber-400/10 border-amber-400/15',
    emerald: 'text-emerald-400 bg-emerald-400/10 border-emerald-400/15',
  }[accent];
  return (
    <section className="rounded-2xl border border-white/[0.07] bg-[#0c111b]/85 shadow-[0_22px_70px_rgba(0,0,0,0.24)] overflow-hidden">
      <div className="flex items-center gap-3 px-5 py-4 border-b border-white/[0.06]">
        <div className={`w-9 h-9 rounded-xl border flex items-center justify-center ${colors}`}><Icon size={17} /></div>
        <div>
          <p className="text-[10px] uppercase tracking-[0.18em] text-slate-600 font-bold">{kicker}</p>
          <h2 className="text-sm font-bold text-slate-100 mt-0.5">{title}</h2>
        </div>
      </div>
      <div className="p-5">{children}</div>
    </section>
  );
}

function Metric({ label, value, note, tone = 'default' }: {
  label: string; value: string; note?: string; tone?: 'default' | 'cyan' | 'emerald' | 'amber' | 'red';
}) {
  const toneClass = {
    default: 'text-white', cyan: 'text-cyan-300', emerald: 'text-emerald-300',
    amber: 'text-amber-300', red: 'text-red-300',
  }[tone];
  return (
    <div className="p-4 rounded-xl border border-white/[0.06] bg-white/[0.025]">
      <p className="text-[10px] uppercase tracking-[0.14em] text-slate-600 font-bold">{label}</p>
      <p className={`mt-2 text-xl font-bold tracking-tight tabular-nums ${toneClass}`}>{value}</p>
      {note && <p className="mt-1 text-[11px] leading-relaxed text-slate-500">{note}</p>}
    </div>
  );
}

export default function PricingModule() {
  const [scenario, setScenario] = useState<Scenario>(loadScenario);
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(scenario));
  }, [scenario]);

  const update = <S extends keyof Scenario>(section: S, key: keyof Scenario[S], value: number | string | boolean) => {
    setScenario((current) => ({
      ...current,
      [section]: { ...(current[section] as object), [key]: value },
    }));
  };

  const result = useMemo(() => {
    const uamRows = ASSETS.map((asset) => ({
      ...asset,
      quantity: scenario.assets[asset.key],
      weight: scenario.weights[asset.key],
      uam: scenario.assets[asset.key] * scenario.weights[asset.key],
    }));
    const totalUam = uamRows.reduce((sum, row) => sum + row.uam, 0);
    const endpointCount = scenario.assets.endpoints;

    const currentRmmBlocks = Math.ceil(scenario.rmm.currentFleet / scenario.rmm.blockCapacity);
    const projectedRmmBlocks = Math.ceil((scenario.rmm.currentFleet + endpointCount) / scenario.rmm.blockCapacity);
    const rmmBlockBrl = scenario.rmm.blockCostUsd * scenario.rmm.usdBrl;
    const rmmAllocatedCost = endpointCount * rmmBlockBrl /
      (scenario.rmm.blockCapacity * (scenario.rmm.safeOccupancy / 100));
    const rmmIncrementalCost = (projectedRmmBlocks - currentRmmBlocks) * rmmBlockBrl;
    const rmmSpareAfter = projectedRmmBlocks * scenario.rmm.blockCapacity - scenario.rmm.currentFleet - endpointCount;

    const exceptionHours = scenario.human.exceptionsPerMonth * scenario.human.minutesPerException / 60;
    const expectedHumanHours = scenario.human.governanceHours + scenario.human.platformHours + exceptionHours;
    const humanCost = expectedHumanHours * scenario.human.internalHourlyCost;
    const humanHeadroom = scenario.commercial.includedHumanHours - expectedHumanHours;

    const projectedSharedUam = scenario.infrastructure.currentSharedUam + totalUam;
    const sharedInfraAllocation = projectedSharedUam > 0
      ? scenario.infrastructure.sharedMonthlyCost * totalUam / projectedSharedUam : 0;
    const agenticCost = totalUam * scenario.infrastructure.agenticCostPerUam;
    const pentestMonthlyCost = scenario.pentest.included
      ? scenario.pentest.internalCostPerTest * scenario.pentest.testsPerYear / 12 : 0;
    const pentestMonthlyRevenue = scenario.pentest.included
      ? scenario.pentest.sellPricePerTest * scenario.pentest.testsPerYear / 12 : 0;

    const directOperatingCost = rmmAllocatedCost + sharedInfraAllocation + agenticCost + humanCost +
      scenario.infrastructure.clientFixedCost + pentestMonthlyCost;
    const contingencyCost = directOperatingCost * scenario.economics.contingency / 100;
    const totalCost = directOperatingCost + contingencyCost;

    const variableRate = (scenario.economics.taxes + scenario.economics.commission) / 100;
    const targetMarginRate = scenario.economics.targetMargin / 100;
    const denominator = Math.max(0.01, 1 - variableRate - targetMarginRate);
    const priceFloor = totalCost / denominator;
    const listPrice = scenario.commercial.tenantBase + totalUam * scenario.commercial.uamPrice + pentestMonthlyRevenue;
    const recommendedPrice = roundUp(Math.max(priceFloor, listPrice));
    const variableDeductions = recommendedPrice * variableRate;
    const contribution = recommendedPrice - variableDeductions - totalCost;
    const contributionMargin = recommendedPrice > 0 ? contribution / recommendedPrice * 100 : 0;

    const setupDirectCost = scenario.setup.hours * scenario.human.internalHourlyCost +
      endpointCount * scenario.setup.variableCostPerEndpoint;
    const setupCostWithContingency = setupDirectCost * (1 + scenario.economics.contingency / 100);
    const setupPrice = roundUp(setupCostWithContingency / denominator);

    return {
      uamRows, totalUam, endpointCount, currentRmmBlocks, projectedRmmBlocks, rmmBlockBrl,
      rmmAllocatedCost, rmmIncrementalCost, rmmSpareAfter, exceptionHours, expectedHumanHours,
      humanCost, humanHeadroom, sharedInfraAllocation, agenticCost, pentestMonthlyCost,
      pentestMonthlyRevenue, directOperatingCost, contingencyCost, totalCost, priceFloor,
      listPrice, recommendedPrice, variableDeductions, contribution, contributionMargin,
      setupDirectCost, setupPrice,
    };
  }, [scenario]);

  const summary = [
    `CENÁRIO: ${scenario.name}`,
    `ESCOPO: ${number.format(result.totalUam)} UAM | ${result.endpointCount} endpoints com RMM`,
    `MENSALIDADE RECOMENDADA: ${brl.format(result.recommendedPrice)}`,
    `SETUP RECOMENDADO: ${brl.format(result.setupPrice)}`,
    `SUPERVISÃO HUMANA: até ${number.format(scenario.commercial.includedHumanHours)} h/mês; excedente ${brl.format(scenario.commercial.extraHourPrice)}/h`,
    `MARGEM ESTIMADA: ${pct(result.contributionMargin)}`,
    `MODELO: operação agentic contínua 24x7; GLPI interno; atendimento cotidiano ao usuário não incluído.`,
  ].join('\n');

  const copySummary = async () => {
    await navigator.clipboard.writeText(summary);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1800);
  };

  const exportScenario = () => {
    const blob = new Blob([JSON.stringify({ scenario, result, generatedAt: new Date().toISOString() }, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `precificacao-${scenario.name.toLowerCase().replace(/[^a-z0-9]+/g, '-') || 'ness-os'}.json`;
    link.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="min-h-full bg-[#070b12] relative overflow-hidden">
      <div className="absolute inset-0 pointer-events-none opacity-50" style={{
        backgroundImage: 'linear-gradient(rgba(0,173,232,.035) 1px, transparent 1px), linear-gradient(90deg, rgba(0,173,232,.035) 1px, transparent 1px)',
        backgroundSize: '32px 32px',
        maskImage: 'linear-gradient(to bottom, black, transparent 72%)',
      }} />
      <div className="absolute -top-40 right-[-8rem] w-[34rem] h-[34rem] rounded-full bg-cyan-500/[0.07] blur-[100px] pointer-events-none" />

      <div className="relative max-w-[1500px] mx-auto px-6 lg:px-8 py-7 animate-fade-in">
        <div className="flex flex-col xl:flex-row xl:items-end justify-between gap-5 mb-7">
          <div>
            <div className="flex items-center gap-2 text-cyan-400 mb-2">
              <Calculator size={15} />
              <span className="text-[10px] font-bold uppercase tracking-[0.2em]">Pricing control room</span>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <input
                value={scenario.name}
                onChange={(event) => setScenario((current) => ({ ...current, name: event.currentTarget.value }))}
                aria-label="Nome do cenário"
                className="bg-transparent text-2xl lg:text-3xl font-bold tracking-[-0.035em] text-white outline-none border-b border-transparent focus:border-cyan-400/50 min-w-0 max-w-full"
              />
              <span className="px-2.5 py-1 rounded-full border border-emerald-400/20 bg-emerald-400/[0.08] text-[10px] uppercase tracking-wider font-bold text-emerald-300">
                agentic 24x7
              </span>
            </div>
            <p className="mt-2 text-sm text-slate-500 max-w-2xl">
              Precificação por capacidade, risco e economia real. Humanos entram como supervisão de exceções — não como escala operacional.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button onClick={copySummary} className="flex items-center gap-2 px-3.5 py-2.5 rounded-xl border border-white/[0.08] bg-white/[0.03] text-xs font-semibold text-slate-300 hover:text-white hover:border-white/15 transition-all">
              {copied ? <Check size={14} className="text-emerald-400" /> : <Copy size={14} />}{copied ? 'Copiado' : 'Copiar resumo'}
            </button>
            <button onClick={exportScenario} className="flex items-center gap-2 px-3.5 py-2.5 rounded-xl border border-cyan-400/20 bg-cyan-400/[0.08] text-xs font-semibold text-cyan-300 hover:bg-cyan-400/[0.13] transition-all">
              <Download size={14} /> Exportar
            </button>
            <button onClick={() => setScenario(DEFAULT_SCENARIO)} title="Restaurar premissas" aria-label="Restaurar premissas" className="p-2.5 rounded-xl border border-white/[0.08] text-slate-500 hover:text-white hover:bg-white/[0.04] transition-all">
              <RotateCcw size={14} />
            </button>
          </div>
        </div>

        <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1.42fr)_minmax(340px,.58fr)] gap-6 items-start">
          <div className="space-y-6">
            <Panel title="Inventário e pesos UAM" kicker="01 · Escopo comercial" icon={Gauge}>
              <div className="grid grid-cols-[minmax(170px,1fr)_92px_82px_90px] gap-2 px-2 pb-2 text-[9px] uppercase tracking-[0.15em] text-slate-600 font-bold">
                <span>Ativo</span><span className="text-right">Qtd.</span><span className="text-right">Peso</span><span className="text-right">UAM</span>
              </div>
              <div className="divide-y divide-white/[0.05]">
                {result.uamRows.map((row) => {
                  const Icon = row.icon;
                  return (
                    <div key={row.key} className="grid grid-cols-[minmax(170px,1fr)_92px_82px_90px] gap-2 items-center py-2.5 px-2 hover:bg-white/[0.02] rounded-lg transition-colors">
                      <div className="flex items-center gap-3 min-w-0">
                        <span className="w-8 h-8 rounded-lg bg-white/[0.035] border border-white/[0.06] flex items-center justify-center text-slate-500 shrink-0"><Icon size={14} /></span>
                        <span className="min-w-0"><strong className="block text-xs text-slate-200 truncate">{row.label}</strong><small className="block text-[10px] text-slate-600 truncate mt-0.5">{row.hint}</small></span>
                      </div>
                      <input type="number" min="0" value={row.quantity} onChange={(event) => update('assets', row.key, clamp(Number(event.currentTarget.value)))} className="w-full rounded-lg border border-white/[0.07] bg-black/20 px-2.5 py-2 text-right text-xs font-bold text-white tabular-nums outline-none focus:border-cyan-400/40" />
                      <input type="number" min="0" step="0.1" value={row.weight} onChange={(event) => update('weights', row.key, clamp(Number(event.currentTarget.value)))} className="w-full rounded-lg border border-white/[0.07] bg-black/20 px-2.5 py-2 text-right text-xs font-bold text-slate-400 tabular-nums outline-none focus:border-cyan-400/40" />
                      <span className="text-right text-sm font-bold text-cyan-300 tabular-nums">{number.format(row.uam)}</span>
                    </div>
                  );
                })}
              </div>
              <div className="mt-3 pt-4 border-t border-cyan-400/15 flex justify-between items-center">
                <span className="text-xs font-bold uppercase tracking-[0.12em] text-slate-500">Carga total ponderada</span>
                <span className="text-2xl font-bold text-white tabular-nums">{number.format(result.totalUam)} <small className="text-xs text-cyan-400">UAM</small></span>
              </div>
            </Panel>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <Panel title="Capacidade RMM compartilhada" kicker="02 · Atera próprio" icon={Database} accent="emerald">
                <div className="grid grid-cols-2 gap-3">
                  <Field label="Frota atual" value={scenario.rmm.currentFleet} onChange={(v) => update('rmm', 'currentFleet', v)} suffix="ativos" />
                  <Field label="Capacidade/bloco" value={scenario.rmm.blockCapacity} onChange={(v) => update('rmm', 'blockCapacity', v)} suffix="ativos" />
                  <Field label="Custo do bloco" value={scenario.rmm.blockCostUsd} onChange={(v) => update('rmm', 'blockCostUsd', v)} suffix="US$/mês" />
                  <Field label="Câmbio" value={scenario.rmm.usdBrl} onChange={(v) => update('rmm', 'usdBrl', v)} suffix="R$/US$" step={0.1} />
                  <Field label="Ocupação segura" value={scenario.rmm.safeOccupancy} onChange={(v) => update('rmm', 'safeOccupancy', v)} suffix="%" max={100} />
                  <div className="rounded-lg border border-white/[0.06] bg-white/[0.025] px-3 py-2.5">
                    <span className="text-[10px] uppercase tracking-wider font-bold text-slate-600">Blocos após venda</span>
                    <p className="text-lg font-bold text-emerald-300 mt-1 tabular-nums">{result.projectedRmmBlocks} <small className="text-[10px] text-slate-500">× {brl.format(result.rmmBlockBrl)}</small></p>
                  </div>
                </div>
                <div className="mt-4 grid grid-cols-2 gap-2">
                  <Metric label="Custo econômico alocado" value={brl.format(result.rmmAllocatedCost)} note="Usa ocupação segura, mesmo sem novo desembolso." />
                  <Metric label="Custo marginal imediato" value={brl.format(result.rmmIncrementalCost)} note={`${number.format(result.rmmSpareAfter)} vagas permanecem livres.`} tone={result.rmmIncrementalCost > 0 ? 'amber' : 'emerald'} />
                </div>
              </Panel>

              <Panel title="Supervisão humana" kicker="03 · Exceções e governança" icon={Users} accent="amber">
                <div className="grid grid-cols-2 gap-3">
                  <Field label="Governança" value={scenario.human.governanceHours} onChange={(v) => update('human', 'governanceHours', v)} suffix="h/mês" step={0.5} />
                  <Field label="Operação da plataforma" value={scenario.human.platformHours} onChange={(v) => update('human', 'platformHours', v)} suffix="h/mês" step={0.5} />
                  <Field label="Exceções esperadas" value={scenario.human.exceptionsPerMonth} onChange={(v) => update('human', 'exceptionsPerMonth', v)} suffix="casos/mês" />
                  <Field label="Tempo por exceção" value={scenario.human.minutesPerException} onChange={(v) => update('human', 'minutesPerException', v)} suffix="min" step={5} />
                  <Field label="Custo interno" value={scenario.human.internalHourlyCost} onChange={(v) => update('human', 'internalHourlyCost', v)} suffix="R$/h" />
                  <Field label="Franquia contratual" value={scenario.commercial.includedHumanHours} onChange={(v) => update('commercial', 'includedHumanHours', v)} suffix="h/mês" step={0.5} />
                </div>
                <div className={`mt-4 rounded-xl border p-3.5 flex items-start gap-3 ${result.humanHeadroom >= 0 ? 'border-emerald-400/15 bg-emerald-400/[0.05]' : 'border-red-400/20 bg-red-400/[0.06]'}`}>
                  {result.humanHeadroom >= 0 ? <Bot size={17} className="text-emerald-400 mt-0.5" /> : <TriangleAlert size={17} className="text-red-400 mt-0.5" />}
                  <div><p className="text-xs font-bold text-slate-200">{number.format(result.expectedHumanHours)} h humanas esperadas</p><p className="text-[11px] text-slate-500 mt-1">{result.humanHeadroom >= 0 ? `${number.format(result.humanHeadroom)} h de folga dentro da franquia.` : `${number.format(Math.abs(result.humanHeadroom))} h acima da franquia; revise automação ou preço.`}</p></div>
                </div>
              </Panel>
            </div>

            <button onClick={() => setAdvancedOpen((open) => !open)} className="w-full flex items-center justify-between rounded-2xl border border-white/[0.07] bg-white/[0.025] px-5 py-4 text-left hover:bg-white/[0.04] transition-all">
              <span><strong className="block text-sm text-slate-200">Premissas financeiras avançadas</strong><small className="block text-[11px] text-slate-600 mt-1">Infra compartilhada, pentest, tributos, margem e setup</small></span>
              <ChevronDown size={16} className={`text-slate-500 transition-transform ${advancedOpen ? 'rotate-180' : ''}`} />
            </button>

            {advancedOpen && (
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 animate-fade-in">
                <Panel title="Infraestrutura e automação" kicker="04 · Custo produtivo" icon={Cpu}>
                  <div className="grid grid-cols-2 gap-3">
                    <Field label="Infra compartilhada" value={scenario.infrastructure.sharedMonthlyCost} onChange={(v) => update('infrastructure', 'sharedMonthlyCost', v)} suffix="R$/mês" />
                    <Field label="UAM atual da plataforma" value={scenario.infrastructure.currentSharedUam} onChange={(v) => update('infrastructure', 'currentSharedUam', v)} suffix="UAM" />
                    <Field label="Compute agentic" value={scenario.infrastructure.agenticCostPerUam} onChange={(v) => update('infrastructure', 'agenticCostPerUam', v)} suffix="R$/UAM" step={0.1} />
                    <Field label="Custo fixo do cliente" value={scenario.infrastructure.clientFixedCost} onChange={(v) => update('infrastructure', 'clientFixedCost', v)} suffix="R$/mês" />
                  </div>
                </Panel>

                <Panel title="Pentest recorrente" kicker="05 · Serviço periódico" icon={Shield} accent="amber">
                  <label className="flex items-center justify-between p-3 rounded-xl border border-white/[0.07] bg-white/[0.025] mb-3 cursor-pointer">
                    <span><strong className="block text-xs text-slate-200">Incluir na mensalidade</strong><small className="text-[10px] text-slate-600">Provisiona custo e receita ao longo do ano</small></span>
                    <input type="checkbox" checked={scenario.pentest.included} onChange={(e) => update('pentest', 'included', e.currentTarget.checked)} className="accent-cyan-400 w-4 h-4" />
                  </label>
                  <div className="grid grid-cols-2 gap-3">
                    <Field label="Testes por ano" value={scenario.pentest.testsPerYear} onChange={(v) => update('pentest', 'testsPerYear', v)} suffix="testes" />
                    <Field label="Custo por teste" value={scenario.pentest.internalCostPerTest} onChange={(v) => update('pentest', 'internalCostPerTest', v)} suffix="R$" />
                    <Field label="Venda por teste" value={scenario.pentest.sellPricePerTest} onChange={(v) => update('pentest', 'sellPricePerTest', v)} suffix="R$" />
                  </div>
                </Panel>

                <Panel title="Formação do preço" kicker="06 · Economia unitária" icon={CircleDollarSign} accent="emerald">
                  <div className="grid grid-cols-2 gap-3">
                    <Field label="Base do tenant" value={scenario.commercial.tenantBase} onChange={(v) => update('commercial', 'tenantBase', v)} suffix="R$/mês" />
                    <Field label="Preço por UAM" value={scenario.commercial.uamPrice} onChange={(v) => update('commercial', 'uamPrice', v)} suffix="R$/mês" />
                    <Field label="Hora excedente" value={scenario.commercial.extraHourPrice} onChange={(v) => update('commercial', 'extraHourPrice', v)} suffix="R$/h" />
                    <Field label="Impostos" value={scenario.economics.taxes} onChange={(v) => update('economics', 'taxes', v)} suffix="%" max={100} step={0.5} />
                    <Field label="Comissão" value={scenario.economics.commission} onChange={(v) => update('economics', 'commission', v)} suffix="%" max={100} step={0.5} />
                    <Field label="Contingência" value={scenario.economics.contingency} onChange={(v) => update('economics', 'contingency', v)} suffix="%" max={100} step={0.5} />
                    <Field label="Margem-alvo" value={scenario.economics.targetMargin} onChange={(v) => update('economics', 'targetMargin', v)} suffix="%" max={90} step={0.5} />
                  </div>
                </Panel>

                <Panel title="Onboarding e setup" kicker="07 · Receita não recorrente" icon={BriefcaseBusiness}>
                  <div className="grid grid-cols-2 gap-3">
                    <Field label="Horas de implantação" value={scenario.setup.hours} onChange={(v) => update('setup', 'hours', v)} suffix="h" />
                    <Field label="Custo por endpoint" value={scenario.setup.variableCostPerEndpoint} onChange={(v) => update('setup', 'variableCostPerEndpoint', v)} suffix="R$/ativo" />
                  </div>
                  <div className="mt-4 grid grid-cols-2 gap-2">
                    <Metric label="Custo direto" value={brl.format(result.setupDirectCost)} />
                    <Metric label="Preço recomendado" value={brl.format(result.setupPrice)} tone="cyan" />
                  </div>
                </Panel>
              </div>
            )}
          </div>

          <aside className="xl:sticky xl:top-6 space-y-4">
            <div className="rounded-3xl border border-cyan-400/20 bg-gradient-to-br from-[#10202b] via-[#0c151e] to-[#090e15] p-5 shadow-[0_30px_90px_rgba(0,0,0,.4),0_0_50px_rgba(0,173,232,.06)] overflow-hidden relative">
              <div className="absolute -top-10 -right-10 w-36 h-36 rounded-full border border-cyan-400/10" />
              <div className="absolute -top-4 -right-4 w-24 h-24 rounded-full border border-cyan-400/10" />
              <div className="relative">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] uppercase tracking-[0.18em] font-bold text-cyan-400">Preço recomendado</span>
                  <Sparkles size={15} className="text-cyan-400" />
                </div>
                <p className="mt-3 text-4xl font-bold tracking-[-0.05em] text-white tabular-nums">{brl.format(result.recommendedPrice)}</p>
                <p className="text-xs text-slate-500 mt-1">por mês · impostos incluídos no cálculo</p>

                <div className="mt-5 grid grid-cols-2 gap-2">
                  <Metric label="Setup" value={brl.format(result.setupPrice)} tone="cyan" />
                  <Metric label="Margem estimada" value={pct(result.contributionMargin)} tone={result.contributionMargin >= scenario.economics.targetMargin ? 'emerald' : 'amber'} />
                  <Metric label="Preço de tabela" value={brl.format(result.listPrice)} note="Base + UAM + pentest" />
                  <Metric label="Piso econômico" value={brl.format(result.priceFloor)} note="Custo, tributos e margem" />
                </div>

                <div className="mt-5 pt-4 border-t border-white/[0.08] space-y-2.5 text-xs">
                  <div className="flex justify-between"><span className="text-slate-500">Receita líquida variável</span><strong className="text-slate-300">{brl.format(result.recommendedPrice - result.variableDeductions)}</strong></div>
                  <div className="flex justify-between"><span className="text-slate-500">Custo mensal total</span><strong className="text-slate-300">{brl.format(result.totalCost)}</strong></div>
                  <div className="flex justify-between"><span className="text-slate-500">Contribuição mensal</span><strong className="text-emerald-300">{brl.format(result.contribution)}</strong></div>
                  <div className="flex justify-between"><span className="text-slate-500">ARR projetado</span><strong className="text-white">{brl.format(result.recommendedPrice * 12)}</strong></div>
                </div>
              </div>
            </div>

            <div className="rounded-2xl border border-white/[0.07] bg-[#0c111b]/90 p-5">
              <div className="flex items-center gap-2 mb-4"><Calculator size={14} className="text-slate-500" /><h3 className="text-xs font-bold uppercase tracking-[0.13em] text-slate-400">Memória mensal de custo</h3></div>
              <div className="space-y-3 text-xs">
                {[
                  ['RMM alocado', result.rmmAllocatedCost],
                  ['Infra compartilhada', result.sharedInfraAllocation],
                  ['Compute agentic', result.agenticCost],
                  ['Supervisão humana', result.humanCost],
                  ['Custo fixo do tenant', scenario.infrastructure.clientFixedCost],
                  ['Pentest provisionado', result.pentestMonthlyCost],
                  ['Contingência', result.contingencyCost],
                ].map(([label, value]) => (
                  <div key={String(label)} className="flex justify-between gap-4"><span className="text-slate-500">{label}</span><strong className="text-slate-300 tabular-nums">{brl.format(Number(value))}</strong></div>
                ))}
              </div>
              <div className="mt-4 pt-4 border-t border-white/[0.07] flex justify-between"><span className="text-xs font-bold text-slate-300">Total</span><strong className="text-sm text-white">{brl.format(result.totalCost)}</strong></div>
            </div>

            <div className={`rounded-2xl border p-4 ${result.humanHeadroom >= 0 ? 'border-emerald-400/15 bg-emerald-400/[0.045]' : 'border-red-400/20 bg-red-400/[0.05]'}`}>
              <div className="flex gap-3">
                <Clock3 size={16} className={result.humanHeadroom >= 0 ? 'text-emerald-400' : 'text-red-400'} />
                <div><p className="text-xs font-bold text-slate-200">Fator humano sob controle</p><p className="text-[11px] leading-relaxed text-slate-500 mt-1">GLPI registra incidentes e evidências da operação regulada. Não há Help Desk cotidiano para o cliente.</p></div>
              </div>
            </div>
          </aside>
        </div>
      </div>
    </div>
  );
}
