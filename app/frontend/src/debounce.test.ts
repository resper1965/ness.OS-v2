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

  it('cada chamada reinicia a espera (não é throttle)', () => {
    vi.useFakeTimers();
    const fn = vi.fn();
    const run = debounce(fn, 2000);
    run();
    vi.advanceTimersByTime(1500);
    run();
    vi.advanceTimersByTime(1500);
    expect(fn).not.toHaveBeenCalled();
    vi.advanceTimersByTime(500);
    expect(fn).toHaveBeenCalledTimes(1);
  });

  it('rajada contínua dispara no máximo após maxMs', () => {
    vi.useFakeTimers();
    const fn = vi.fn();
    const run = debounce(fn, 2000, 10_000);
    for (let t = 0; t < 10_000; t += 1000) {
      run();
      vi.advanceTimersByTime(1000);
    }
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
