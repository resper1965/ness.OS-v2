import * as access from '../access';
import { useContacts, useCustomers } from '../hooks/useCustomers';
import CustomersView from './customers/CustomersView';
import { Denied, Screen } from './ui/kit';

// Contêiner: papel e dados. A apresentação mora em customers/CustomersView.
export default function CustomersScreen({ role }: { role?: string }) {
  const allowed = access.canReadCadastros(role as never);
  const canReadContacts = access.canReadContacts(role as never);
  const customers = useCustomers(allowed);
  const contacts = useContacts(customers.state.selectedId, allowed && canReadContacts);
  return (
    <Screen>
      {allowed
        ? <CustomersView state={customers.state} actions={customers.actions} canEdit={access.canEditCadastros(role as never)}
            contacts={contacts.state} contactsActions={contacts.actions} canReadContacts={canReadContacts} />
        : <Denied what="clientes" role={role} />}
    </Screen>
  );
}
