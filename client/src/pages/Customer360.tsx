import React, { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { customersApi, opportunitiesApi, CustomerDetail, Opportunity, ApiError } from '../api/client';
import { ApiErrorBanner } from '../components/ApiErrorBanner';

const SYS_META: Record<string, { icon: string; colorClass: string }> = {
  EQUITY:    { icon: '📈', colorClass: 'sys-equity' },
  MF:        { icon: '💼', colorClass: 'sys-mf' },
  INSURANCE: { icon: '🛡️', colorClass: 'sys-insurance' },
  LOANS:     { icon: '🏦', colorClass: 'sys-loans' },
  WEALTH:    { icon: '💎', colorClass: 'sys-wealth' },
};

type Tab = '360' | 'opportunities';

function renderMatchReasons(reasons: unknown): React.ReactNode {
  if (!reasons) return <span style={{ color: 'var(--c-text-4)' }}>—</span>;
  if (typeof reasons === 'string') return reasons;
  if (typeof reasons === 'object') {
    const r = reasons as Record<string, unknown>;
    // If narrated text exists, prefer it
    if (r.narrative && typeof r.narrative === 'string') return r.narrative;
    if (r.reason && typeof r.reason === 'string') return r.reason;
    if (r.reasons && Array.isArray(r.reasons)) return (r.reasons as string[]).join('; ');
    // Fallback: show key fields in human-readable form
    const parts: string[] = [];
    if (r.match_type)        parts.push(`Match: ${r.match_type}`);
    if (r.confidence_score)  parts.push(`Confidence: ${(Number(r.confidence_score) * 100).toFixed(0)}%`);
    if (r.matched_on)        parts.push(`Matched on: ${Array.isArray(r.matched_on) ? (r.matched_on as string[]).join(', ') : r.matched_on}`);
    return parts.length ? parts.join(' · ') : JSON.stringify(reasons);
  }
  return String(reasons);
}

export function Customer360Page() {
  const { id } = useParams<{ id: string }>();
  const customerId = Number(id);
  const { isAdmin } = useAuth();

  const [tab, setTab] = useState<Tab>('360');
  const [unmasked, setUnmasked] = useState(false);
  const [detail, setDetail] = useState<CustomerDetail | null>(null);
  const [opportunities, setOpportunities] = useState<Opportunity[]>([]);
  const [loadErr, setLoadErr] = useState<{ status?: number; detail: string } | null>(null);
  const [loading, setLoading] = useState(true);

  function loadCustomer(mask: boolean) {
    setLoading(true);
    setLoadErr(null);
    customersApi.get(customerId, !mask)
      .then(setDetail)
      .catch(err => {
        if (err instanceof ApiError) setLoadErr({ status: err.status, detail: err.detail });
        else setLoadErr({ detail: String(err) });
      })
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    loadCustomer(!unmasked);
    // Load opportunities for this customer
    opportunitiesApi.list({ limit: 200 })
      .then(ops => setOpportunities(ops.filter(o => o.golden_customer_id === customerId)))
      .catch(() => {});
  }, [customerId]);

  function handleUnmaskToggle() {
    const next = !unmasked;
    setUnmasked(next);
    loadCustomer(!next);
  }

  const c = detail?.customer;

  // Group provenance by field name to identify conflicts
  const provenanceByField: Record<string, NonNullable<CustomerDetail['field_provenance']>> = {};
  (detail?.field_provenance ?? []).forEach(p => {
    if (!provenanceByField[p.field_name]) provenanceByField[p.field_name] = [];
    provenanceByField[p.field_name].push(p);
  });

  return (
    <div className="page-content">
      {/* Back link */}
      <div style={{ marginBottom: 16 }}>
        <Link to="/customers" className="btn btn-ghost btn-sm">← All customers</Link>
      </div>

      {loading && (
        <div style={{ display: 'flex', gap: 10, color: 'var(--c-text-3)', padding: '20px 0' }}>
          <span className="spinner" /> Loading customer profile…
        </div>
      )}

      {loadErr && (
        <div style={{ marginTop: 8 }}>
          <ApiErrorBanner status={loadErr.status} detail={loadErr.detail} />
        </div>
      )}

      {!loading && !loadErr && c && (
        <>
          {/* Header */}
          <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 20, flexWrap: 'wrap', gap: 12 }}>
            <div>
              <h1 className="page-title" style={{ marginBottom: 4 }}>{c.primary_name}</h1>
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                {c.city && <span className="chip chip-grey">{c.city}</span>}
                {c.dob && <span className="chip chip-grey">DOB: {c.dob.slice(0, 10)}</span>}
                {c.relationship_value != null && (
                  <span className="chip chip-blue">
                    ₹{Number(c.relationship_value).toLocaleString('en-IN')} AUM
                  </span>
                )}
              </div>
            </div>

            {/* Unmask toggle — Admin only */}
            {isAdmin ? (
              <div className="toggle-wrap" id="unmask-toggle-wrap">
                <label className="toggle">
                  <input type="checkbox" checked={unmasked} onChange={handleUnmaskToggle} id="unmask-toggle" />
                  <span className="toggle-slider" />
                </label>
                <span style={{ fontSize: 13, color: 'var(--c-text-2)' }}>
                  {unmasked ? '🔓 Unmasked (Admin)' : '🔒 Unmask PII'}
                </span>
              </div>
            ) : (
              <div title="Only Admin can unmask PII — the backend enforces this via can_unmask()">
                <span style={{ fontSize: 12, color: 'var(--c-text-4)', display: 'flex', alignItems: 'center', gap: 4 }}>
                  🔒 PII masked — Admin only
                </span>
              </div>
            )}
          </div>

          {/* PII row */}
          <div className="card card-sm" style={{ marginBottom: 20, display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: 14 }}>
            {[
              { label: 'PAN-like ID', value: c.pan_like },
              { label: 'Mobile',      value: c.mobile },
              { label: 'Email',       value: c.email },
            ].map(f => (
              <div key={f.label}>
                <div style={{ fontSize: 11, color: 'var(--c-text-3)', textTransform: 'uppercase', letterSpacing: '.4px', marginBottom: 3 }}>{f.label}</div>
                <div className="mono" style={{ fontSize: 13 }}>{f.value ?? '—'}</div>
              </div>
            ))}
          </div>

          {/* Tabs */}
          <div style={{ display: 'flex', gap: 2, borderBottom: '1px solid var(--c-border)', marginBottom: 20 }}>
            {(['360', 'opportunities'] as Tab[]).map(t => (
              <button
                key={t}
                id={`tab-${t}`}
                className="btn btn-ghost"
                style={{
                  borderBottom: tab === t ? '2px solid var(--c-brand)' : '2px solid transparent',
                  borderRadius: 0, paddingBottom: 8, color: tab === t ? 'var(--c-brand)' : 'var(--c-text-3)',
                  fontWeight: tab === t ? 600 : 400,
                }}
                onClick={() => setTab(t)}
              >
                {t === '360' ? 'Customer 360' : `Opportunities (${opportunities.length})`}
              </button>
            ))}
          </div>

          {/* Tab: Customer 360 */}
          {tab === '360' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>

              {/* Source system lineage chips */}
              <div>
                <div className="section-heading">Source Systems</div>
                {detail.source_records.length === 0 ? (
                  <div className="empty-state" style={{ padding: '20px 0' }}>
                    <div className="empty-state-text">No source records linked yet.</div>
                  </div>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                    {detail.source_records.map((sr, i) => {
                      const meta = SYS_META[sr.source_system] ?? { icon: '📄', colorClass: '' };
                      const matchReason = detail.match_reasons?.[i];
                      // Try to get match type and confidence from match_reasons
                      let matchType = 'UNKNOWN';
                      let confidence = 0;
                      if (matchReason && typeof matchReason === 'object') {
                        const mr = matchReason as Record<string, unknown>;
                        if (mr.match_type)       matchType  = String(mr.match_type);
                        if (mr.confidence_score) confidence = Number(mr.confidence_score);
                      }
                      return (
                        <div key={sr.id} className="card card-sm" style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
                            <span className={`chip ${meta.colorClass}`}>{meta.icon} {sr.source_system}</span>
                            <span className="chip chip-grey" style={{ fontSize: 11 }}>ID: {sr.source_customer_id}</span>
                            {matchType !== 'UNKNOWN' && (
                              <span className={`chip ${matchType === 'DETERMINISTIC' ? 'chip-green' : 'chip-amber'}`}>
                                {matchType}
                              </span>
                            )}
                            {confidence > 0 && (
                              <span className="chip chip-blue" style={{ fontSize: 11 }}>
                                {(confidence * 100).toFixed(0)}% confidence
                              </span>
                            )}
                          </div>
                          {/* Narrated match_reasons — not raw JSON */}
                          {Boolean(matchReason) && (
                            <div style={{ fontSize: 12, color: 'var(--c-text-2)', background: 'var(--c-surface)', borderRadius: 6, padding: '6px 10px', borderLeft: '3px solid var(--c-brand-mid)' }}>
                              <strong>Match rationale:</strong> {renderMatchReasons(matchReason)}
                            </div>
                          )}
                          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(150px, 1fr))', gap: 8 }}>
                            {[
                              { label: 'Name',   value: sr.name },
                              { label: 'PAN',    value: sr.pan_like },
                              { label: 'Mobile', value: sr.mobile },
                              { label: 'Email',  value: sr.email },
                              { label: 'City',   value: sr.city },
                              { label: 'Balance', value: sr.balance != null ? `₹${Number(sr.balance).toLocaleString('en-IN')}` : null },
                            ].map(f => (
                              <div key={f.label}>
                                <div style={{ fontSize: 10, color: 'var(--c-text-4)', textTransform: 'uppercase', letterSpacing: '.4px' }}>{f.label}</div>
                                <div className="mono" style={{ fontSize: 12 }}>{f.value ?? '—'}</div>
                              </div>
                            ))}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>

              {/* Field provenance — winners, losers, conflicts */}
              {Object.keys(provenanceByField).length > 0 && (
                <div>
                  <div className="section-heading">Field Provenance &amp; Conflict Resolution</div>
                  <div style={{ marginBottom: 8, fontSize: 12, color: 'var(--c-text-3)' }}>
                    The winning value is shown in <span style={{ color: 'var(--c-green)', fontWeight: 600 }}>green</span>.
                    Losing values are <em>still stored</em> — not discarded — and shown in grey for auditability.
                  </div>
                  <div className="table-wrap">
                    <table className="data-table">
                      <thead>
                        <tr>
                          <th>Field</th>
                          <th>Winner</th>
                          <th>Source</th>
                          <th>Confidence</th>
                          <th>Other values (stored, not discarded)</th>
                          <th>Resolution</th>
                        </tr>
                      </thead>
                      <tbody>
                        {Object.entries(provenanceByField).map(([field, rows]) => {
                          const winner = rows.find(r => r.is_resolved) ?? rows.reduce((a, b) => (a.confidence ?? 0) >= (b.confidence ?? 0) ? a : b);
                          const losers = rows.filter(r => r.id !== winner.id);
                          return (
                            <tr key={field}>
                              <td><strong>{field}</strong></td>
                              <td className="prov-win">
                                <span className="mono">{winner.value ?? '—'}</span>
                              </td>
                              <td>
                                <span className={`chip chip-grey`}>{winner.source_system}</span>
                              </td>
                              <td>
                                {winner.confidence != null
                                  ? `${(winner.confidence * 100).toFixed(0)}%`
                                  : '—'}
                              </td>
                              <td className="prov-lose">
                                {losers.length === 0 ? (
                                  <span style={{ color: 'var(--c-text-4)', fontSize: 12 }}>No conflict</span>
                                ) : (
                                  <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                                    {losers.map(l => (
                                      <div key={l.id} style={{ fontSize: 12 }}>
                                        <span className="mono">{l.value ?? '—'}</span>
                                        <span style={{ color: 'var(--c-text-4)', marginLeft: 6 }}>({l.source_system})</span>
                                      </div>
                                    ))}
                                  </div>
                                )}
                              </td>
                              <td>
                                <span className={`chip ${winner.is_resolved ? 'chip-green' : 'chip-grey'}`}>
                                  {winner.resolution_method ?? (winner.is_resolved ? 'resolved' : 'pending')}
                                </span>
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Tab: Opportunities */}
          {tab === 'opportunities' && (
            <OpportunitiesTab opportunities={opportunities} />
          )}
        </>
      )}
    </div>
  );
}

function OpportunitiesTab({ opportunities }: { opportunities: Opportunity[] }) {
  if (opportunities.length === 0) {
    return (
      <div className="empty-state">
        <div className="empty-state-icon">🎯</div>
        <div className="empty-state-text">No opportunities generated for this customer yet. Run the pipeline to generate them.</div>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {opportunities.map(opp => (
        <OpportunityCard key={opp.id} opp={opp} />
      ))}
    </div>
  );
}

function OpportunityCard({ opp }: { opp: Opportunity }) {
  const scoreBreakdown = opp.score_breakdown ?? {};
  const scoreEntries = Object.entries(scoreBreakdown);

  return (
    <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
        <span style={{ fontSize: 15, fontWeight: 600 }}>{opp.product_type}</span>
        <span className={`chip ${opp.eligibility_passed ? 'chip-green' : 'chip-red'}`}>
          {opp.eligibility_passed ? '✓ Eligible' : '✗ Not eligible'}
        </span>
        <span className={`chip ${opp.score >= 70 ? 'chip-green' : opp.score >= 40 ? 'chip-amber' : 'chip-red'}`}>
          Score: {opp.score.toFixed(0)}
        </span>
        <span className="chip chip-grey" style={{ marginLeft: 'auto' }}>{opp.status}</span>
      </div>

      {/* Reason text — verbatim from API */}
      {opp.reason_text && (
        <div style={{ fontSize: 13, color: 'var(--c-text-2)', padding: '8px 12px', background: 'var(--c-brand-lt)', borderRadius: 6, borderLeft: '3px solid var(--c-brand)' }}>
          {opp.reason_text}
        </div>
      )}

      {/* Eligibility checklist from score_breakdown keys */}
      {scoreEntries.length > 0 && (
        <div>
          <div className="section-heading" style={{ marginBottom: 8 }}>Score Breakdown</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {scoreEntries.map(([key, val]) => {
              const pct = Math.min(100, Math.max(0, Number(val)));
              const label = key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
              return (
                <div key={key}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                    <span style={{ fontSize: 12, color: 'var(--c-text-2)' }}>
                      {opp.eligibility_passed ? '✓' : '○'} {label}
                    </span>
                    <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--c-text)' }}>
                      {typeof val === 'number' ? val.toFixed(1) : String(val)}
                    </span>
                  </div>
                  <div className="score-bar-track">
                    <div className="score-bar-fill" style={{ width: `${pct}%` }} />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
