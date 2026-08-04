// A tiny immutable store for URL-backed dashboard state.

export function createStore(initialState) {
    let current = Object.freeze({...initialState});
    const listeners = new Set();

    return {
        getState() {
            return current;
        },
        dispatch(patch, metadata = {}) {
            const previous = current;
            const changes = typeof patch === 'function' ? patch(previous) : patch;
            current = Object.freeze({...previous, ...changes});
            for (const listener of listeners) listener(current, previous, metadata);
            return current;
        },
        subscribe(listener) {
            listeners.add(listener);
            return () => listeners.delete(listener);
        },
    };
}
