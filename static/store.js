function createStore(initialState) {
  let state = { ...initialState };
  const listeners = new Set();

  function get() {
    return state;
  }

  function set(patch) {
    const prevState = state;
    const nextPatch = typeof patch === "function" ? patch(state) : patch;
    state = { ...state, ...nextPatch };
    listeners.forEach((listener) => listener(state, prevState));
  }

  function subscribe(listener) {
    listeners.add(listener);
    listener(state, state);
    return () => listeners.delete(listener);
  }

  function select(keys, listener) {
    let first = true;
    return subscribe((next, prev) => {
      const changed = first || keys.some((key) => next[key] !== prev[key]);
      first = false;
      if (changed) listener(next, prev);
    });
  }

  return { get, set, subscribe, select };
}
