/**
 * ness.OS — Module Switcher
 * Top bar que permite navegar entre os 3 módulos da plataforma.
 * Cada módulo tem cor, ícone e label próprios.
 */
import React from 'react';
import { Globe, Server, Shield } from 'lucide-react';

export type NessModule = 'core' | 'infraops' | 'secops';

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
];

export default function ModuleSwitcher({
  active, onChange, scoped = false,
}: {
  active: NessModule;
  onChange: (mod: NessModule) => void;
  scoped?: boolean;
}) {
  const visibleModules = MODULES.filter((module) =>
    !scoped || module.id === 'infraops'
  );
  return (
    <div
      className="flex items-center gap-1 px-1.5 md:px-2 py-1.5 rounded-2xl border min-w-0 overflow-x-auto"
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
            aria-label={mod.label}
            aria-pressed={isActive}
            className="relative flex items-center gap-2 px-3 py-2 md:py-1.5 shrink-0 rounded-xl transition-all duration-300 select-none"
            style={isActive ? {
              background: `${mod.color}18`,
            } : {}}
          >
            <Icon
              size={14}
              style={{ color: isActive ? mod.color : 'rgba(255,255,255,0.3)' }}
            />
            <span
              className={`text-xs font-semibold tracking-tight transition-colors duration-200 ${isActive ? '' : 'hidden sm:inline'}`}
              style={{ color: isActive ? mod.color : 'rgba(255,255,255,0.3)' }}
            >
              {mod.label}
            </span>
            {isActive && (
              <span
                className="absolute bottom-0 left-1/2 -translate-x-1/2 w-4 h-0.5 rounded-full"
                style={{ background: mod.color }}
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
