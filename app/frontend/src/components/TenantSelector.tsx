import React, { useState, useEffect } from 'react';
import { Users, ChevronDown, Check, Building2 } from 'lucide-react';

const API_BASE = import.meta.env.VITE_API_URL ?? '';
const AUTH = { Authorization: 'Basic ' + btoa('admin:Nessnet@436!') };

interface Tenant {
  id: string;
  name: string;
}

interface Props {
  selectedTenant: string | null;
  onSelect: (tenantId: string | null) => void;
}

export default function TenantSelector({ selectedTenant, onSelect }: Props) {
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [isOpen, setIsOpen] = useState(false);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const fetchTenants = async () => {
      setLoading(true);
      try {
        const res = await fetch(`${API_BASE}/api/tenants/list`, { headers: AUTH });
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
  }, []);

  const currentTenant = tenants.find(t => t.id === selectedTenant);

  return (
    <div className="relative">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center gap-3 px-3 py-2 rounded-xl bg-white/[0.03] border border-white/[0.06] hover:bg-white/[0.06] transition-all group"
      >
        <div className="p-2 rounded-lg bg-[var(--color-brand-primary-dim)] text-[var(--color-brand-primary)]">
          <Building2 size={16} />
        </div>
        <div className="flex-1 text-left">
          <p className="text-[9px] font-bold text-[var(--color-brand-muted)] uppercase tracking-wider">Contexto</p>
          <p className="text-sm font-bold text-white truncate">
            {currentTenant ? currentTenant.name : 'Todos os Clientes'}
          </p>
        </div>
        <ChevronDown size={14} className={`text-[var(--color-brand-muted)] transition-transform ${isOpen ? 'rotate-180' : ''}`} />
      </button>

      {isOpen && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setIsOpen(false)} />
          <div className="absolute top-full left-0 right-0 mt-2 z-50 glass rounded-xl border border-white/[0.08] shadow-2xl py-2 overflow-hidden animate-fade-in">
            <button
              onClick={() => { onSelect(null); setIsOpen(false); }}
              className="w-full flex items-center justify-between px-4 py-2.5 text-sm font-medium text-white hover:bg-white/[0.05] transition-all"
            >
              <div className="flex items-center gap-3">
                <Users size={14} className="text-[var(--color-brand-muted)]" />
                Todos os Clientes
              </div>
              {!selectedTenant && <Check size={14} className="text-[var(--color-brand-primary)]" />}
            </button>
            
            <div className="h-px bg-white/[0.04] my-1" />
            
            <div className="max-h-60 overflow-y-auto no-scrollbar">
              {tenants.map(t => (
                <button
                  key={t.id}
                  onClick={() => { onSelect(t.id); setIsOpen(false); }}
                  className="w-full flex items-center justify-between px-4 py-2.5 text-sm font-medium text-white hover:bg-white/[0.05] transition-all"
                >
                  <div className="flex items-center gap-3">
                    <div className="w-1.5 h-1.5 rounded-full bg-[var(--color-brand-primary)]" />
                    {t.name}
                  </div>
                  {selectedTenant === t.id && <Check size={14} className="text-[var(--color-brand-primary)]" />}
                </button>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
