import * as access from '../access';
import { useAjustes } from '../hooks/useAjustes';
import AjustesView from './ajustes/AjustesView';
import { Denied, Screen } from './ui/kit';

// Contêiner: papel e dados. A apresentação mora em ajustes/AjustesView.
export default function AjustesScreen({ role, refreshKey }: { role?: string; refreshKey?: number }) {
  const allowed = access.isOperator(role as never);
  const ajustes = useAjustes(allowed, refreshKey);
  return (
    <Screen>
      {allowed
        ? <AjustesView state={ajustes.state} actions={ajustes.actions} canEdit={access.canEditAjustes(role as never)} />
        : <Denied what="ajustes" role={role} />}
    </Screen>
  );
}
