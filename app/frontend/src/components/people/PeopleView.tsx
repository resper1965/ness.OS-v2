import { useState } from 'react';
import { Pencil, Plus, RefreshCw, Save, X } from 'lucide-react';
import type { PeopleActions, PeopleState, PendingLogin, Person, PersonForm } from '../../hooks/usePeople';
import {
  Alert, Badge, Button, CheckField, ConfirmButton, Empty, ErrorState, Panel, PageHeader, SelectField, Skeleton, TextField,
} from '../ui/kit';

const empty: PersonForm = { email: '', full_name: '', kind: 'ness', customer_ids: [], is_oncall: false, is_active: true };
const toForm = (p: Person): PersonForm => ({
  email: p.email, full_name: p.full_name ?? '', kind: p.kind, customer_ids: p.customer_ids, is_oncall: p.is_oncall, is_active: p.is_active,
});

function PersonFormView({ initial, creating, state, onSave, onCancel }: {
  initial: PersonForm; creating: boolean; state: PeopleState; onSave: (f: PersonForm) => void; onCancel: () => void;
}) {
  const [f, setF] = useState(initial);
  const external = f.kind === 'externo';
  const toggle = (id: number) => setF({
    ...f,
    // Externo tem exatamente 1 cliente: marcar troca o anterior.
    customer_ids: external ? [id] : f.customer_ids.includes(id) ? f.customer_ids.filter((x) => x !== id) : [...f.customer_ids, id],
  });
  return (
    <form aria-label={creating ? 'Nova pessoa' : 'Editar pessoa'} className="nx-stack" autoComplete="off"
      onSubmit={(e) => { e.preventDefault(); onSave(f); }}>
      <div className="nx-grid">
        <TextField label="E-mail" type="email" value={f.email} required maxLength={320} disabled={!creating}
          hint={creating && !external ? 'Equipe ness.: somente @ness.com.br.' : undefined} onChange={(e) => setF({ ...f, email: e.target.value })} />
        <TextField label="Nome" value={f.full_name} required maxLength={255} onChange={(e) => setF({ ...f, full_name: e.target.value })} />
        <SelectField label="Tipo" value={f.kind} disabled={!creating}
          onChange={(e) => setF({ ...f, kind: e.target.value as PersonForm['kind'], customer_ids: [], is_oncall: false })}>
          <option value="ness">Equipe ness.</option>
          <option value="externo">Técnico do cliente</option>
        </SelectField>
      </div>
      <fieldset className="nx-stack" style={{ border: 0, padding: 0, margin: 0 }}>
        <legend className="nx-meta">{external ? 'Cliente (exatamente 1)' : 'Equipes de cliente'}</legend>
        {state.customers.filter((c) => c.active && c.glpi_entity_id !== null).map((c) => (
          <CheckField key={c.id} label={c.display_name} checked={f.customer_ids.includes(c.id)} onChange={() => toggle(c.id)} />
        ))}
      </fieldset>
      {!external && <CheckField label="Plantão (vê todos os clientes)" checked={f.is_oncall} onChange={(e) => setF({ ...f, is_oncall: e.target.checked })} />}
      {!creating && <CheckField label="Pessoa ativa" checked={f.is_active} onChange={(e) => setF({ ...f, is_active: e.target.checked })} />}
      <div className="nx-actions">
        <Button variant="primary" type="submit" icon={Save} disabled={state.busy}>{creating ? 'Cadastrar' : 'Salvar'}</Button>
        <Button icon={X} onClick={onCancel}>Cancelar</Button>
      </div>
    </form>
  );
}

function PendingRow({ p, people, busy, onLink }: { p: PendingLogin; people: Person[]; busy: boolean; onLink: (id: number) => void }) {
  const [id, setId] = useState('');
  return (
    <tr>
      <td>{p.email ?? '—'}<br /><span className="nx-mono nx-muted">{p.subject}</span></td>
      <td>{p.attempts}</td>
      <td>{new Date(p.last_seen).toLocaleString('pt-BR', { timeZone: 'America/Sao_Paulo' })}</td>
      <td>
        <div className="nx-actions">
          <SelectField label="Pessoa" value={id} onChange={(e) => setId(e.target.value)}>
            <option value="">Escolher…</option>
            {people.filter((x) => x.is_active).map((x) => <option key={x.id} value={x.id}>{x.full_name ?? x.email}</option>)}
          </SelectField>
          <ConfirmButton label="Vincular" confirmLabel="Confirmar vínculo" disabled={busy || !id} onConfirm={() => onLink(Number(id))} />
        </div>
      </td>
    </tr>
  );
}

export default function PeopleView({ state, actions }: { state: PeopleState; actions: PeopleActions }) {
  const names = new Map(state.customers.map((c) => [c.id, c.display_name]));
  const editingPerson = typeof state.editing === 'number' ? state.people.find((p) => p.id === state.editing) : undefined;
  return (
    <>
      <PageHeader title="Pessoas" kicker="Administração" actions={(
        <>
          <Button icon={RefreshCw} disabled={state.phase !== 'ready' || state.busy} onClick={() => void actions.checkSync()}>Verificar GLPI</Button>
          <Button variant="primary" icon={Plus} disabled={state.phase !== 'ready' || state.busy} onClick={() => actions.startEdit('new')}>Nova pessoa</Button>
        </>
      )} />
      <div role="status" aria-live="polite">{state.notice && <Alert tone="info">{state.notice}</Alert>}</div>
      {state.actionError && <Alert>{state.actionError}</Alert>}
      {state.diff && (
        <Panel title="Sincronização com o GLPI" meta={<Badge tone={state.diff.length ? 'warn' : 'ok'}>{state.diff.length ? `${state.diff.length} diferenças` : 'Em dia'}</Badge>}>
          {state.diff.length === 0 ? <p className="nx-muted">O GLPI já reflete o cadastro.</p> : (
            <ul className="nx-mono" aria-label="Diferenças com o GLPI">{state.diff.map((d, i) => <li key={i}>{d}</li>)}</ul>
          )}
        </Panel>
      )}
      {state.canLink && state.pending.length > 0 && (
        <Panel title="Logins pendentes" meta={<Badge tone="warn">{state.pending.length}</Badge>} flush>
          <table className="nx-table">
            <caption className="sr-only">Logins recusados por falta de vínculo</caption>
            <thead><tr><th scope="col">Quem tentou</th><th scope="col">Tentativas</th><th scope="col">Última</th><th scope="col">Vincular a</th></tr></thead>
            <tbody>{state.pending.map((p) => <PendingRow key={`${p.issuer}|${p.subject}`} p={p} people={state.people} busy={state.busy} onLink={(id) => void actions.link(p, id)} />)}</tbody>
          </table>
        </Panel>
      )}
      {state.phase === 'loading' && <Skeleton rows={4} />}
      {state.phase === 'error' && state.error && <ErrorState error={state.error} onRetry={() => void actions.load()} />}
      {state.phase === 'ready' && (
        <>
          {state.editing !== null && (state.editing === 'new' || editingPerson) && (
            <Panel title={state.editing === 'new' ? 'Nova pessoa' : (editingPerson?.full_name ?? 'Editar pessoa')}>
              <PersonFormView key={String(state.editing)} initial={editingPerson ? toForm(editingPerson) : empty} creating={state.editing === 'new'}
                state={state} onSave={(f) => void actions.save(f)} onCancel={actions.cancelEdit} />
            </Panel>
          )}
          <Panel title="Pessoas e equipes" meta={<Badge>{state.people.length}</Badge>} flush>
            {state.people.length === 0 ? <Empty title="Ninguém cadastrado." hint="Cadastre as pessoas aqui: o acesso ao Hub, ao GLPI e aos avisos nasce deste cadastro." /> : (
              <table className="nx-table">
                <caption className="sr-only">Pessoas e equipes</caption>
                <thead><tr><th scope="col">Pessoa</th><th scope="col">Tipo</th><th scope="col">Clientes</th><th scope="col">Plantão</th><th scope="col">Estado</th><th scope="col"><span className="sr-only">Ações</span></th></tr></thead>
                <tbody>
                  {state.people.map((p) => (
                    <tr key={p.id}>
                      <td>{p.full_name ?? '—'}<br /><span className="nx-mono nx-muted">{p.email}</span></td>
                      <td>{p.kind === 'externo' ? 'Técnico do cliente' : 'ness.'}</td>
                      <td>{p.customer_ids.map((id) => names.get(id) ?? `#${id}`).join(', ') || '—'}</td>
                      <td>{p.is_oncall ? <Badge tone="info">Plantão</Badge> : '—'}</td>
                      <td><Badge tone={p.is_active ? 'ok' : 'neutral'}>{p.is_active ? 'Ativa' : 'Inativa'}</Badge></td>
                      <td>
                        <div className="nx-actions">
                          <Button icon={Pencil} aria-label={`Editar ${p.full_name ?? p.email}`} onClick={() => actions.startEdit(p.id)}>Editar</Button>
                          {p.is_active && <ConfirmButton label="Desativar" confirmLabel={`Confirmar desativação de ${p.full_name ?? p.email}`} disabled={state.busy} onConfirm={() => void actions.deactivate(p.id)} />}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </Panel>
        </>
      )}
    </>
  );
}
