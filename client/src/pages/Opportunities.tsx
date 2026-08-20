import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { opportunitiesApi, Opportunity, ApiError } from '../api/client';
import { ApiErrorBanner } from '../components/ApiErrorBanner';

// Standalone opportunities list (all customers in scope)
export function Opportunities() {
  const { user } = useAuth();
  const [opps, setOpps] = useState<Opportunity[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<{ status?: number; detail: string } | null>(null);

  useEffect(() => {
    setLoading(true);
    opportunitiesApi.list({ limit: 200 })
      .then(setOpps)
      .catch(err => {
        if (err instanceof ApiError) setError({ status: err.status, detail: err.detail });
        else setError({ detail: String(err) });
      })
      .finally(() => setLoading(false));
  }, []);

  const scopeNote =
    user?.role === 'ADMIN' ? 'All opportunities (ADMIN scope)' :
    user?.role === 'MANAGER' ? 'Opportunities in your RM hierarchy' :
    'Opportunities for your assigned customers';

  return (
    <div className="page-content">
      <div className="page-header">
        <h1 className="page-title">Opportunities</h1>
        <p className="page-subtitle">{scopeNote} — read-only for all roles</p>
      </div>

      {error && <ApiErrorBanner status={error.status} detail={error.detail} />}
      {loading && <div style={{ display: 'flex', gap: 10, color: 'var(--c-text-3)' }}><span className="spinner" /> Loading…</div>}

      {!loading && !error && opps.length === 0 && (
        <div className="empty-state">
          <div className="empty-state-icon">🎯</div>
          <div className="empty-state-text">No opportunities found. Run the pipeline first.</div>
        </div>
      )}

      {!loading && !error && opps.length > 0 && (
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Customer</th>
                <th>Product</th>
                <th>Eligible</th>
                <th>Score</th>
                <th>Reason</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {opps.map(o => (
                <tr key={o.id}>
                  <td>
                    <div style={{ fontWeight: 500 }}>{o.customer.primary_name}</div>
                    <div className="mono" style={{ fontSize: 11, color: 'var(--c-text-3)' }}>{o.customer.pan_like}</div>
                  </td>
                  <td><strong>{o.product_type}</strong></td>
                  <td>
                    <span className={`chip ${o.eligibility_passed ? 'chip-green' : 'chip-red'}`}>
                      {o.eligibility_passed ? '✓' : '✗'}
                    </span>
                  </td>
                  <td>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                      <span style={{ fontWeight: 600 }}>{o.score.toFixed(0)}</span>
                      <div className="score-bar-track" style={{ width: 60 }}>
                        <div className="score-bar-fill" style={{ width: `${Math.min(100, o.score)}%` }} />
                      </div>
                    </div>
                  </td>
                  <td style={{ maxWidth: 260, fontSize: 12, color: 'var(--c-text-2)' }}>{o.reason_text ?? '—'}</td>
                  <td>
                    <Link to={`/customers/${o.golden_customer_id}`} className="btn btn-outline btn-sm">
                      View →
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
