import { describe, expect, it } from 'vitest';
import { allowedView } from './App';

describe('allowedView', () => {
  it('operator opens any screen and defaults to overview', () => {
    expect(allowedView('cloud', true, true)).toBe('cloud');
    expect(allowedView(null, true, true)).toBe('overview');
    expect(allowedView('nonsense', true, false)).toBe('overview');
  });
  it('client role cannot reach operator screens via URL', () => {
    for (const v of ['overview', 'monitoring', 'cloud', 'secops', 'contracts']) expect(allowedView(v, false, false)).toBe('incidents');
    expect(allowedView('customers', false, true)).toBe('customers');
  });
});
