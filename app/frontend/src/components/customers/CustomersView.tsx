import { useState } from 'react';
import { Eye, EyeOff, Lock, Pencil, Plus, Save, Trash2, X } from 'lucide-react';
import { maskEmail, maskPhone } from '../../format';
import {
  isCanonicalAlias, type Contact, type ContactForm, type ContactsActions, type ContactsState, type Customer,
  type CustomerForm, type CustomersActions, type CustomersState,
} from '../../hooks/useCustomers';
import {
  Alert, Badge, Button, CheckField, ConfirmButton, Empty, ErrorState, ICON, Panel, PageHeader, SelectField,
  Skeleton, TextField,
} from '../ui/kit';

const SEVERITIES = [1, 2, 3, 4, 5];

function CustomerFormView({ initial, creating, busy, onSave, onCancel }: {
  initial: CustomerForm; creating: boolean; busy: boolean; onSave: (f: CustomerForm) => void; onCancel: () => void;
}) {
  const [f, setF] = useState(initial);
  return (
    <form aria-label={creating ? 'Novo cliente' : 'Editar cliente'} className="nx-stack"
      onSubmit={(e) => { e.preventDefault(); onSave(f); }}>
      <div className="nx-grid">
        <TextField label="Chave" value={f.key} required disabled={!creating} onChange={(e) => setF({ ...f, key: e.target.value })}
          hint={creating ? 'Identificador estável do cliente.' : 'Não muda depois de criado.'} />
        <TextField label="Nome de exibição" value={f.display_name} required onChange={(e) => setF({ ...f, display_name: e.target.value })} />
        <TextField label="Entidade de atendimento (ID)" type="number" min={0} inputMode="numeric" value={f.entity_id}
          onChange={(e) => setF({ ...f, entity_id: e.target.value })} hint="Um ID só pode estar em um cliente ativo." />
      </div>
      <CheckField label="Cliente ativo" checked={f.active} onChange={(e) => setF({ ...f, active: e.target.checked })} />
      <div className="nx-actions">
        <Button variant="primary" type="submit" icon={Save} disabled={busy}>{creating ? 'Criar cliente' : 'Salvar'}</Button>
        <Button icon={X} onClick={onCancel}>Cancelar</Button>
      </div>
    </form>
  );
}

function Aliases({ customer, state, actions, canEdit }: {
  customer: Customer; state: CustomersState; actions: CustomersActions; canEdit: boolean;
}) {
  const [alias, setAlias] = useState('');
  return (
    <Panel title="Apelidos" meta={<Badge>{customer.aliases.length}</Badge>}>
      {customer.aliases.length === 0 ? <Empty title="Sem apelidos." hint="Apelidos ligam nomes alternativos ao cliente." /> : (
        <ul className="nx-chips" aria-label="Apelidos do cliente">
          {customer.aliases.map((a) => (
            <li key={a}>
              <span className="nx-mono">{a}</span>
              {isCanonicalAlias(customer, a) && <Badge tone="info" icon={Lock}>canônico</Badge>}
              {canEdit && (
                <button type="button" aria-label={`Remover apelido ${a}`} disabled={state.busy} onClick={() => void actions.removeAlias(customer.id, a)}>
                  <Trash2 {...ICON} />
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
      {canEdit && (
        <form className="nx-actions" style={{ marginTop: 16, alignItems: 'flex-end' }} aria-label="Adicionar apelido"
          onSubmit={async (e) => { e.preventDefault(); if (await actions.addAlias(customer.id, alias)) setAlias(''); }}>
          <TextField label="Novo apelido" value={alias} required onChange={(e) => setAlias(e.target.value)} />
          <Button type="submit" icon={Plus} disabled={state.busy || !alias.trim()}>Adicionar</Button>
        </form>
      )}
    </Panel>
  );
}

const emptyContact: ContactForm = { name: '', email: '', phone: '', role: '', notify_severity_min: '3', active: true };
const toContactForm = (c: Contact): ContactForm => ({
  name: c.name, email: c.email, phone: c.phone ?? '', role: c.role, notify_severity_min: String(c.notify_severity_min), active: c.active,
});

function ContactFormView({ initial, creating, busy, onSave, onCancel }: {
  initial: ContactForm; creating: boolean; busy: boolean; onSave: (f: ContactForm) => void; onCancel: () => void;
}) {
  const [f, setF] = useState(initial);
  return (
    <form aria-label={creating ? 'Novo contato' : 'Editar contato'} className="nx-stack" autoComplete="off"
      onSubmit={(e) => { e.preventDefault(); onSave(f); }}>
      <div className="nx-grid">
        <TextField label="Nome do contato" value={f.name} required maxLength={255} onChange={(e) => setF({ ...f, name: e.target.value })} />
        <TextField label="E-mail do contato" type="email" value={f.email} required maxLength={320} onChange={(e) => setF({ ...f, email: e.target.value })} />
        <TextField label="Telefone do contato" type="tel" value={f.phone} maxLength={64} onChange={(e) => setF({ ...f, phone: e.target.value })} />
        <TextField label="Função" value={f.role} required maxLength={64} onChange={(e) => setF({ ...f, role: e.target.value })} />
        <SelectField label="Avisar a partir da severidade" value={f.notify_severity_min} onChange={(e) => setF({ ...f, notify_severity_min: e.target.value })}>
          {SEVERITIES.map((s) => <option key={s} value={s}>{s}</option>)}
        </SelectField>
      </div>
      <CheckField label="Contato ativo" checked={f.active} onChange={(e) => setF({ ...f, active: e.target.checked })} />
      <div className="nx-actions">
        <Button variant="primary" type="submit" icon={Save} disabled={busy}>{creating ? 'Criar contato' : 'Salvar'}</Button>
        <Button icon={X} onClick={onCancel}>Cancelar</Button>
      </div>
    </form>
  );
}

function Contacts({ state, actions, canEdit }: { state: ContactsState; actions: ContactsActions; canEdit: boolean }) {
  return (
    <Panel
      title="Contatos de aviso"
      meta={<Badge tone="warn">dado pessoal</Badge>}
      actions={canEdit && state.editingId === null && <Button icon={Plus} onClick={() => actions.startEdit('new')}>Novo contato</Button>}
      flush={state.editingId === null}
    >
      <div role="status" aria-live="polite">{state.notice && <Alert tone="info">{state.notice}</Alert>}</div>
      {state.actionError && <Alert>{state.actionError}</Alert>}
      {state.phase === 'loading' && <Skeleton rows={2} />}
      {state.phase === 'error' && state.error && <ErrorState error={state.error} />}
      {state.editingId !== null && canEdit && (
        <ContactFormView
          key={String(state.editingId)}
          initial={state.editingId === 'new' ? emptyContact : toContactForm(state.contacts.find((c) => c.id === state.editingId) as Contact)}
          creating={state.editingId === 'new'} busy={state.busy}
          onSave={(f) => void actions.save(f)} onCancel={actions.cancelEdit}
        />
      )}
      {state.phase === 'ready' && state.editingId === null && (state.contacts.length === 0
        ? <Empty title="Sem contatos cadastrados." hint="Sem contato, o cliente não recebe avisos." />
        : (
          <table className="nx-table">
            <caption className="sr-only">Contatos de aviso. E-mail e telefone ficam ocultos até serem revelados.</caption>
            <thead><tr><th scope="col">Nome</th><th scope="col">Função</th><th scope="col">E-mail</th><th scope="col">Telefone</th><th scope="col">Severidade mín.</th><th scope="col">Estado</th><th scope="col"><span className="sr-only">Ações</span></th></tr></thead>
            <tbody>
              {state.contacts.map((c) => {
                const shown = state.revealed.includes(c.id);
                return (
                  <tr key={c.id}>
                    <td>{c.name}</td><td>{c.role}</td>
                    <td className="nx-mono">{shown ? c.email : maskEmail(c.email)}</td>
                    <td className="nx-mono">{c.phone ? (shown ? c.phone : maskPhone(c.phone)) : '—'}</td>
                    <td className="nx-mono">{c.notify_severity_min}</td>
                    <td><Badge tone={c.active ? 'ok' : 'neutral'}>{c.active ? 'Ativo' : 'Inativo'}</Badge></td>
                    <td>
                      <div className="nx-actions">
                        <Button icon={shown ? EyeOff : Eye} aria-pressed={shown} aria-label={`${shown ? 'Ocultar' : 'Revelar'} e-mail e telefone de ${c.name}`}
                          onClick={() => actions.toggleReveal(c.id)}>{shown ? 'Ocultar' : 'Revelar'}</Button>
                        {canEdit && <Button icon={Pencil} aria-label={`Editar contato ${c.name}`} onClick={() => actions.startEdit(c.id)}>Editar</Button>}
                        {canEdit && <ConfirmButton icon={Trash2} label="Excluir" confirmLabel={`Confirmar exclusão de ${c.name}`} disabled={state.busy} onConfirm={() => void actions.remove(c.id)} />}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        ))}
    </Panel>
  );
}

const emptyCustomer: CustomerForm = { key: '', display_name: '', entity_id: '', active: true };
const toCustomerForm = (c: Customer): CustomerForm => ({
  key: c.key, display_name: c.display_name, entity_id: c.glpi_entity_id === null ? '' : String(c.glpi_entity_id), active: c.active,
});

export default function CustomersView({ state, actions, canEdit, contacts, contactsActions, canReadContacts }: {
  state: CustomersState; actions: CustomersActions; canEdit: boolean;
  contacts: ContactsState; contactsActions: ContactsActions; canReadContacts: boolean;
}) {
  const selected = state.customers.find((c) => c.id === state.selectedId) ?? null;
  return (
    <>
      <PageHeader title="Clientes" kicker="Cadastro" actions={canEdit && (
        <Button variant="primary" icon={Plus} disabled={state.phase !== 'ready' || state.busy} onClick={actions.startCreate}>Novo cliente</Button>
      )} />
      <div role="status" aria-live="polite">{state.notice && <Alert tone="info">{state.notice}</Alert>}</div>
      {state.actionError && <Alert>{state.actionError}</Alert>}

      {state.phase === 'loading' && <Skeleton rows={4} />}
      {state.phase === 'error' && state.error && <ErrorState error={state.error} onRetry={() => void actions.load()} />}
      {state.phase === 'ready' && (
        <>
          {canEdit && state.editing === 'new' && (
            <Panel title="Novo cliente">
              <CustomerFormView initial={emptyCustomer} creating busy={state.busy} onSave={(f) => void actions.save(f)} onCancel={actions.cancelEdit} />
            </Panel>
          )}
          <Panel title="Clientes" meta={<Badge>{state.customers.length}</Badge>} flush>
            {state.customers.length === 0 ? <Empty title="Nenhum cliente cadastrado." hint={canEdit ? 'Crie o primeiro cliente para vincular contratos e contatos.' : undefined} /> : (
              <table className="nx-table">
                <caption className="sr-only">Clientes</caption>
                <thead><tr><th scope="col">Cliente</th><th scope="col">Chave</th><th scope="col">Entidade de atendimento</th><th scope="col">Estado</th></tr></thead>
                <tbody>
                  {state.customers.map((c) => (
                    <tr key={c.id} className={c.id === state.selectedId ? 'is-selected' : undefined}>
                      <td><Button variant="link" aria-current={c.id === state.selectedId ? 'true' : undefined} onClick={() => actions.select(c.id)}>{c.display_name}</Button></td>
                      <td className="nx-mono">{c.key}</td>
                      <td className="nx-mono">{c.glpi_entity_id ?? '—'}</td>
                      <td><Badge tone={c.active ? 'ok' : 'neutral'}>{c.active ? 'Ativo' : 'Inativo'}</Badge></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </Panel>
          {selected && (
            <>
              <Panel title={selected.display_name} meta={<Badge tone={selected.active ? 'ok' : 'neutral'}>{selected.active ? 'Ativo' : 'Inativo'}</Badge>}
                actions={canEdit && state.editing !== 'edit' && <Button icon={Pencil} onClick={actions.startEdit}>Editar</Button>}>
                {state.editing === 'edit' && canEdit
                  ? <CustomerFormView key={selected.id} initial={toCustomerForm(selected)} creating={false} busy={state.busy} onSave={(f) => void actions.save(f)} onCancel={actions.cancelEdit} />
                  : (
                    <dl className="nx-grid" style={{ margin: 0 }}>
                      <div><dt className="nx-meta">Chave</dt><dd className="nx-mono" style={{ margin: 0 }}>{selected.key}</dd></div>
                      <div><dt className="nx-meta">Entidade de atendimento</dt><dd className="nx-mono" style={{ margin: 0 }}>{selected.glpi_entity_id ?? '—'}</dd></div>
                    </dl>
                  )}
              </Panel>
              <Aliases customer={selected} state={state} actions={actions} canEdit={canEdit} />
              {canReadContacts
                ? <Contacts state={contacts} actions={contactsActions} canEdit={canEdit} />
                : <Panel title="Contatos de aviso"><Empty title="Contatos são dado pessoal." hint="Seu papel não lê contatos. Peça a um operador NOC." /></Panel>}
            </>
          )}
          {!selected && state.customers.length > 0 && <p className="nx-muted">Selecione um cliente para ver apelidos e contatos.</p>}
        </>
      )}
    </>
  );
}
