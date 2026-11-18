// @vitest-environment jsdom
import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, describe, expect, it, vi } from 'vitest';
import AiView from './AiView';

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

let root: Root | null = null;
let host: HTMLElement | null = null;
const flush = () => act(async () => { await new Promise((r) => setTimeout(r, 0)); });
afterEach(async () => {
  await act(async () => { root?.unmount(); });
  host?.remove();
  root = host = null;
  vi.unstubAllGlobals();
});

const json = (body: unknown) => new Response(JSON.stringify(body), { status: 200, headers: { 'content-type': 'application/json' } });
const kind = { total: 4, by_outcome: { ok: 3 }, divergence_rate: 0.25, feedback: {}, useful_rate: null, cost_usd: 1, cost_missing: 0, avg_latency_ms: null, failure_rate: 0, mttr_minutes: { useful: null, other: null } };
const metrics = { window_days: 30, budget: { month_cost_usd: 3.5, limit_usd: 50 }, by_kind: { incident_analysis: kind } };
const decision = { id: 9, kind: 'incident_analysis', customer_id: 'Cavan', ticket_id: '77', outcome: 'ok', model: 'm', rule_value: 'MEDIUM', model_value: 'CRITICAL', divergent: true, feedback: null, cost_usd: 0.01, created_at: '2026-11-18T12:00:00Z' };

async function mount(decisions: unknown[]) {
  const f = vi.fn(async (url: string, init?: RequestInit) => {
    if (url.includes('/feedback')) return json({ id: 9, feedback: JSON.parse(String(init?.body)).verdict, feedback_at: 'x' });
    return json(url.includes('/metrics') ? metrics : decisions);
  });
  vi.stubGlobal('fetch', f);
  host = document.createElement('div');
  document.body.append(host);
  root = createRoot(host);
  await act(async () => { root!.render(<AiView />); });
  await flush();
  return f;
}

describe('AiView', () => {
  it('shows rates as percent, "—" for null and an empty state for a missing kind', async () => {
    await mount([decision]);
    expect(host!.textContent).toContain('25%');
    expect(host!.textContent).toContain('Sem decisões na janela.');
    expect(host!.textContent).toContain('NOC (Zabbix)');
    expect(host!.textContent).toContain('SOC (Wazuh)');
  });
  it('POSTs the verdict and the row shows "útil"', async () => {
    const f = await mount([decision]);
    const btn = host!.querySelector('button[aria-label="Útil: decisão 9"]') as HTMLButtonElement;
    await act(async () => { btn.click(); });
    await flush();
    const call = f.mock.calls.find((c) => String(c[0]).includes('/feedback'))!;
    expect(call[1]!.method).toBe('POST');
    expect(call[1]!.body).toBe('{"verdict":"useful"}');
    expect(host!.querySelector('tbody')!.textContent).toContain('útil');
  });
  it('null cost renders "—", never 0', async () => {
    await mount([{ ...decision, cost_usd: null }]);
    const cells = [...host!.querySelectorAll('tbody td')].map((td) => td.textContent);
    expect(cells).toContain('—');
    expect(host!.querySelector('tbody')!.textContent).not.toContain('US$');
  });
  it('divergent filter refetches with divergent=true', async () => {
    const f = await mount([decision]);
    const btn = [...host!.querySelectorAll('button')].find((b) => b.textContent === 'Só divergentes')!;
    await act(async () => { btn.click(); });
    await flush();
    expect(f.mock.calls.some((c) => String(c[0]).includes('divergent=true'))).toBe(true);
  });
});
