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
    label: 'ness.OS',
    sublabel: 'Gestão Global',
    color: '#6366F1',
    glowColor: 'rgba(99,102,241,0.4)',
    icon: Globe,
  },
  {
    id: 'infraops',
    label: 'n.infraops',
    sublabel: 'NOC · Infraestrutura',
    color: '#3B82F6',
    glowColor: 'rgba(59,130,246,0.4)',
    icon: Server,
  },
  {
    id: 'secops',
    label: 'n.secops',
    sublabel: 'SOC · Segurança',
    color: '#EF4444',
    glowColor: 'rgba(239,68,68,0.4)',
    icon: Shield,
  },
];

export default function ModuleSwitcher({
  active,
  onChange,
}: {
  active: NessModule;
  onChange: (mod: NessModule) => void;
}) {
  const activeDef = MODULES.find(m => m.id === active)!;

  return (
    <div
      className="flex items-center gap-1 px-2 py-1.5 rounded-2xl border"
      style={{
        background: 'rgba(255,255,255,0.03)',
        borderColor: 'rgba(255,255,255,0.08)',
      }}
    >
      {MODULES.map(mod => {
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
