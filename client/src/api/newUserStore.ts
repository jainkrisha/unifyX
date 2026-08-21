/**
 * In-memory pub/sub store for newly-added simulated users.
 *
 * This lets the DepartmentsPage push a user and the CustomersListPage
 * (or any other page) subscribe to changes — making new users appear
 * "real-time" across RM, Manager, and Admin views in the same session.
 *
 * State resets on page refresh (session-scoped).
 */

export interface NewUser {
  /** Unique ID for this simulated user (timestamp-based) */
  id: number;
  primary_name: string;
  pan_like: string;
  mobile: string;
  email: string;
  city: string;
  relationship_value: number;
  /** The user-id that was entered when running the pipeline */
  pipeline_user_id: string;
  added_at: string; // ISO timestamp
}

type Listener = (users: NewUser[]) => void;

// Module-level state — survives across components, resets on page refresh
const newUsers: NewUser[] = [];
const listeners = new Set<Listener>();

function notify() {
  const snapshot = [...newUsers];
  listeners.forEach(fn => fn(snapshot));
}

/** Add a new simulated user to the store and notify all subscribers. */
export function addNewUser(user: Omit<NewUser, 'id' | 'added_at'>): NewUser {
  const entry: NewUser = {
    ...user,
    id: Date.now() + Math.floor(Math.random() * 1000),
    added_at: new Date().toISOString(),
  };
  // Prepend so newest is first
  newUsers.unshift(entry);
  notify();
  return entry;
}

/** Get current list of new users (newest first). */
export function getNewUsers(): NewUser[] {
  return [...newUsers];
}

/**
 * Subscribe to changes. Returns an unsubscribe function.
 * The callback is called immediately with the current state.
 */
export function subscribe(callback: Listener): () => void {
  listeners.add(callback);
  // Deliver current state immediately
  callback([...newUsers]);
  return () => { listeners.delete(callback); };
}
