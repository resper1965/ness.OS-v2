import { describe, expect, it } from 'vitest';
import { vulnQuery } from './VulnsView';

describe('vulnQuery', () => {
  it('drops empty filters and pins the selected tenant', () => {
    expect(vulnQuery({ agent: ' PC1 ', cve: '', severity: 'High' }, 'rzk', 100).toString()).toBe('agent=PC1&severity=High&customer_id=rzk&offset=100');
    expect(vulnQuery({ customer_id: 'target' }, null).toString()).toBe('customer_id=target');
  });
});
