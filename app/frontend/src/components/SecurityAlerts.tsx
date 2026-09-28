import { useState, useEffect } from 'react';
import { ShieldAlert, X } from 'lucide-react';
import { useAuth } from '../hooks/useAuth';

const API_BASE = import.meta.env.VITE_API_URL ?? '';

interface AuditItem {
  check: string;
  status: 'secure' | 'warning' | 'danger' | 'unknown';
  message: string;
  details?: string[];
}

export default function SecurityAlerts() {
  const { authHeader } = useAuth();
  const [audits, setAudits] = useState<AuditItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [visible, setVisible] = useState(true);

  useEffect(() => {
    const fetchAudits = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/tenants/security-audit`, { credentials: 'include', headers: authHeader() });
        if (res.ok) {
          const data = await res.json();
          setAudits(data);
        }
      } catch (e) {
        console.error('Failed to fetch security audits', e);
      } finally {
        setLoading(false);
      }
    };
    fetchAudits();
  }, [authHeader]);

  const issues = audits.filter(a => a.status === 'warning' || a.status === 'danger');
  if (loading || issues.length === 0 || !visible) return null;

  return (
    <div className="mb-6 animate-slide-down">
      <div className="bg-red-500/10 border border-red-500/25 rounded-xl p-4 flex flex-col gap-3 relative overflow-hidden group">
        <div className="absolute top-0 right-0 p-2 opacity-40 hover:opacity-100 cursor-pointer transition-opacity" onClick={() => setVisible(false)}>
          <X size={14} className="text-white" />
        </div>
        
        <div className="flex items-start gap-4">
          <div className="p-2.5 rounded-lg bg-red-500/20 text-red-400">
            <ShieldAlert size={20} className="animate-pulse" />
          </div>
          <div className="flex-1">
            <h3 className="text-sm font-bold text-white flex items-center gap-2">
              Riscos Detectados no Ambiente Cloud
              <span className="px-2 py-0.5 rounded-full bg-red-500 text-[10px] font-bold uppercase tracking-wider text-white">Crítico</span>
            </h3>
            <p className="text-xs text-red-200/60 mt-1">
              Foram identificadas vulnerabilidades e desatualizações críticas na infraestrutura do Hub.Ness.
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-2 mt-1">
          {issues.map((issue, idx) => (
            <div key={idx} className="flex items-center gap-3 px-3 py-2 rounded-lg bg-black/20 border border-white/5">
              <div className={`w-1.5 h-1.5 rounded-full ${issue.status === 'danger' ? 'bg-red-500' : 'bg-orange-400'}`} />
              <div className="flex-1 min-w-0">
                <p className="text-[11px] font-bold text-white/90 truncate">{issue.check}</p>
                <p className="text-[10px] text-white/40 truncate">{issue.message}</p>
              </div>
            </div>
          ))}
        </div>
        
        <div className="mt-2 pt-2 border-t border-white/5 flex justify-between items-center">
            <p className="text-[10px] text-white/30 italic">Ambiente analisado em: {new Date().toLocaleDateString()}</p>
            <button className="text-[10px] font-bold text-red-400 hover:text-red-300 transition-colors uppercase tracking-wider">
              Ver Relatório Completo
            </button>
        </div>
      </div>
    </div>
  );
}
