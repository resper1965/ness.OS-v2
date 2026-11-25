import * as access from '../access';
import { usePeople } from '../hooks/usePeople';
import PeopleView from './people/PeopleView';
import { Denied, Screen } from './ui/kit';

// Contêiner: papel e dados. A apresentação mora em people/PeopleView.
export default function PeopleScreen({ role, refreshKey }: { role?: string; refreshKey?: number }) {
  const allowed = access.canManagePeople(role as never);
  const people = usePeople(allowed, refreshKey);
  return (
    <Screen>
      {allowed ? <PeopleView state={people.state} actions={people.actions} /> : <Denied what="pessoas" role={role} />}
    </Screen>
  );
}
