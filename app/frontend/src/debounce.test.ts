import { afterEach, describe, expect, it, vi } from 'vitest';
import { debounce } from './debounce';

afterEach(() => vi.useRealTimers());

describe('debounce', () => {
  it('rajada de 50 chamadas vira uma só (#231)', () => {
    vi.useFakeTimers();
    const fn = vi.fn();
    const run = debounce(fn, 2000);
    for (let i = 0; i < 50; i++) run();
    vi.advanceTimersByTime(1999);
    expect(fn).not.toHaveBeenCalled();
    vi.advanceTimersByTime(1);
    expect(fn).toHaveBeenCalledTimes(1);
  });

  it('cancel descarta a chamada pendente', () => {
    vi.useFakeTimers();
    const fn = vi.fn();
    const run = debounce(fn, 2000);
    run();
    run.cancel();
    vi.advanceTimersByTime(5000);
    expect(fn).not.toHaveBeenCalled();
  });
});
