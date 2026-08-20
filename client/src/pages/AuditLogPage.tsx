import React, { useEffect, useState } from 'react';
import { auditLogApi, AuditLogEntry, ApiError } from '../api/client';
import { ApiErrorBanner } from '../components/ApiErrorBanner';

function fmtTime(ts: string | null): string {
  if (!ts) return '—';
  return new Date(ts).toLocaleString('en-IN', { timeZone: 'Asia/Kolkata', hour12: false });
}

const ENTITY_COLORS: Record<string, string> = {
  ConfigEntry:      'chip-blue',
  ReviewQueueItem:  'chip-amber',
  CustomerLink:     'chip-green',
  GoldenCustomer:   'chip-teal',
  FieldProvenance:  'chip-purple',
};

export function AuditLogPage() {
  const [entries, setEntries] = useState<AuditLogEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<{ status?: number; detail: string } | null>(null);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [entityFilter, setEntityFilter] = useState('');

  function load() {
    setLoading(true);
    setError(null);
    auditLogApi.list({ limit: 100, entity_type: entityFilter || undefined })
      .then(setEntries)
      .catch(err => {
        if (err instanceof ApiError) setError({ status: err.status, detail: err.detail });
        else setError({ detail: String(err) });
      })
      .finally(() => setLoading(false));
  }

  useEffect(load, [entityFilter]);

  const entityTypes = Array.from(new Set(entries.map(e => e.entity_type)));

  return (
    <div className="page-content">
      <div className="page-header" style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
        <div style={{ flex: 1 }}>
          <h1 className="page-title">Audit Log</h1>
          <p className="page-subtitle">Every change tracked — Admin only view</p>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <select
            id="audit-entity-filter"
            className="form-input"
            style={{ width: 200 }}
            value={entityFilter}
            onChange={e => setEntityFilter(e.target.value)}
          >
            <option value="">All entity types</option>
            {entityTypes.map(t => <option key={t} value={t}>{t}</option>)}
          </select>
          <button className="btn btn-outline btn-sm" onClick={load}>↻ Refresh</button>
        </div>
      </div>

      {error && <ApiErrorBanner status={error.status} detail={error.detail} />}

      {loading && (
        <div style={{ display: 'flex', gap: 10, color: 'var(--c-text-3)', padding: '20px 0' }}>
          <span className="spinner" /> Loading audit log…
        </div>
      )}

      {!loading && !error && entries.length === 0 && (
        <div className="empty-state">
          <div className="empty-state-icon">📋</div>
          <div className="empty-state-text">No audit log entries found.</div>
        </div>
      )}

      {!loading && !error && entries.length > 0 && (
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th style={{ width: 44 }}>#</th>
                <th style={{ width: 60 }}>Actor</th>
                <th style={{ width: 110 }}>Action</th>
                <th>Entity</th>
                <th>Entity ID</th>
                <th style={{ width: 180 }}>Timestamp</th>
                <th style={{ width: 80 }}>Changes</th>
              </tr>
            </thead>
            <tbody>
              {entries.map(entry => {
                const isExpanded = expandedId === entry.id;
                const colorClass = ENTITY_COLORS[entry.entity_type] ?? 'chip-grey';
                const hasChanges = entry.before_value != null || entry.after_value != null;
                return (
                  <React.Fragment key={entry.id}>
                    <tr style={{ cursor: hasChanges ? 'pointer' : 'default' }} onClick={() => hasChanges && setExpandedId(isExpanded ? null : entry.id)}>
                      <td style={{ color: 'var(--c-text-4)', fontSize: 11 }}>{entry.id}</td>
                      <td>
                        <span className="chip chip-grey" style={{ fontSize: 11 }}>
                          #{entry.actor_id ?? '—'}
                        </span>
                      </td>
                      <td>
                        <span className="chip chip-blue" style={{ fontSize: 11 }}>{entry.action}</span>
                      </td>
                      <td>
                        <span className={`chip ${colorClass}`} style={{ fontSize: 11 }}>{entry.entity_type}</span>
                      </td>
                      <td style={{ fontSize: 12 }}>{entry.entity_id ?? '—'}</td>
                      <td style={{ fontSize: 12 }}>{fmtTime(entry.timestamp)}</td>
                      <td>
                        {hasChanges ? (
                          <button
                            id={`audit-expand-${entry.id}`}
                            className="btn btn-ghost btn-sm"
                            style={{ fontSize: 11 }}
                            onClick={e => { e.stopPropagation(); setExpandedId(isExpanded ? null : entry.id); }}
                          >
                            {isExpanded ? 'Hide ↑' : 'Show ↓'}
                          </button>
                        ) : '—'}
                      </td>
                    </tr>
                    {isExpanded && hasChanges && (
                      <tr>
                        <td colSpan={7} style={{ background: 'var(--c-surface)', padding: '12px 16px' }}>
                          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
                            <div>
                              <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--c-text-3)', marginBottom: 6, textTransform: 'uppercase' }}>Before</div>
                              {entry.before_value != null ? (
                                <pre style={{ fontSize: 11, background: 'white', border: '1px solid var(--c-border)', borderRadius: 6, padding: 10, overflow: 'auto', maxHeight: 200 }}>
                                  {JSON.stringify(entry.before_value, null, 2)}
                                </pre>
                              ) : (
                                <span style={{ fontSize: 12, color: 'var(--c-text-4)' }}>—</span>
                              )}
                            </div>
                            <div>
                              <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--c-green)', marginBottom: 6, textTransform: 'uppercase' }}>After</div>
                              {entry.after_value != null ? (
                                <pre style={{ fontSize: 11, background: 'white', border: '1px solid #86efac', borderRadius: 6, padding: 10, overflow: 'auto', maxHeight: 200 }}>
                                  {JSON.stringify(entry.after_value, null, 2)}
                                </pre>
                              ) : (
                                <span style={{ fontSize: 12, color: 'var(--c-text-4)' }}>—</span>
                              )}
                            </div>
                          </div>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
