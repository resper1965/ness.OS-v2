import { useState, useEffect, useCallback } from 'react';
import { 
  Server, HardDrive, RefreshCw, AlertTriangle, 
  Search,
  Shield, Network, Cpu, Database,
  Camera, Globe, ShieldAlert
} from 'lucide-react';
import { useAuth } from '../hooks/useAuth';

const API_BASE = import.meta.env.VITE_API_URL ?? '';

type Tab = 'compute' | 'snapshots' | 'storage' | 'networks' | 'firewall';
type HealthAlert = { type: 'danger'; title: string; message: string; icon: typeof AlertTriangle };

export default function CloudManagement({ selectedTenant }: { selectedTenant: string | null }) {
  const { authHeader } = useAuth();
  const [activeTab, setActiveTab] = useState<Tab>('compute');
  const [summary, setSummary] = useState<any>(null);
  const [instances, setInstances] = useState<any[]>([]);
  const [storage, setStorage] = useState<any[]>([]);
  const [firewalls, setFirewalls] = useState<any[]>([]);
  const [networks, setNetworks] = useState<any[]>([]);
  const [healthAlerts, setHealthAlerts] = useState<HealthAlert[]>([]);
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState('');
  
  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const query = selectedTenant ? `?customer_id=${selectedTenant}` : '';
      const res = await fetch(`${API_BASE}/api/contabo/dashboard-full${query}`, { headers: authHeader() });
      if (res.ok) {
        const data = await res.json();
        setSummary(data.summary);
        setStorage(data.storage);
        setFirewalls(data.firewalls);
        setNetworks(data.networks);
        
        const instData = data.instances;
        setInstances(instData);
        
        const alerts: HealthAlert[] = [];
        instData.forEach((inst: any) => {
          if (inst.status === 'running') {
            if (inst.imageId && (inst.imageId.includes('ubuntu-18') || inst.imageId.includes('debian-9'))) {
              alerts.push({
                type: 'danger',
                title: 'OS Obsoleto Detectado',
                message: `A instância ${inst.displayName} está rodando uma imagem com fim de vida (EOL).`,
                icon: AlertTriangle
              });
            }
          }
        });
        setHealthAlerts(alerts);
      }

    } catch (e) {
      console.error('Failed to fetch cloud data', e);
    } finally {
      setLoading(false);
    }
  }, [authHeader, selectedTenant]);

  useEffect(() => {
    fetchData();
  }, [fetchData, selectedTenant]);

  const filteredInstances = instances.filter(i => 
    i.displayName.toLowerCase().includes(search.toLowerCase()) ||
    i.ipConfig?.v4?.ip.includes(search)
  );

  return (
    <div className="space-y-6 animate-fade-in">
      
      {/* ── Health Alerts (Risk Analysis) ── */}
      {healthAlerts.length > 0 && (
        <div className="space-y-3">
          {healthAlerts.map((alert, idx) => (
            <div key={idx} className={`
              flex items-center gap-4 p-4 rounded-xl border animate-slide-left
              ${alert.type === 'danger' ? 'bg-red-500/10 border-red-500/20 text-red-400' : 'bg-orange-500/10 border-orange-500/20 text-orange-400'}
            `}>
              <alert.icon size={20} />
              <div className="flex-1">
                <p className="text-sm font-bold">{alert.title}</p>
                <p className="text-xs opacity-80">{alert.message}</p>
              </div>
              <button className="text-[10px] uppercase font-bold tracking-widest px-3 py-1 rounded bg-white/5 hover:bg-white/10 transition-all">
                Corrigir Agora
              </button>
            </div>
          ))}
        </div>
      )}

      {/* ── Summary Header ── */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="glass rounded-xl p-4 flex items-center gap-4">
          <div className="p-3 rounded-lg bg-[var(--color-brand-primary-dim)] text-[var(--color-brand-primary)]">
            <Server size={20} />
          </div>
          <div>
            <p className="text-[10px] uppercase tracking-wider text-[var(--color-brand-muted)] font-bold">Instâncias</p>
            <p className="text-xl font-bold text-white">{summary?.instances?.total ?? '—'}</p>
          </div>
        </div>

        <div className="glass rounded-xl p-4 flex items-center gap-4">
          <div className="p-3 rounded-lg bg-emerald-500/10 text-emerald-400">
            <Database size={20} />
          </div>
          <div>
            <p className="text-[10px] uppercase tracking-wider text-[var(--color-brand-muted)] font-bold">Storage</p>
            <p className="text-xl font-bold text-white">{summary?.storage?.total_tb ?? 0} TB</p>
          </div>
        </div>

        <div className="glass rounded-xl p-4 flex items-center gap-4">
          <div className="p-3 rounded-lg bg-orange-500/10 text-orange-400">
            <Network size={20} />
          </div>
          <div>
            <p className="text-[10px] uppercase tracking-wider text-[var(--color-brand-muted)] font-bold">VPC Redes</p>
            <p className="text-xl font-bold text-white">{networks.length}</p>
          </div>
        </div>

        <div className="glass rounded-xl p-4 flex items-center gap-4">
          <div className="p-3 rounded-lg bg-blue-500/10 text-blue-400">
            <Shield size={20} />
          </div>
          <div>
            <p className="text-[10px] uppercase tracking-wider text-[var(--color-brand-muted)] font-bold">Firewalls</p>
            <p className="text-xl font-bold text-white">{firewalls.length}</p>
          </div>
        </div>
      </div>

      {/* ── Tabs Navigation ── */}
      <div className="flex items-center justify-between border-b border-white/[0.04] px-1 overflow-x-auto no-scrollbar">
        <div className="flex gap-6 min-w-max">
          {[
            { id: 'compute', label: 'Instâncias', icon: Server },
            { id: 'snapshots', label: 'Snapshots', icon: Camera },
            { id: 'storage', label: 'Storage', icon: HardDrive },
            { id: 'networks', label: 'Redes VPC', icon: Globe },
            { id: 'firewall', label: 'Segurança', icon: ShieldAlert },
          ].map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as Tab)}
              className={`
                flex items-center gap-2 py-4 text-sm font-medium transition-all relative
                ${activeTab === tab.id ? 'text-[var(--color-brand-primary)]' : 'text-[var(--color-brand-muted)] hover:text-white'}
              `}
            >
              <tab.icon size={16} />
              {tab.label}
              {activeTab === tab.id && (
                <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-[var(--color-brand-primary)] glow-primary rounded-t-full" />
              )}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-3 mb-2 ml-4">
          <div className="relative group hidden md:block">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--color-brand-muted)] group-focus-within:text-[var(--color-brand-primary)] transition-colors" />
            <input 
              type="text" 
              placeholder="Buscar..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="bg-white/[0.03] border border-white/[0.06] rounded-lg py-1.5 pl-9 pr-4 text-xs text-white placeholder:text-white/20 focus:outline-none focus:border-[var(--color-brand-primary)]/40 focus:bg-white/[0.05] transition-all w-48 focus:w-64"
            />
          </div>
          <button onClick={fetchData} className="p-1.5 rounded-lg bg-white/[0.03] border border-white/[0.06] text-[var(--color-brand-muted)] hover:text-white transition-all">
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
          </button>
        </div>
      </div>

      {/* ── Tab Content ── */}
      <div className="min-h-[400px]">
        {activeTab === 'compute' && (
          <div className="grid grid-cols-1 gap-4">
            {filteredInstances.map(instance => (
              <div key={instance.instanceId} className="glass rounded-2xl p-5 hover:border-white/[0.12] transition-all group relative overflow-hidden">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-5">
                    <div className={`w-12 h-12 rounded-xl flex items-center justify-center border ${instance.status === 'running' ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400' : 'bg-white/5 border-white/10 text-white/30'}`}>
                      <Cpu size={24} />
                    </div>
                    <div>
                      <div className="flex items-center gap-3">
                        <h3 className="font-bold text-white text-lg">{instance.displayName}</h3>
                        <span className={`text-[10px] font-bold uppercase tracking-widest px-2 py-0.5 rounded-md border ${instance.status === 'running' ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400' : 'bg-white/5 border-white/10 text-white/40'}`}>{instance.status}</span>
                      </div>
                      <div className="flex items-center gap-4 mt-1 text-xs text-[var(--color-brand-muted)]">
                        <span className="flex items-center gap-1"><Network size={12}/> {instance.ipConfig?.v4?.ip}</span>
                        <span className="flex items-center gap-1"><Globe size={12}/> {instance.region}</span>
                      </div>
                    </div>
                  </div>
                  <div className="flex flex-col items-end gap-3">
                    <div className="flex items-center gap-4">
                      <div className="text-right"><p className="text-[10px] font-bold text-[var(--color-brand-muted)] uppercase">vCPU/RAM</p><p className="text-xs font-semibold text-white">{instance.vCpu} / {instance.ramMb/1024}GB</p></div>
                      <div className="text-right"><p className="text-[10px] font-bold text-[var(--color-brand-muted)] uppercase">Disco</p><p className="text-xs font-semibold text-white">{instance.diskMb/1024}GB</p></div>
                    </div>
                    <span className="text-[10px] font-bold uppercase tracking-widest text-[var(--color-brand-muted)]">Somente leitura</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {activeTab === 'firewall' && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="md:col-span-2 flex justify-between items-center mb-2">
              <h2 className="text-lg font-bold text-white">Firewalls Ativos</h2>
              <span className="text-[10px] font-bold uppercase tracking-widest text-[var(--color-brand-muted)]">Somente leitura</span>
            </div>
            {firewalls.length === 0 ? (
              <div className="md:col-span-2 py-20 glass rounded-2xl flex flex-col items-center justify-center opacity-40">
                <ShieldAlert size={48} className="mb-4" />
                <p>Nenhum firewall configurado via API.</p>
              </div>
            ) : firewalls.map(fw => (
              <div key={fw.firewallId} className="glass rounded-2xl p-6 hover:border-[var(--color-brand-primary)]/30 transition-all">
                <div className="flex justify-between items-start mb-6">
                  <div className="p-3 rounded-xl bg-blue-500/10 text-blue-400"><Shield size={24}/></div>
                  <span className="text-[10px] font-bold px-2 py-1 bg-white/5 rounded border border-white/10">{fw.status}</span>
                </div>
                <h3 className="text-xl font-bold text-white mb-2">{fw.displayName}</h3>
                <div className="space-y-2 mb-6">
                  <div className="flex justify-between text-xs text-[var(--color-brand-muted)]"><span>Instâncias</span><span className="text-white font-mono">{fw.instanceIds?.length || 0}</span></div>
                  <div className="flex justify-between text-xs text-[var(--color-brand-muted)]"><span>Regras Inbound</span><span className="text-white font-mono">{fw.rules?.inbound?.length || 0}</span></div>
                </div>
              </div>
            ))}
          </div>
        )}

        {activeTab === 'networks' && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {networks.map(net => (
              <div key={net.privateNetworkId} className="glass rounded-2xl p-6">
                <div className="flex items-center gap-4 mb-6">
                  <div className="p-3 rounded-xl bg-orange-500/10 text-orange-400"><Globe size={24}/></div>
                  <div>
                    <h3 className="text-lg font-bold text-white">{net.name || 'Private Network'}</h3>
                    <p className="text-xs text-[var(--color-brand-muted)]">{net.regionName}</p>
                  </div>
                </div>
                <div className="p-4 bg-white/[0.03] rounded-xl border border-white/[0.05] space-y-3">
                  <div className="flex justify-between text-xs">
                    <span className="text-[var(--color-brand-muted)]">Network ID</span>
                    <span className="text-white font-mono">{net.privateNetworkId}</span>
                  </div>
                  <div className="flex justify-between text-xs">
                    <span className="text-[var(--color-brand-muted)]">Instâncias Conectadas</span>
                    <span className="text-white font-bold">{net.instanceIds?.length || 0}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {activeTab === 'snapshots' && (
          <div className="grid grid-cols-1 gap-4">
            <div className="py-20 glass rounded-2xl flex flex-col items-center justify-center opacity-40">
              <Camera size={48} className="mb-4" />
              <p>Selecione uma instância para gerenciar snapshots.</p>
            </div>
          </div>
        )}

        {activeTab === 'storage' && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {storage.map(bucket => (
              <div key={bucket.tenantId} className="glass rounded-2xl p-6 relative overflow-hidden group">
                <div className="flex items-start justify-between mb-6">
                  <div>
                    <h3 className="text-xl font-bold text-white mb-1">Object Storage</h3>
                    <p className="text-xs text-[var(--color-brand-muted)] font-mono">{bucket.tenantId}</p>
                  </div>
                  <span className="px-2 py-1 rounded bg-emerald-500/10 text-emerald-400 text-[10px] font-bold uppercase tracking-widest border border-emerald-500/20">{bucket.status}</span>
                </div>
                <div className="space-y-4">
                  <div>
                    <div className="flex justify-between text-xs mb-1.5"><span className="text-[var(--color-brand-muted)]">Uso</span><span className="text-white font-bold">0% de {bucket.totalSpaceTb} TB</span></div>
                    <div className="h-1.5 w-full bg-white/5 rounded-full overflow-hidden"><div className="h-full bg-[var(--color-brand-primary)] w-[2%] rounded-full" /></div>
                  </div>
                  <div className="bg-white/5 rounded-xl p-3 border border-white/[0.03]">
                    <p className="text-[10px] uppercase font-bold text-[var(--color-brand-muted)] mb-1">S3 Endpoint</p>
                    <p className="text-xs font-mono text-white/90 truncate">{bucket.s3Url}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
