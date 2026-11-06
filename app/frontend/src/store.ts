import { useSyncExternalStore } from 'react';

// Estado fora do React: hooks e telas só leem; a lógica é testável sem DOM.
export interface Store<S> {
  get: () => S;
  set: (patch: Partial<S>) => void;
  subscribe: (fn: () => void) => () => void;
}

export function createStore<S>(initial: S): Store<S> {
  let state = initial;
  const subs = new Set<() => void>();
  return {
    get: () => state,
    set: (patch) => { state = { ...state, ...patch }; subs.forEach((f) => f()); },
    subscribe: (fn) => { subs.add(fn); return () => { subs.delete(fn); }; },
  };
}

export const useStore = <S,>(store: Store<S>): S => useSyncExternalStore(store.subscribe, store.get, store.get);
