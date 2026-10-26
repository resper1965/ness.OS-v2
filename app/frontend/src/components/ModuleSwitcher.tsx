/**
 * ness.OS — Module Switcher
 * Top bar que permite navegar entre os 3 módulos da plataforma.
 * Cada módulo tem cor, ícone e label próprios.
 */
import React from 'react';
import { Calculator, Globe, Server, Shield } from 'lucide-react';

export type NessModule = 'core' | 'infraops' | 'secops' | 'pricing';

interface ModuleDef {
  id: NessModule;
  label: string;
  sublabel: string;
  color: string;
  glowColor: string;
  icon: React.ElementType;
}

const MODULES: ModuleDef[] = [
  {
    id: 'core',
    label: 'Visão geral',
    sublabel: 'Gestão Global',
    color: '#6366F1',
    glowColor: 'rgba(99,102,241,0.4)',
    icon: Globe,
  },
  {
    id: 'infraops',
    label: 'InfraOps',
    sublabel: 'NOC · Infraestrutura',
    color: '#3B82F6',
    glowColor: 'rgba(59,130,246,0.4)',
    icon: Server,
  },
  {
    id: 'secops',
    label: 'SecOps',
    sublabel: 'SOC · Segurança',
    color: '#EF4444',
    glowColor: 'rgba(239,68,68,0.4)',
    icon: Shield,
  },
  {
    id: 'pricing',
    label: 'Pricing',
    sublabel: 'Comercial · Unit economics',
    color: '#10B981',
    glowColor: 'rgba(16,185,129,0.4)',
    icon: Calculator,
  },
];

export default function ModuleSwitcher({
  active, onChange, showPricing = false, scoped = false,
}: {
  active: NessModule;
  onChange: (mod: NessModule) => void;
  showPricing?: boolean;
  scoped?: boolean;
}) {
  const visibleModules = MODULES.filter((module) =>
    module.id === 'pricing' ? showPricing : !scoped || module.id === 'infraops'
  );
  return (
    <div
      className="flex items-center gap-1 px-2 py-1.5 rounded-2xl border"
      style={{
        background: 'rgba(255,255,255,0.03)',
        borderColor: 'rgba(255,255,255,0.08)',
      }}
    >
      {visibleModules.map(mod => {
        const Icon = mod.icon;
        const isActive = mod.id === active;
        return (
          <button
            key={mod.id}
            onClick={() => onChange(mod.id)}
            title={`${mod.label} — ${mod.sublabel}`}
            className="relative flex items-center gap-2 px-3 py-1.5 rounded-xl transition-all duration-300 select-none"
            style={isActive ? {
              background: `${mod.color}18`,
              boxShadow: `0 0 16px ${mod.glowColor}40`,
            } : {}}
          >
            <Icon
              size={14}
              style={{ color: isActive ? mod.color : 'rgba(255,255,255,0.3)' }}
            />
            <span
              className="text-xs font-semibold tracking-tight transition-colors duration-200"
              style={{ color: isActive ? mod.color : 'rgba(255,255,255,0.3)' }}
            >
              {mod.label}
            </span>
            {isActive && (
              <span
                className="absolute bottom-0 left-1/2 -translate-x-1/2 w-4 h-0.5 rounded-full"
                style={{ background: mod.color, boxShadow: `0 0 6px ${mod.glowColor}` }}
              />
            )}
          </button>
        );
      })}
    </div>
  );
}

export { MODULES };
export type { ModuleDef };
