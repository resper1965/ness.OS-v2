/** Agrupa chamadas seguidas numa só, `ms` depois da última. `cancel` limpa o que está pendente. */
export function debounce(fn: () => void, ms: number) {
  let t: ReturnType<typeof setTimeout> | undefined;
  const run = () => {
    clearTimeout(t);
    t = setTimeout(fn, ms);
  };
  run.cancel = () => clearTimeout(t);
  return run;
}
