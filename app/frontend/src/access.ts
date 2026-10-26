import type { User } from './hooks/useAuth';

type Role = User['role'] | undefined;

export const isOperator = (role: Role) => ['platform_admin', 'admin', 'noc', 'soc'].includes(role ?? '');
export const canActOnIncidents = (role: Role) => isOperator(role) || role === 'operator';
export const canAccessPricing = (role: Role) => ['platform_admin', 'admin', 'gestao'].includes(role ?? '');

// Tenant filter sent to the API: only global operators may pick one; scoped users are pinned by the backend.
export const tenantScope = (role: Role, selected: string | null) =>
  isOperator(role) && selected ? selected.trim().toLowerCase() : null;

// Client-side SSE filter: no selection shows everything the backend already scoped.
export const matchesTenant = (selected: string | null, eventTenant: string | null | undefined) =>
  !selected || eventTenant === selected.trim().toLowerCase();

// Missing/zero/invalid timestamp is "no data", never "just now" or "56 years ago".
// number = epoch seconds, string = ISO 8601.
export function timeAgo(value: number | string | null | undefined, now = Date.now()): string {
  const ms = typeof value === 'number' ? value * 1000 : value ? new Date(value).getTime() : NaN;
  if (!Number.isFinite(ms) || ms <= 0) return 'sem dado';
  const s = Math.max(0, Math.floor((now - ms) / 1000));
  if (s < 60) return `há ${s}s`;
  if (s < 3600) return `há ${Math.floor(s / 60)}min`;
  if (s < 86400) return `há ${Math.floor(s / 3600)}h`;
  return `há ${Math.floor(s / 86400)}d`;
}
