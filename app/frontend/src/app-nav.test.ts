import { describe, expect, it } from 'vitest';
import { allowedView } from './App';

describe('allowedView', () => {
  it('operator opens any screen and defaults to overview', () => {
    expect(allowedView('cloud', true, true)).toBe('cloud');
    expect(allowedView(null, true, true)).toBe('overview');
    expect(allowedView('ai', true, false)).toBe('ai');
    expect(allowedView('nonsense', true, false)).toBe('overview');
  });
  it('pessoas só para quem administra', () => {
    expect(allowedView('people', true, true, true)).toBe('people');
    expect(allowedView('people', true, true, false)).toBe('overview');
    expect(allowedView('people', false, false, false)).toBe('incidents');
  });
  it('client role cannot reach operator screens via URL', () => {
    for (const v of ['overview', 'monitoring', 'cloud', 'secops', 'ai', 'contracts']) expect(allowedView(v, false, false)).toBe('incidents');
    expect(allowedView('customers', false, true)).toBe('customers');
    expect(allowedView('vulns', false, false)).toBe('vulns');
  });
  it('cliente abre no painel; os demais seguem o padrão', () => {
    expect(allowedView(null, false, false, false, true)).toBe('painel');
    expect(allowedView('overview', false, false, false, true)).toBe('painel');
    expect(allowedView('vulns', false, false, false, true)).toBe('vulns');
    expect(allowedView(null, false, false, false, false)).toBe('incidents');
  });
});
