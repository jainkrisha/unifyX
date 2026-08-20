import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { reviewQueueApi, ReviewQueueItem, ResolveRequest, ApiError } from '../api/client';
import { ApiErrorBanner } from '../components/ApiErrorBanner';

const STATUS_COLOR: Record<string, string> = {
  PENDING:  'chip-amber',
  RESOLVED: 'chip-green',
  REJECTED: 'chip-red',
};

function ResolveForm({
  item,
  onResolved,
}: {
  item: ReviewQueueItem;
  onResolved: (id: number) => void;
}) {
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  // For match-type items (candidate_source_record_id_2 present): MATCH / NO_MATCH decision
  // For field conflict items (golden_customer_id present, no second candidate): field resolution
  const isMatchReview = item.candidate_source_record_id_2 != null;

  const [decision, setDecision] = useState<string>('MATCH');
  const [fieldName, setFieldName] = useState('');
  const [winningValue, setWinningValue] = useState('');
  const [winningSource, setWinningSource] = useState('');

  async function submit() {
    setErr(null);
    setLoading(true);
    const body: ResolveRequest = isMatchReview
      ? { decision }
      : { field_name: fieldName, winning_value: winningValue, winning_source_system: winningSource };
    try {
      await reviewQueueApi.resolve(item.id, body);
      onResolved(item.id);
    } catch (e) {
      if (e instanceof ApiError) setErr(`${e.status}: ${e.detail}`);
      else setErr(String(e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{ marginTop: 12, padding: '12px 14px', background: 'var(--c-surface)', borderRadius: 'var(--radius)', border: '1px solid var(--c-border)' }}>
      <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 10, color: 'var(--c-text-2)' }}>
        Admin: Resolve this item
      </div>
      {err && <div className="banner banner-error" style={{ marginBottom: 10, fontSize: 12 }}>{err}</div>}
      {isMatchReview ? (
        <div style={{ display: 'flex', gap: 8 }}>
          <button className={`btn btn-sm ${decision === 'MATCH' ? 'btn-primary' : 'btn-outline'}`} onClick={() => setDecision('MATCH')}>
            MATCH
          </button>
          <button className={`btn btn-sm ${decision === 'NO_MATCH' ? 'btn-danger' : 'btn-outline'}`} onClick={() => setDecision('NO_MATCH')}>
            NO MATCH
          </button>
          <button className="btn btn-primary btn-sm" disabled={loading} onClick={submit} style={{ marginLeft: 'auto' }}>
            {loading ? <span className="spinner" /> : 'Confirm'}
          </button>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <input className="form-input" placeholder="Field name (e.g. mobile)" value={fieldName} onChange={e => setFieldName(e.target.value)} />
          <input className="form-input" placeholder="Winning value" value={winningValue} onChange={e => setWinningValue(e.target.value)} />
          <input className="form-input" placeholder="Winning source system (e.g. EQUITY)" value={winningSource} onChange={e => setWinningSource(e.target.value)} />
          <button className="btn btn-primary btn-sm" disabled={loading} onClick={submit} style={{ alignSelf: 'flex-end' }}>
            {loading ? <span className="spinner" /> : 'Resolve'}
          </button>
        </div>
      )}
    </div>
  );
}

export function ReviewQueuePage() {
  const { isAdmin } = useAuth();
  const [items, setItems] = useState<ReviewQueueItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<{ status?: number; detail: string } | null>(null);
  const [resolvedIds, setResolvedIds] = useState<Set<number>>(new Set());
  const [expandedId, setExpandedId] = useState<number | null>(null);

  function load() {
    setLoading(true);
    reviewQueueApi.list({ limit: 100 })
      .then(setItems)
      .catch(err => {
        if (err instanceof ApiError) setError({ status: err.status, detail: err.detail });
        else setError({ detail: String(err) });
      })
      .finally(() => setLoading(false));
  }

  useEffect(load, []);

  function handleResolved(id: number) {
    setResolvedIds(prev => new Set([...prev, id]));
    setExpandedId(null);
    // Reload after brief delay so the resolved state is reflected
    setTimeout(load, 400);
  }

  const pending  = items.filter(i => i.status === 'PENDING');
  const resolved = items.filter(i => i.status !== 'PENDING');

  return (
    <div className="page-content">
      <div className="page-header" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <h1 className="page-title">Review Queue</h1>
          <p className="page-subtitle">
            {isAdmin ? 'All review items (ADMIN — can resolve)' : 'Review items in your scope (read-only — only Admin can resolve)'}
          </p>
        </div>
        <button className="btn btn-outline btn-sm" onClick={load}>↻ Refresh</button>
      </div>

      {!isAdmin && (
        <div className="banner banner-info" style={{ marginBottom: 16 }}>
          <span className="banner-icon">ℹ️</span>
          <span>You can view these items but cannot resolve them. The resolve button is only shown to Admins, and the backend will also 403 non-Admin calls to <code>POST /review-queue/:id/resolve</code>.</span>
        </div>
      )}

      {error && <ApiErrorBanner status={error.status} detail={error.detail} />}

      {loading && (
        <div style={{ display: 'flex', gap: 10, color: 'var(--c-text-3)', padding: '20px 0' }}>
          <span className="spinner" /> Loading…
        </div>
      )}

      {!loading && !error && (
        <>
          {pending.length === 0 && resolved.length === 0 && (
            <div className="empty-state">
              <div className="empty-state-icon">✅</div>
              <div className="empty-state-text">Review queue is empty.</div>
            </div>
          )}

          {pending.length > 0 && (
            <div style={{ marginBottom: 24 }}>
              <div className="section-heading" style={{ marginBottom: 12 }}>
                Pending ({pending.length})
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                {pending.map(item => (
                  <ReviewItem
                    key={item.id}
                    item={item}
                    isAdmin={isAdmin}
                    expanded={expandedId === item.id}
                    onToggle={() => setExpandedId(expandedId === item.id ? null : item.id)}
                    onResolved={handleResolved}
                  />
                ))}
              </div>
            </div>
          )}

          {resolved.length > 0 && (
            <div>
              <div className="section-heading" style={{ marginBottom: 12 }}>
                Resolved / Rejected ({resolved.length})
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {resolved.map(item => (
                  <ReviewItem
                    key={item.id}
                    item={item}
                    isAdmin={false}
                    expanded={false}
                    onToggle={() => {}}
                    onResolved={() => {}}
                  />
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}

function ReviewItem({
  item, isAdmin, expanded, onToggle, onResolved,
}: {
  item: ReviewQueueItem;
  isAdmin: boolean;
  expanded: boolean;
  onToggle: () => void;
  onResolved: (id: number) => void;
}) {
  const isPending = item.status === 'PENDING';
  const isMatchReview = item.candidate_source_record_id_2 != null;

  return (
    <div className="card card-sm" id={`review-item-${item.id}`} style={{ border: isPending ? '1px solid var(--c-border)' : '1px solid var(--c-border)' }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12, flexWrap: 'wrap' }}>
        <div style={{ flex: 1 }}>
          {/* Status + type */}
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 8, flexWrap: 'wrap' }}>
            <span className={`chip ${STATUS_COLOR[item.status]}`}>{item.status}</span>
            <span className="chip chip-grey">{isMatchReview ? 'Match decision' : 'Field conflict'}</span>
            <span style={{ fontSize: 11, color: 'var(--c-text-4)' }}>ID #{item.id}</span>
            {item.golden_customer_id && (
              <Link to={`/customers/${item.golden_customer_id}`} className="chip chip-blue" style={{ fontSize: 11 }}>
                Customer #{item.golden_customer_id}
              </Link>
            )}
          </div>

          {/* Reason */}
          {item.reason && (
            <div style={{ fontSize: 13, color: 'var(--c-text-2)', marginBottom: 10 }}>
              {item.reason}
            </div>
          )}

          {/* Candidate values side by side */}
          <div className="conflict-grid">
            <div className="conflict-side">
              <div className="conflict-label">Candidate A (record #{item.candidate_source_record_id})</div>
              <div className="conflict-value mono" style={{ fontSize: 12 }}>
                PAN: {item.candidate_source_record.pan_like ?? '—'}<br />
                Mobile: {item.candidate_source_record.mobile ?? '—'}<br />
                Email: {item.candidate_source_record.email ?? '—'}
              </div>
            </div>
            {item.candidate_source_record_id_2 && (
              <div className="conflict-side">
                <div className="conflict-label">Candidate B (record #{item.candidate_source_record_id_2})</div>
                <div className="conflict-value mono" style={{ fontSize: 12, color: 'var(--c-text-3)' }}>
                  Data from second candidate record
                </div>
              </div>
            )}
          </div>

          {/* Context (collapsed) */}
          {item.context && (
            <details className="json-expand" style={{ marginTop: 10 }}>
              <summary>Context detail</summary>
              <pre>{JSON.stringify(item.context, null, 2)}</pre>
            </details>
          )}

          {/* Admin resolve form */}
          {isAdmin && isPending && (
            expanded ? (
              <ResolveForm item={item} onResolved={onResolved} />
            ) : (
              <div style={{ marginTop: 12 }}>
                <button
                  className="btn btn-primary btn-sm"
                  id={`resolve-btn-${item.id}`}
                  onClick={onToggle}
                >
                  Resolve ↓
                </button>
              </div>
            )
          )}

          {/* Non-admin: explain why no resolve button */}
          {!isAdmin && isPending && (
            <div style={{ marginTop: 10, fontSize: 12, color: 'var(--c-text-4)' }}>
              🔒 Only Admin can resolve — backend returns 403 for non-Admin
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
