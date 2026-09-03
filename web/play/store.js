export function createStore(initialState) {
  let state = structuredClone(initialState);
  const listeners = new Set();
  return {
    getState: () => state,
    setState(update, { notify = true } = {}) {
      state = typeof update === 'function' ? update(state) : { ...state, ...update };
      if (notify) listeners.forEach(listener => listener(state));
    },
    subscribe(listener) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
  };
}
