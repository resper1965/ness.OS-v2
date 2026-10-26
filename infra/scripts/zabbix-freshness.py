"""Summarize sample freshness only; this is not availability or health acceptance."""
import re


def summarize_freshness(metrics: list[dict], observed_epoch: int) -> dict:
    """Consume normalized clocks/states and already-resolved effective delays."""
    result = {'essential_metrics': len(metrics), 'fresh': 0, 'stale': 0,
              'unknown': 0}
    for metric in metrics:
        delay = metric.get('delay')
        match = re.fullmatch(r'([0-9]+)([smhd]?)', delay) if isinstance(delay, str) else None
        interval = (int(match[1]) * {'': 1, 's': 1, 'm': 60, 'h': 3600,
                                   'd': 86400}[match[2]]) if match else 0
        clock = metric.get('lastclock')
        if (not interval or metric.get('state') != 0 or type(clock) is not int
                or clock <= 0 or clock > observed_epoch):
            result['unknown'] += 1
        elif observed_epoch - clock <= 3 * interval:
            result['fresh'] += 1
        else:
            result['stale'] += 1
    result['state'] = ('UNKNOWN' if not metrics or result['unknown'] else
                       'STALE' if result['stale'] else 'FRESH')
    return result
