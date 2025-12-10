// Simple in-memory store for passing data between screens.
// Not persisted — suitable for short-lived navigation state in this app.

// ============================================================================
// Flow State Persistence
// ============================================================================
export {
  saveFlowState,
  loadFlowState,
  getActiveFlow,
  clearFlowState,
  getTargetScreen,
  getTargetScreenForActiveJob,
  createInitialFlowState,
  updateFlowState,
} from './flowState';

export type { FlowState, FlowStep, JobType } from './flowState';

// ============================================================================
// ACTUAL FUNCTIONALITY - Cross-screen ID storage for API integration
// ============================================================================

// ----- List ID storage -----
// Holds the current shopping list ID for cross-screen access
let currentListId: string | null = null;

export function getListId(): string | null {
  return currentListId;
}

export function setListId(id: string | null): void {
  currentListId = id;
}

// ----- Route Plan ID storage -----
// Holds the current route plan ID for cross-screen access
let currentRoutePlanId: string | null = null;

export function getRoutePlanId(): string | null {
  return currentRoutePlanId;
}

export function setRoutePlanId(id: string | null): void {
  currentRoutePlanId = id;
}

// ============================================================================
// TEMP: Demo data and mock store logic for UI visualization until API integration is complete
// ============================================================================

export type ItemRef = { id: string; name: string; price?: number; quantity?: number; alts?: ItemRef[] };
export type StoreRef = { id: string; name: string; distance?: string; totalCost?: number; items: ItemRef[] };

let items: ItemRef[] = [];
let stores: StoreRef[] = [
    { id: '1', name: 'Walmart', distance: '2.1mi', items: [] },
    { id: '2', name: 'Target', distance: '3.6mi', items: [] },
    { id: '3', name: 'Trader Joes', distance: '5.4mi', items: [] },
];

type Listener = (next: ItemRef[]) => void;
const listeners = new Set<Listener>();

type StoreListener = (next: StoreRef[]) => void;
const storeListeners = new Set<StoreListener>();

export function getItems(): ItemRef[] {
  return items.slice();
}

export function getStores(): StoreRef[] {
    return stores.filter(s => (s.items?.length ?? 0) > 0);
}

export function setStores(next: StoreRef[]) {
  stores = next.map(s => ({ ...s }));
  for (const l of Array.from(storeListeners)) {
    try {
      l(getStores());
    } catch (e) {
      // swallow
    }
  }
}

export function subscribeStores(cb: StoreListener) {
  storeListeners.add(cb);
  return () => {
    // remove listener; ignore the boolean return value from Set.delete
    storeListeners.delete(cb);
  };
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

  // Simple processing: assign each incoming item to exactly one store (randomly)
  // and compute that store's totalCost. This imitates a store-match step for
  // visualization purposes.
  const nextStores: StoreRef[] = stores.map((s) => ({ ...s, items: [], totalCost: 0 }));

  if (items.length > 0) {
    for (const it of items) {
      // choose a random store index for this item
      const idx = Math.floor(Math.random() * nextStores.length);
      const store = nextStores[idx];
      // apply a small deterministic-ish modifier so different stores show
      // slightly different prices (use store id as number when possible)
      const modifier = 1 + Number(store.id || 0) * 0.02;
      const price = typeof it.price === 'number' ? Number((it.price * modifier).toFixed(2)) : it.price;
      const itemCopy: ItemRef = { ...it, price };
      store.items = [...store.items, itemCopy];
      store.totalCost = (store.totalCost ?? 0) + (price ?? 0);
    }
  }

  setStores(nextStores);
}

export function subscribe(cb: Listener) {
  listeners.add(cb);
  // return unsubscribe
  return () => {
    listeners.delete(cb);
  };
}

// ============================================================================
// end of TEMP: Demo data and mock store logic
// ============================================================================
