import { useState, useEffect } from 'react';
import { Users, ChevronDown, Check, Building2 } from 'lucide-react';
import { useAuth } from '../hooks/useAuth';

const API_BASE = import.meta.env.VITE_API_URL ?? '';

interface Tenant {
  id: string;
  name: string;
}

interface Props {
  selectedTenant: string | null;
  onSelect: (tenantId: string | null) => void;
}

export default function TenantSelector({ selectedTenant, onSelect }: Props) {
  const { authHeader } = useAuth();
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [isOpen, setIsOpen] = useState(false);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const fetchTenants = async () => {
      setLoading(true);
      try {
        const res = await fetch(`${API_BASE}/api/tenants/list`, { credentials: 'include', headers: authHeader() });
        if (res.ok) {
          const data = await res.json();
          setTenants(data);
        }
      } catch (e) {
        console.error('Failed to fetch tenants', e);
      } finally {
        setLoading(false);
      }
    };
    fetchTenants();
  }, [authHeader]);

  const currentTenant = tenants.find(t => t.id === selectedTenant);

  return (
    <div className="relative">
      <button
        onClick={() => setIsOpen(!isOpen)}
        disabled={loading}
        aria-haspopup="listbox"
        aria-expanded={isOpen}
        className="w-full flex items-center gap-3 px-3 py-2 bg-brand-surface border border-brand-border hover:border-brand-primary transition-colors"
      >
        <div className="p-2 text-brand-primary">
          <Building2 size={16} strokeWidth={1.5} />
        </div>
        <div className="flex-1 text-left">
          <p className="font-mono text-[10px] text-brand-muted uppercase tracking-[0.12em]">Contexto</p>
          <p className="text-sm font-semibold text-brand-text truncate">
            {loading ? 'Carregando…' : currentTenant ? currentTenant.name : 'Todos os clientes'}
          </p>
        </div>
        <ChevronDown size={14} className={`text-brand-muted ${isOpen ? 'rotate-180' : ''}`} />
      </button>

      {isOpen && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setIsOpen(false)} />
          <div className="absolute top-full left-0 right-0 mt-2 z-50 bg-brand-surface border border-brand-border shadow-lg py-2 overflow-hidden animate-fade-in">
            <button
              onClick={() => { onSelect(null); setIsOpen(false); }}
              className="w-full flex items-center justify-between gap-3 px-4 py-2.5 text-sm font-medium text-brand-text hover:bg-brand-elevated"
            >
              <div className="flex items-center gap-3 text-left whitespace-nowrap">
                <Users size={14} strokeWidth={1.5} className="text-brand-muted" />
                Todos os clientes
              </div>
              {!selectedTenant && <Check size={14} className="text-brand-primary" />}
            </button>
            
            <div className="h-px bg-brand-border my-1" />
            
            <div className="max-h-60 overflow-y-auto no-scrollbar">
              {tenants.map(t => (
                <button
                  key={t.id}
                  onClick={() => { onSelect(t.id); setIsOpen(false); }}
                  className="w-full flex items-center justify-between gap-3 px-4 py-2.5 text-sm font-medium text-brand-text hover:bg-brand-elevated"
                >
                  <div className="flex items-center gap-3 text-left whitespace-nowrap">
                    <div className="w-2 h-2 rounded-full bg-brand-primary" />
                    {t.name}
                  </div>
                  {selectedTenant === t.id && <Check size={14} className="text-brand-primary" />}
                </button>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
