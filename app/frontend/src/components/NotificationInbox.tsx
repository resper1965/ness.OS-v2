import { useEffect, useState } from 'react';
import { Inbox } from 'lucide-react';

const API_BASE = import.meta.env.VITE_API_URL ?? '';

interface Item { incident_id: string; severity: number; sent_at: string | null; acknowledged_at: string | null }

// Avisos do usuário logado. `sent_at` é só aceite do provedor; lido = `acknowledged_at`.
// `version` muda a cada evento de incidente ou ação no caso; abrir a caixa também recarrega.
export default function NotificationInbox({ version = 0 }: { version?: number }) {
  const [items, setItems] = useState<Item[]>([]);
  const [opened, setOpened] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    fetch(`${API_BASE}/api/notifications/inbox?limit=10`, { credentials: 'include', signal: controller.signal })
      .then(r => (r.ok ? (r.json() as Promise<Item[]>) : []))
      .then(setItems)
      .catch(() => {});
    return () => controller.abort();
  }, [version, opened]);

  const pending = items.filter(i => !i.acknowledged_at).length;
  return (
    <details className="px-3 py-2 rounded-lg bg-white/[0.03] text-xs" onToggle={e => { if (e.currentTarget.open) setOpened(n => n + 1); }}>
      <summary className="flex cursor-pointer items-center gap-2 text-[var(--color-brand-muted)]">
        <Inbox size={14} aria-hidden="true" />
        <span>Avisos</span>
        <span className="ml-auto" aria-label={`${pending} sem reconhecimento`}>{pending}</span>
      </summary>
      <ul className="mt-2 space-y-1">
        {items.length === 0 && <li className="text-brand-muted">Nenhum aviso.</li>}
        {items.map(i => (
          <li key={i.incident_id}>
            <a href={`/?view=incidents&id=${encodeURIComponent(i.incident_id)}`} className="flex justify-between gap-2 hover:underline">
              <span>Caso #{i.incident_id} · sev. {i.severity}</span>
              <span>{i.acknowledged_at ? 'reconhecido' : 'pendente'}</span>
            </a>
          </li>
        ))}
      </ul>
    </details>
  );
}
