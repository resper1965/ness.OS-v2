import { useEffect, useId, useRef, useState, type ComponentProps, type ElementType, type ReactNode } from 'react';
import { Info, Lock, RefreshCw, TriangleAlert } from 'lucide-react';
import { type ApiError } from '../../http';
import '../../ness-ui.css';

export const ICON = { size: 14, strokeWidth: 1.5, 'aria-hidden': true } as const;

export const Screen = ({ children }: { children: ReactNode }) => <div className="nx">{children}</div>;

// Marca de produto: minúscula, ponto interno sempre em BlueDot.
export const ProductMark = () => <>n<span style={{ color: 'var(--nx-accent)' }}>.</span>infraops</>;

// O título da tela fica na banda do shell (h1); aqui só o kicker e as ações.
export function PageHeader({ kicker, actions }: { title: string; kicker: string; actions?: ReactNode }) {
  return (
    <div className="nx-head">
      <div><span className="nx-meta"><ProductMark /> · {kicker}</span></div>
      {actions && <div className="nx-actions">{actions}</div>}
    </div>
  );
}

export function Panel({ title, meta, actions, flush, children }: {
  title: string; meta?: ReactNode; actions?: ReactNode; flush?: boolean; children: ReactNode;
}) {
  return (
    <section className="nx-panel" aria-label={title}>
      <header><div className="nx-actions"><h2>{title}</h2>{meta}</div>{actions}</header>
      <div className={flush ? 'nx-flush' : undefined}>{children}</div>
    </section>
  );
}

export function Button({ variant, icon: Icon, children, ...rest }: ComponentProps<'button'> & {
  variant?: 'primary' | 'danger' | 'link'; icon?: ElementType;
}) {
  return (
    <button type="button" {...rest} className={`nx-btn ${variant ? `nx-${variant}` : ''}`}>
      {Icon && <Icon {...ICON} />}{children}
    </button>
  );
}

export type Tone = 'ok' | 'warn' | 'bad' | 'info' | 'neutral';
// Estado nunca só por cor: sempre texto, e ícone quando informado.
export function Badge({ tone = 'neutral', icon: Icon, children }: { tone?: Tone; icon?: ElementType; children: ReactNode }) {
  return <span className={`nx-badge ${tone}`}>{Icon && <Icon size={12} strokeWidth={1.5} aria-hidden />}{children}</span>;
}

// Ação destrutiva em dois passos, operável por teclado: o foco acompanha a troca de botão.
export function ConfirmButton({ label, confirmLabel, onConfirm, disabled, icon }: {
  label: string; confirmLabel: string; onConfirm: () => void; disabled?: boolean; icon?: ElementType;
}) {
  const [asking, setAsking] = useState(false);
  const confirmRef = useRef<HTMLButtonElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const moved = useRef(false);
  useEffect(() => {
    if (asking) confirmRef.current?.focus();
    else if (moved.current) triggerRef.current?.focus();
  }, [asking]);
  const ask = (v: boolean) => { moved.current = true; setAsking(v); };
  if (!asking) return <Button ref={triggerRef} variant="danger" icon={icon} disabled={disabled} onClick={() => ask(true)}>{label}</Button>;
  return (
    <span className="nx-actions">
      <Button ref={confirmRef} variant="danger" disabled={disabled} onClick={() => { setAsking(false); onConfirm(); }}>{confirmLabel}</Button>
      <Button onClick={() => ask(false)}>Cancelar</Button>
    </span>
  );
}

export function Alert({ tone, children }: { tone?: 'warn' | 'info'; children: ReactNode }) {
  const Icon = tone === 'info' ? Info : TriangleAlert;
  return <div role={tone === 'info' ? 'status' : 'alert'} className={`nx-alert ${tone ?? ''}`}><Icon {...ICON} />{children}</div>;
}

export interface FieldProps {
  id: string;
  'aria-describedby'?: string;
  'aria-invalid'?: true;
  'aria-errormessage'?: string;
}

// Dica e erro ligados ao controle; erro só texto vindo do servidor já tratado (nunca lista de 422).
export function Field({ label, hint, error, children }: {
  label: string; hint?: string; error?: string | null; children: (p: FieldProps) => ReactNode;
}) {
  const id = useId();
  const hintId = `${id}-hint`;
  const errId = `${id}-err`;
  const describedBy = [error && errId, hint && hintId].filter(Boolean).join(' ');
  const props: FieldProps = {
    id,
    ...(describedBy && { 'aria-describedby': describedBy }),
    ...(error && { 'aria-invalid': true as const, 'aria-errormessage': errId }),
  };
  return (
    <div className="nx-field">
      <label htmlFor={id}>{label}</label>
      {children(props)}
      {hint && <span id={hintId} className="nx-hint">{hint}</span>}
      {error && <span id={errId} className="nx-error">{error}</span>}
    </div>
  );
}

type Extra = { label: string; hint?: string; error?: string | null };
export const TextField = ({ label, hint, error, ...p }: Extra & ComponentProps<'input'>) =>
  <Field label={label} hint={hint} error={error}>{(a) => <input {...a} {...p} />}</Field>;

export const AreaField = ({ label, hint, error, ...p }: Extra & ComponentProps<'textarea'>) =>
  <Field label={label} hint={hint} error={error}>{(a) => <textarea {...a} {...p} />}</Field>;

export const SelectField = ({ label, hint, error, children, ...p }: Extra & ComponentProps<'select'>) =>
  <Field label={label} hint={hint} error={error}>{(a) => <select {...a} {...p}>{children}</select>}</Field>;

export function CheckField({ label, ...p }: { label: string } & Omit<ComponentProps<'input'>, 'type'>) {
  const id = useId();
  return <div className="nx-field nx-check"><input id={id} type="checkbox" {...p} /><label htmlFor={id}>{label}</label></div>;
}

export const Skeleton = ({ rows = 3 }: { rows?: number }) => (
  <div role="status" aria-label="Carregando"><span className="sr-only">Carregando…</span>
    {Array.from({ length: rows }, (_, i) => <div key={i} className="nx-skel" />)}
  </div>
);

export const Empty = ({ title, hint, action }: { title: string; hint?: string; action?: ReactNode }) => (
  <div className="nx-empty"><strong>{title}</strong>{hint && <span>{hint}</span>}{action}</div>
);

export function Denied({ what, role }: { what: string; role?: string }) {
  return (
    <Panel title="Sem permissão">
      <Empty
        title={`Seu papel${role ? ` (${role})` : ''} não acessa ${what}.`}
        hint="Peça acesso a um administrador da plataforma. Nenhum dado foi carregado."
      />
    </Panel>
  );
}

export function ErrorState({ error, onRetry }: { error: ApiError; onRetry?: () => void }) {
  return (
    <div role="alert" className="nx-alert">
      {error.status === 403 ? <Lock {...ICON} /> : <TriangleAlert {...ICON} />}
      <div className="nx-stack" style={{ gap: 8 }}>
        <span>{error.message}</span>
        {error.requestId && <span className="nx-mono nx-muted">request {error.requestId}</span>}
        {onRetry && error.status !== 403 && <Button icon={RefreshCw} onClick={onRetry}>Tentar de novo</Button>}
      </div>
    </div>
  );
}
