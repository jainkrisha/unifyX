// Central API client — attaches JWT from localStorage to every request,
// surfaces 401/403 as thrown ApiError so every screen can render a clear
// "not authorized" message (not a blank screen or console-only log).

const BASE = '/api';

export class ApiError extends Error {
  status: number;
  detail: string;
  constructor(status: number, detail: string) {
    super(detail);
    this.status = status;
    this.detail = detail;
  }
}

function getToken(): string | null {
  return localStorage.getItem('unifyx_token');
}

async function request<T>(
  method: string,
  path: string,
  body?: unknown,
  extraHeaders?: Record<string, string>
): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...extraHeaders,
  };

  const res = await fetch(`${BASE}${path}`, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const json = await res.json();
      detail = json.detail ?? detail;
    } catch {
      // ignore parse error
    }
    throw new ApiError(res.status, detail);
  }

  // 204 No Content
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

// ---- Auth ----
export interface LoginResponse {
  access_token: string;
  token_type: string;
  user_id: number;
  email: string;
  role: 'RM' | 'MANAGER' | 'ADMIN';
}

export const authApi = {
  login: (email: string, password: string) =>
    request<LoginResponse>('POST', '/auth/login', { email, password }),
  me: () => request<{ id: number; email: string; role: string }>('GET', '/auth/me'),
};

// ---- Customers ----
export interface CustomerSummary {
  id: number;
  primary_name: string;
  pan_like: string | null;
  mobile: string | null;
  email: string | null;
  city: string | null;
  dob: string | null;
  relationship_value: number;
  rm_id: number | null;
}

export interface SourceRecord {
  id: number;
  source_system: string;
  source_customer_id: string;
  name: string;
  pan_like: string | null;
  mobile: string | null;
  email: string | null;
  city: string | null;
  dob: string | null;
  product_holdings: unknown;
  balance: number | null;
  raw_payload: unknown;
}

export interface FieldProvenance {
  id: number;
  field_name: string;
  value: string | null;
  source_system: string;
  confidence: number;
  is_resolved: boolean;
  resolution_method: string | null;
}

export interface CustomerDetail {
  customer: CustomerSummary;
  source_records: SourceRecord[];
  field_provenance: FieldProvenance[];
  match_reasons: unknown[];
}

export const customersApi = {
  list: (params?: { limit?: number; offset?: number; unmask?: boolean }) => {
    const q = new URLSearchParams();
    if (params?.limit) q.set('limit', String(params.limit));
    if (params?.offset) q.set('offset', String(params.offset));
    if (params?.unmask) q.set('unmask', 'true');
    return request<CustomerSummary[]>('GET', `/customers?${q}`);
  },
  get: (id: number, unmask = false) =>
    request<CustomerDetail>('GET', `/customers/${id}${unmask ? '?unmask=true' : ''}`),
};

// ---- Opportunities ----
export interface Opportunity {
  id: number;
  golden_customer_id: number;
  product_type: string;
  eligibility_passed: boolean;
  score: number;
  score_breakdown: Record<string, number> | null;
  reason_text: string | null;
  status: string;
  customer: {
    primary_name: string;
    pan_like: string | null;
    mobile: string | null;
    email: string | null;
  };
}

export const opportunitiesApi = {
  list: (params?: { limit?: number; offset?: number }) => {
    const q = new URLSearchParams();
    if (params?.limit) q.set('limit', String(params.limit));
    if (params?.offset) q.set('offset', String(params.offset));
    return request<Opportunity[]>('GET', `/opportunities?${q}`);
  },
};

// ---- Review Queue ----
export interface ReviewQueueItem {
  id: number;
  golden_customer_id: number | null;
  candidate_source_record_id: number;
  candidate_source_record_id_2: number | null;
  reason: string | null;
  context: unknown;
  status: 'PENDING' | 'RESOLVED' | 'REJECTED';
  candidate_source_record: {
    pan_like: string | null;
    mobile: string | null;
    email: string | null;
  };
}

export interface ResolveRequest {
  decision?: string;
  field_name?: string;
  winning_value?: string;
  winning_source_system?: string;
}

export const reviewQueueApi = {
  list: (params?: { limit?: number; offset?: number }) => {
    const q = new URLSearchParams();
    if (params?.limit) q.set('limit', String(params.limit));
    if (params?.offset) q.set('offset', String(params.offset));
    return request<ReviewQueueItem[]>('GET', `/review-queue?${q}`);
  },
  resolve: (id: number, body: ResolveRequest) =>
    request<{ status: string; id: number }>('POST', `/review-queue/${id}/resolve`, body),
};

// ---- Config ----
export interface ConfigEntry {
  id: number;
  category: string;
  key: string;
  value: unknown;
  version: number;
  updated_by: number | null;
}

export const configApi = {
  list: (category?: string) => {
    const q = category ? `?category=${encodeURIComponent(category)}` : '';
    return request<ConfigEntry[]>('GET', `/config${q}`);
  },
  update: (id: number, value: unknown) =>
    request<ConfigEntry>('PUT', `/config/${id}`, { value }),
};

// ---- Audit Log ----
export interface AuditLogEntry {
  id: number;
  actor_id: number | null;
  action: string;
  entity_type: string;
  entity_id: string | null;
  before_value: unknown;
  after_value: unknown;
  timestamp: string | null;
}

export const auditLogApi = {
  list: (params?: { entity_type?: string; limit?: number; offset?: number }) => {
    const q = new URLSearchParams();
    if (params?.entity_type) q.set('entity_type', params.entity_type);
    if (params?.limit) q.set('limit', String(params.limit));
    if (params?.offset) q.set('offset', String(params.offset));
    return request<AuditLogEntry[]>('GET', `/audit-log?${q}`);
  },
};

// ---- Admin ----
export interface PipelineSummary {
  status: string;
  summary: {
    deterministic_links?: number;
    probabilistic_links?: number;
    review_items_created?: number;
    [key: string]: unknown;
  };
}

export const adminApi = {
  runPipeline: () => request<PipelineSummary>('POST', '/admin/run-pipeline'),
};
