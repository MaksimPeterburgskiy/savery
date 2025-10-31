// Simple in-memory store for passing item lists between screens.
// Not persisted — suitable for short-lived navigation state in this app.

export type ItemRef = { id: string; name: string; price?: number; quantity?: number; alts?: ItemRef[] };

let items: ItemRef[] = [];

type Listener = (next: ItemRef[]) => void;
const listeners = new Set<Listener>();

export function getItems(): ItemRef[] {
  return items.slice();
}

export function setItems(next: ItemRef[]) {
  items = next.slice();
  for (const l of Array.from(listeners)) {
    try {
      l(getItems());
    } catch (e) {
      // swallow listener errors to avoid breaking the store
      // callers should handle their own errors
    }
  }
}

export function subscribe(cb: Listener) {
  listeners.add(cb);
  // return unsubscribe
  return () => {
    listeners.delete(cb);
  };
}
