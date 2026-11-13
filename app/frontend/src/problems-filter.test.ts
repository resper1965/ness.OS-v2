import { describe, expect, it } from 'vitest';
import { applyFilter, readFilter, type Problem } from './components/ProblemsView';

const p = (id: string, sev: number, host: string, clock: number, ack = false): Problem =>
  ({ id, title: `t${id}`, severity: '', severity_level: sev, host, clock, acknowledged: ack });
const list = [p('1', 3, 'web01', 100), p('2', 5, 'db01', 300), p('3', 3, 'web02', 50, true), p('4', 2, 'web01', 10)];

describe('problems filter', () => {
  it('orders by severity then oldest first', () => {
    expect(applyFilter(list, readFilter('')).rows.map(r => r.id)).toEqual(['2', '3', '1', '4']);
  });
  it('severity chip counts ignore the severity filter but respect search and ack', () => {
    const { rows, counts } = applyFilter(list, readFilter('?sev=5&q=web&ack=no'));
    expect(rows).toEqual([]);
    expect(counts.get(3)).toBe(1);
    expect(counts.get(2)).toBe(1);
    expect(counts.get(5)).toBeUndefined();
  });
  it('filters by customer, with unknown customer as its own bucket', () => {
    const l = [{ ...list[0], customer: 'Cavan' }, list[1]];
    expect(applyFilter(l, readFilter('?cliente=Cavan')).rows.map(r => r.id)).toEqual(['1']);
    expect(applyFilter(l, readFilter('?cliente=Sem+cliente')).rows.map(r => r.id)).toEqual(['2']);
  });
  it('rejects junk from the URL', () => {
    expect(readFilter('?sev=9,x,4&ack=maybe&group=foo')).toEqual({ sev: [4], ack: '', q: '', group: '', customer: '' });
  });
});

import { incidentQuery, readIncidentFilter } from './components/IncidentsPage';

describe('incident filter', () => {
  it('defaults to the last 24h and maps to the API query', () => {
    const f = readIncidentFilter('?view=incidents&id=3');
    expect(f).toEqual({ period: '24h', status: '', sev: '', q: '' });
    expect(incidentQuery(f, Date.parse('2026-11-13T12:00:00Z'))).toBe('&from=2026-11-12T12%3A00%3A00.000Z');
    expect(incidentQuery({ period: 'all', status: 'open', sev: '5,4', q: ' db 1 ' })).toBe('&status=open&severity=5,4&q=db%201');
  });
});

import { customerMatrix } from './components/CoreDashboard';

describe('customer matrix', () => {
  it('counts per severity and puts the worst customer first', () => {
    const m = customerMatrix([{ ...list[0], customer: 'A' }, { ...list[3], customer: 'A' }, list[1]]);
    expect(m.map(([c]) => c)).toEqual(['Sem cliente', 'A']);
    expect(m[1][1][3]).toBe(1);
    expect(m[1][1][2]).toBe(1);
  });
});
