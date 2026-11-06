export const TZ = 'America/Sao_Paulo';

// Data pura (AAAA-MM-DD) não passa por Date: evita deslocar um dia pelo fuso.
export function fmtDate(v?: string | null): string {
  if (!v) return '—';
  const [y, m, d] = v.slice(0, 10).split('-');
  return `${d}/${m}/${y}`;
}

export function fmtDateTime(v?: string | null): string {
  const t = v ? new Date(v) : null;
  if (!t || Number.isNaN(t.getTime())) return '—';
  return `${new Intl.DateTimeFormat('pt-BR', { timeZone: TZ, dateStyle: 'short', timeStyle: 'short' }).format(t)} BRT`;
}

export const fmtTime = (v: string) => v.slice(0, 5);

export function maskEmail(email: string): string {
  const [user = '', domain = ''] = email.split('@');
  const tld = domain.includes('.') ? domain.slice(domain.lastIndexOf('.')) : '';
  return `${user.slice(0, 1)}***@${domain.slice(0, 1)}***${tld}`;
}

export const maskPhone = (phone: string) => '*'.repeat(Math.max(phone.length - 2, 0)) + phone.slice(-2);

export const MODALITY: Record<string, string> = { managed: 'Gerenciado', onsite: 'No local', shared: 'Compartilhado' };
export const STATUS: Record<string, string> = { draft: 'Rascunho', active: 'Ativo', suspended: 'Suspenso', ended: 'Encerrado' };
export const ROLE: Record<string, string> = { soc: 'SOC', noc: 'NOC', operator: 'Operador', admin: 'Administrador' };
export const WEEKDAY = ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb', 'Dom'];
