/**
 * Pool of hardcoded simulated user profiles for the pipeline demo.
 * Each session picks randomly without repeats; pool resets on page refresh.
 */

export interface SimulatedUserProfile {
  name: string;
  email: string;
  phone: string;
  pan: string;
  city: string;
  relationship_value: number;
  /** Which departments this user was matched across */
  auditLog: { dept: string; action: string; date: string }[];
  review: string;
}

const TODAY = new Date().toISOString().slice(0, 10); // YYYY-MM-DD

const PROFILE_POOL: SimulatedUserProfile[] = [
  {
    name: 'Rahul Sharma',
    email: 'rahul.sharma@example.com',
    phone: '+91-9876543210',
    pan: 'ABCDE1234F',
    city: 'Mumbai',
    relationship_value: 425000,
    auditLog: [
      { dept: 'Equity', action: 'Matched by PAN', date: TODAY },
      { dept: 'Mutual Funds', action: 'Matched by Email & Phone', date: TODAY },
    ],
    review: 'Matched on PAN successfully across 2 source systems.',
  },
  {
    name: 'Priya Patel',
    email: 'priya.patel@example.com',
    phone: '+91-9823456781',
    pan: 'BQRPP4567G',
    city: 'Ahmedabad',
    relationship_value: 780000,
    auditLog: [
      { dept: 'Insurance', action: 'Matched by PAN', date: TODAY },
      { dept: 'Loans', action: 'Matched by Mobile & DOB', date: TODAY },
      { dept: 'Wealth', action: 'Matched by Email', date: TODAY },
    ],
    review: 'PAN match confirmed across Insurance & Loans; Email match added Wealth.',
  },
  {
    name: 'Amit Deshmukh',
    email: 'amit.desh@example.com',
    phone: '+91-9912345678',
    pan: 'CXYAD8901H',
    city: 'Pune',
    relationship_value: 310000,
    auditLog: [
      { dept: 'Equity', action: 'Matched by PAN', date: TODAY },
      { dept: 'Insurance', action: 'Matched by PAN & Name fuzzy', date: TODAY },
    ],
    review: 'Deterministic PAN match for Equity; fuzzy name match confirmed for Insurance.',
  },
  {
    name: 'Sneha Iyer',
    email: 'sneha.iyer@example.com',
    phone: '+91-9834567890',
    pan: 'DKLSI2345J',
    city: 'Chennai',
    relationship_value: 560000,
    auditLog: [
      { dept: 'Mutual Funds', action: 'Matched by PAN', date: TODAY },
      { dept: 'Wealth', action: 'Matched by Phone & Email', date: TODAY },
    ],
    review: 'PAN matched in Mutual Funds; Phone+Email confirmed in Wealth system.',
  },
  {
    name: 'Vikram Singh',
    email: 'vikram.singh@example.com',
    phone: '+91-9945612378',
    pan: 'EFGVS6789K',
    city: 'Delhi',
    relationship_value: 1250000,
    auditLog: [
      { dept: 'Equity', action: 'Matched by PAN', date: TODAY },
      { dept: 'Loans', action: 'Matched by PAN', date: TODAY },
      { dept: 'Mutual Funds', action: 'Matched by Email & Mobile', date: TODAY },
    ],
    review: 'High-value customer matched across 3 systems via PAN and contact info.',
  },
  {
    name: 'Ananya Reddy',
    email: 'ananya.r@example.com',
    phone: '+91-9801234567',
    pan: 'FHJAR3456L',
    city: 'Hyderabad',
    relationship_value: 680000,
    auditLog: [
      { dept: 'Insurance', action: 'Matched by PAN', date: TODAY },
      { dept: 'Equity', action: 'Matched by Mobile', date: TODAY },
    ],
    review: 'PAN match in Insurance; Mobile-based match in Equity confirmed.',
  },
  {
    name: 'Rajesh Kumar',
    email: 'rajesh.kumar@example.com',
    phone: '+91-9867890123',
    pan: 'GMNRK7890M',
    city: 'Bangalore',
    relationship_value: 490000,
    auditLog: [
      { dept: 'Wealth', action: 'Matched by PAN', date: TODAY },
      { dept: 'Loans', action: 'Matched by Email & Name', date: TODAY },
    ],
    review: 'PAN deterministic match in Wealth; Email+Name confirmed in Loans.',
  },
  {
    name: 'Meera Joshi',
    email: 'meera.joshi@example.com',
    phone: '+91-9756781234',
    pan: 'HPQMJ1234N',
    city: 'Jaipur',
    relationship_value: 375000,
    auditLog: [
      { dept: 'Mutual Funds', action: 'Matched by PAN', date: TODAY },
      { dept: 'Insurance', action: 'Matched by PAN & DOB', date: TODAY },
    ],
    review: 'PAN match across MF and Insurance; DOB corroborates Insurance match.',
  },
  {
    name: 'Arjun Nair',
    email: 'arjun.nair@example.com',
    phone: '+91-9712345678',
    pan: 'IXYAN5678P',
    city: 'Kochi',
    relationship_value: 920000,
    auditLog: [
      { dept: 'Equity', action: 'Matched by PAN', date: TODAY },
      { dept: 'Wealth', action: 'Matched by PAN', date: TODAY },
      { dept: 'Insurance', action: 'Matched by Mobile & Email', date: TODAY },
    ],
    review: 'PAN match in Equity & Wealth; Mobile+Email match added Insurance.',
  },
  {
    name: 'Kavita Mehta',
    email: 'kavita.mehta@example.com',
    phone: '+91-9698765432',
    pan: 'JLSKM9012Q',
    city: 'Kolkata',
    relationship_value: 540000,
    auditLog: [
      { dept: 'Loans', action: 'Matched by PAN', date: TODAY },
      { dept: 'Mutual Funds', action: 'Matched by Phone & Name', date: TODAY },
    ],
    review: 'Deterministic PAN match in Loans; Phone+Name probabilistic match in MF.',
  },
];

// Session-scoped set of already-used profile indices
const usedIndices = new Set<number>();

/**
 * Pick a random unused profile from the pool.
 * Returns null when all profiles have been exhausted this session.
 */
export function getNextSimulatedUser(): SimulatedUserProfile | null {
  const available = PROFILE_POOL
    .map((_, i) => i)
    .filter(i => !usedIndices.has(i));

  if (available.length === 0) return null;

  const pick = available[Math.floor(Math.random() * available.length)];
  usedIndices.add(pick);

  // Return a fresh copy so callers can't mutate the pool
  return { ...PROFILE_POOL[pick], auditLog: PROFILE_POOL[pick].auditLog.map(a => ({ ...a })) };
}

/** How many profiles remain unused this session */
export function remainingProfiles(): number {
  return PROFILE_POOL.length - usedIndices.size;
}
