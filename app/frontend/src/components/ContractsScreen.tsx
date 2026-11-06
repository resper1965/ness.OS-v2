import * as access from '../access';
import { useContracts } from '../hooks/useContracts';
import ContractsView from './contracts/ContractsView';
import { Denied, Screen } from './ui/kit';

// Contêiner: papel e dados. A apresentação mora em contracts/ContractsView.
export default function ContractsScreen({ role, refreshKey }: { role?: string; refreshKey?: number }) {
  const allowed = access.canReadCadastros(role as never);
  const { state, actions } = useContracts(allowed, refreshKey);
  return (
    <Screen>
      {allowed
        ? <ContractsView state={state} actions={actions} canEdit={access.canEditCadastros(role as never)} />
        : <Denied what="contratos" role={role} />}
    </Screen>
  );
}
