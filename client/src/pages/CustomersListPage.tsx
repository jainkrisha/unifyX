import React, { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { customersApi, CustomerSummary, ApiError } from '../api/client';
import { ApiErrorBanner } from '../components/ApiErrorBanner';

const DEPT_LABELS: Record<string, string> = {
  EQUITY: 'Equity', MF: 'Mutual Funds', INSURANCE: 'Insurance', LOANS: 'Loans', WEALTH: 'Wealth',
};

export function CustomersListPage() {
  const { user } = useAuth();
  const [searchParams] = useSearchParams();
  const deptFilter = searchParams.get('dept');

  const [customers, setCustomers] = useState<CustomerSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<{ status?: number; detail: string } | null>(null);

  const scopeNote =
    user?.role === 'ADMIN' ? 'All customers (ADMIN scope)' :
    user?.role === 'MANAGER' ? 'Customers in your RM hierarchy (MANAGER scope)' :
    'Your assigned customers (RM scope)';

  useEffect(() => {
    setLoading(true);
    setError(null);
    customersApi.list({ limit: 200 })
      .then(setCustomers)
      .catch(err => {
        if (err instanceof ApiError) setError({ status: err.status, detail: err.detail });
        else setError({ detail: String(err) });
      })
      .finally(() => setLoading(false));
  }, []);

  const displayed = customers; // all scoping done server-side

  return (
    <div className="page-content">
      <div className="page-header" style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
        <div style={{ flex: 1 }}>
          <h1 className="page-title">
            Customers
            {deptFilter && <span style={{ fontWeight: 400, color: 'var(--c-text-3)', fontSize: 16 }}> — {DEPT_LABELS[deptFilter] ?? deptFilter}</span>}
          </h1>
          <p className="page-subtitle">{scopeNote}</p>
        </div>
        {deptFilter && (
          <Link to="/customers" className="btn btn-ghost btn-sm">✕ Clear filter</Link>
        )}
      </div>

      {error && <ApiErrorBanner status={error.status} detail={error.detail} />}

      {loading && (
        <div style={{ display: 'flex', gap: 10, color: 'var(--c-text-3)', padding: '20px 0' }}>
          <span className="spinner" /> Loading customers…
        </div>
      )}

      {!loading && !error && displayed.length === 0 && (
        <div className="empty-state">
          <div className="empty-state-icon">👤</div>
          <div className="empty-state-text">No customers in your scope.</div>
        </div>
      )}

      {!loading && !error && displayed.length > 0 && (
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>PAN-like ID</th>
                <th>Mobile</th>
                <th>Email</th>
                <th>City</th>
                <th>Rel. Value</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {displayed.map(c => (
                <tr key={c.id}>
                  <td><strong>{c.primary_name}</strong></td>
                  <td><span className="mono">{c.pan_like ?? '—'}</span></td>
                  <td><span className="mono">{c.mobile ?? '—'}</span></td>
                  <td><span className="mono">{c.email ?? '—'}</span></td>
                  <td>{c.city ?? '—'}</td>
                  <td>
                    {c.relationship_value != null
                      ? `₹${Number(c.relationship_value).toLocaleString('en-IN')}`
                      : '—'}
                  </td>
                  <td>
                    <Link
                      to={`/customers/${c.id}`}
                      className="btn btn-outline btn-sm"
                      id={`customer-link-${c.id}`}
                    >
                      View 360 →
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {!loading && !error && (
        <div style={{ marginTop: 10, fontSize: 12, color: 'var(--c-text-4)' }}>
          {displayed.length} record{displayed.length !== 1 ? 's' : ''} — PII masked by default; only Admin can unmask.
        </div>
      )}
    </div>
  );
}
