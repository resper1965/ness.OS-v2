/**
 * Agrupa chamadas seguidas numa só, `ms` depois da última. `maxMs` impede que uma rajada
 * contínua adie a execução para sempre. `cancel` limpa o que está pendente.
 */
export function debounce(fn: () => void, ms: number, maxMs = 10_000) {
  let t: ReturnType<typeof setTimeout> | undefined;
  let first = 0;
  const fire = () => {
    clearTimeout(t);
    first = 0;
    fn();
  };
  const run = () => {
    const now = Date.now();
    if (!first) first = now;
    clearTimeout(t);
    t = setTimeout(fire, Math.max(0, Math.min(ms, first + maxMs - now)));
  };
  run.cancel = () => {
    clearTimeout(t);
    first = 0;
  };
  return run;
}
