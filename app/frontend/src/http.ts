const API_BASE = import.meta.env.VITE_API_URL ?? '';

export class ApiError extends Error {
  status: number;
  requestId?: string;
  constructor(status: number, message: string, requestId?: string) {
    super(message);
    this.status = status;
    this.requestId = requestId;
  }
}

// Nome de fornecedor nunca chega à tela: mensagens conhecidas ganham texto neutro, o resto é varrido.
const KNOWN: Record<string, string> = {
  'Entidade GLPI já em uso': 'Entidade de atendimento já em uso por outro cliente ativo',
  'Entidade GLPI ou nome já em uso': 'Entidade de atendimento ou nome já em uso por outro cliente',
};
const VENDOR = /\b(zabbix|wazuh|glpi|action1|resend|authentik)\b/gi;
const GENERIC = 'Não foi possível concluir. Nada foi gravado.';
const MAX_DETAIL = 200;
// Detalhe longo pode carregar eco de dado enviado: acima do teto, só a mensagem genérica.
export const scrub = (text: string) =>
  KNOWN[text] ?? (text.length > MAX_DETAIL ? GENERIC : text.replace(VENDOR, 'sistema externo'));

function messageFor(status: number, detail: unknown): string {
  if (status === 401) return 'Sessão expirada. Entre novamente.';
  if (status === 403) return 'Seu papel não tem permissão para esta área ou ação.';
  if (status >= 500) return 'Falha no serviço. Nada foi gravado.';
  // detail em lista (422 do validador) ecoa o valor enviado, que pode ser dado pessoal: nunca exibir.
  if (typeof detail === 'string') return scrub(detail);
  return 'Dados inválidos. Revise os campos.';
}

export async function request<T>(path: string, init: { method?: string; body?: unknown } = {}): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      method: init.method ?? 'GET',
      credentials: 'include',
      headers: init.body === undefined ? undefined : { 'Content-Type': 'application/json' },
      body: init.body === undefined ? undefined : JSON.stringify(init.body),
    });
  } catch {
    throw new ApiError(0, 'Sem conexão com o serviço. Nada foi gravado.');
  }
  if (!res.ok) {
    const data = await res.json().catch(() => null);
    throw new ApiError(res.status, messageFor(res.status, data?.detail), res.headers.get('x-request-id') ?? undefined);
  }
  return res.status === 204 ? (undefined as T) : res.json();
}

export const asApiError = (e: unknown): ApiError => (e instanceof ApiError ? e : new ApiError(0, 'Erro inesperado.'));
export const describeError = (e: unknown): string => asApiError(e).message;
