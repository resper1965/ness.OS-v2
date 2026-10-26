"""Judge actual stored collection clocks, allowing additive LLD discovery."""


def evaluate(original_ids, current_ids, observations, change_epoch, max_unsupported):
    if not original_ids or not set(original_ids).issubset(current_ids):
        raise ValueError('Existing items lost; abort and reconcile')
    clocks = {o['clock'] for o in observations if o['clock'] > 0
        and o['clock'] >= change_epoch and o['master_state'] == 0
        and o['unsupported'] <= max_unsupported}
    return 'PASS' if len(clocks) >= 3 else 'PENDING'
