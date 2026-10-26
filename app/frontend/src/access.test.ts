import { describe, expect, it } from 'vitest';
import { canAccessPricing, canActOnIncidents, isOperator, matchesTenant, tenantScope, timeAgo } from './access';

describe('role gating', () => {
  it.each(['platform_admin', 'admin', 'noc', 'soc'] as const)('%s is a global operator', (r) => {
    expect(isOperator(r)).toBe(true);
    expect(canActOnIncidents(r)).toBe(true);
  });
  it.each(['cliente', 'viewer', 'helpdesk', 'gestao', 'operator', undefined] as const)('%s is not a global operator', (r) => {
    expect(isOperator(r)).toBe(false);
  });
  it('operator acts on incidents but only inside its tenant', () => {
    expect(canActOnIncidents('operator')).toBe(true);
    expect(canActOnIncidents('viewer')).toBe(false);
  });
  it('pricing is limited to admin/gestao', () => {
    expect(['platform_admin', 'admin', 'gestao'].every((r) => canAccessPricing(r as never))).toBe(true);
    expect(['noc', 'soc', 'cliente', 'operator', undefined].some((r) => canAccessPricing(r as never))).toBe(false);
  });
});

describe('tenant scope', () => {
  it('global operator may pick a tenant (normalized)', () => {
    expect(tenantScope('noc', ' Tenant-A ')).toBe('tenant-a');
    expect(tenantScope('noc', null)).toBeNull();
  });
  it('scoped users never send a tenant override', () => {
    expect(tenantScope('cliente', 'tenant-b')).toBeNull();
    expect(tenantScope('operator', 'tenant-b')).toBeNull();
  });
  it('SSE events from another tenant are dropped when one is selected', () => {
    expect(matchesTenant('Tenant-A', 'tenant-a')).toBe(true);
    expect(matchesTenant('tenant-a', 'tenant-b')).toBe(false);
    expect(matchesTenant('tenant-a', undefined)).toBe(false);
    expect(matchesTenant(null, 'tenant-b')).toBe(true);
  });
});

describe('freshness', () => {
  const now = Date.parse('2026-10-26T12:00:00Z');
  it.each([null, undefined, 0, '', 'not-a-date'])('%s → sem dado, never zero', (v) => {
    expect(timeAgo(v, now)).toBe('sem dado');
  });
  it('formats epoch seconds and ISO strings', () => {
    expect(timeAgo(now / 1000 - 30, now)).toBe('há 30s');
    expect(timeAgo('2026-10-26T11:00:00Z', now)).toBe('há 1h');
    expect(timeAgo('2026-10-24T12:00:00Z', now)).toBe('há 2d');
  });
  it('future timestamps clamp to 0s instead of negative', () => {
    expect(timeAgo(now / 1000 + 60, now)).toBe('há 0s');
  });
});
