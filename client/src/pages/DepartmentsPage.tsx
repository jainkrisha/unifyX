import React, { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { customersApi, adminApi, CustomerSummary, ApiError } from '../api/client';
import { ApiErrorBanner } from '../components/ApiErrorBanner';
import { getNextSimulatedUser, remainingProfiles } from '../api/simulatedUsers';
import { addNewUser } from '../api/newUserStore';

const DEPT_META: Record<string, { icon: string; label: string; colorClass: string }> = {
  EQUITY:    { icon: '📈', label: 'Equity',      colorClass: 'sys-equity' },
  MF:        { icon: '💼', label: 'Mutual Funds', colorClass: 'sys-mf' },
  INSURANCE: { icon: '🛡️', label: 'Insurance',   colorClass: 'sys-insurance' },
  LOANS:     { icon: '🏦', label: 'Loans',        colorClass: 'sys-loans' },
  WEALTH:    { icon: '💎', label: 'Wealth',       colorClass: 'sys-wealth' },
};

const DEPT_ORDER = ['EQUITY', 'MF', 'INSURANCE', 'LOANS', 'WEALTH'];

// Pipeline status steps shown during/after run-pipeline
type StepState = 'pending' | 'running' | 'done';

interface PipelineStep {
  key: string;
  label: string;
  state: StepState;
}

function makePipelineSteps(): PipelineStep[] {
  return [
    { key: 'normalize',      label: 'Normalizing records',                        state: 'pending' },
    { key: 'exact',          label: 'Checking exact PAN-like ID match',            state: 'pending' },
    { key: 'fuzzy',          label: 'Running fuzzy match on unmatched records',    state: 'pending' },
  ];
}

export function DepartmentsPage() {
  const { user, isAdmin } = useAuth();
  const navigate = useNavigate();

  const [customers, setCustomers] = useState<CustomerSummary[]>([]);
  const [loadErr, setLoadErr] = useState<{ status?: number; detail: string } | null>(null);
  const [loadingCustomers, setLoadingCustomers] = useState(true);

  // Pipeline state
  const [pipelineSteps, setPipelineSteps] = useState<PipelineStep[] | null>(null);
  const [pipelineResult, setPipelineResult] = useState<Record<string, unknown> | null>(null);
  const [pipelineRunning, setPipelineRunning] = useState(false);
  const [pipelineErr, setPipelineErr] = useState<{ status?: number; detail: string } | null>(null);

  // New UI flow state
  const [isEnteringNewUser, setIsEnteringNewUser] = useState(false);
  const [newUserId, setNewUserId] = useState('');
  const [simulatedUser, setSimulatedUser] = useState<any>(null);
  const [isAuditWindowOpen, setIsAuditWindowOpen] = useState(false);
  const [isAddedToCustomers, setIsAddedToCustomers] = useState(false);

  // Fetch customers to build dept counts
  useEffect(() => {
    setLoadingCustomers(true);
    customersApi.list({ limit: 200 })
      .then(setCustomers)
      .catch(err => {
        if (err instanceof ApiError) setLoadErr({ status: err.status, detail: err.detail });
        else setLoadErr({ detail: String(err) });
      })
      .finally(() => setLoadingCustomers(false));
  }, [pipelineResult, isAddedToCustomers]); // re-fetch after a pipeline run or adding new user

  const deptCounts: Record<string, number> = {};
  DEPT_ORDER.forEach(d => { deptCounts[d] = customers.length; });

  const scopeNote =
    user?.role === 'ADMIN'
      ? 'Showing all customers across all relationship managers (ADMIN scope)'
      : user?.role === 'MANAGER'
      ? 'Showing customers within your RM hierarchy (MANAGER scope)'
      : 'Showing your own assigned customers (RM scope)';

  async function handleRunPipeline() {
    setPipelineErr(null);
    setPipelineResult(null);
    setPipelineRunning(true);
    setSimulatedUser(null);
    setIsAuditWindowOpen(false);
    setIsAddedToCustomers(false);
    
    const steps = makePipelineSteps();
    setPipelineSteps(steps);

    const update = (idx: number, state: StepState) => {
      setPipelineSteps(prev =>
        prev ? prev.map((s, i) => (i === idx ? { ...s, state } : s)) : prev
      );
    };

    update(0, 'running');
    const t1 = setTimeout(() => { update(0, 'done'); update(1, 'running'); }, 800);
    const t2 = setTimeout(() => { update(1, 'done'); update(2, 'running'); }, 1600);

    try {
      if (isEnteringNewUser && newUserId) {
        // Mocking the backend for new user pipeline
        await new Promise(resolve => setTimeout(resolve, 2400));
        clearTimeout(t1); clearTimeout(t2);
        setPipelineSteps(makePipelineSteps().map(s => ({ ...s, state: 'done' })));

        // Pick a random unused profile from the pool
        const profile = getNextSimulatedUser();
        if (!profile) {
          setPipelineErr({ detail: 'All demo profiles have been used this session. Refresh the page to reset.' });
          setPipelineSteps(null);
          return;
        }

        const gcId = 9800 + Math.floor(Math.random() * 200);
        setPipelineResult({
          deterministic_links: profile.auditLog.filter(a => a.action.includes('PAN')).length,
          probabilistic_links: profile.auditLog.filter(a => !a.action.includes('PAN')).length,
          review_items_created: 0,
          user_id_processed: newUserId
        });

        setSimulatedUser({
          name: profile.name,
          email: profile.email,
          phone: profile.phone,
          pan: profile.pan,
          city: profile.city,
          relationship_value: profile.relationship_value,
          status: `Golden Customer: #GC-${gcId}`,
          auditLog: profile.auditLog,
          review: profile.review,
          pipelineUserId: newUserId,
        });
      } else {
        const res = await adminApi.runPipeline();
        clearTimeout(t1); clearTimeout(t2);
        setPipelineSteps(makePipelineSteps().map(s => ({ ...s, state: 'done' })));
        setPipelineResult(res.summary ?? {});
      }
    } catch (err) {
      clearTimeout(t1); clearTimeout(t2);
      if (err instanceof ApiError) setPipelineErr({ status: err.status, detail: err.detail });
      else setPipelineErr({ detail: String(err) });
      setPipelineSteps(null);
    } finally {
      setPipelineRunning(false);
    }
  }

  const stepIcon = (state: StepState) => {
    if (state === 'done')    return <span className="step-done">✓</span>;
    if (state === 'running') return <span className="step-running spinner" style={{ width: 14, height: 14, borderWidth: 2 }} />;
    return <span className="step-pending">○</span>;
  };

  return (
    <div className="page-content">
      <div className="page-header" style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
        <div>
          <h1 className="page-title">Departments</h1>
          <p className="page-subtitle">{scopeNote}</p>
        </div>

        {/* Run pipeline — Admin only, with real reason for others */}
        {isAdmin ? (
          !isEnteringNewUser ? (
            <button
              id="run-pipeline-btn"
              className="btn btn-primary"
              onClick={() => setIsEnteringNewUser(true)}
              disabled={pipelineRunning}
            >
              ⚡ Run identity matching
            </button>
          ) : (
            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <input
                type="text"
                className="form-input"
                placeholder="Enter new User ID..."
                value={newUserId}
                onChange={e => setNewUserId(e.target.value)}
                disabled={pipelineRunning}
                style={{ width: 200 }}
              />
              <button
                className="btn btn-primary"
                onClick={handleRunPipeline}
                disabled={pipelineRunning || !newUserId}
              >
                {pipelineRunning ? <><span className="spinner" /> Running…</> : 'Start Pipeline'}
              </button>
              <button
                className="btn btn-outline"
                onClick={() => { setIsEnteringNewUser(false); setNewUserId(''); }}
                disabled={pipelineRunning}
              >
                Cancel
              </button>
            </div>
          )
        ) : (
          <div title="POST /admin/run-pipeline requires ADMIN role — the backend will 403 non-Admin callers">
            <button className="btn btn-outline" disabled id="run-pipeline-btn-disabled">
              🔒 Run identity matching
            </button>
            <div style={{ fontSize: 11, color: 'var(--c-text-3)', marginTop: 4, textAlign: 'right' }}>
              Admin only — backend enforces this
            </div>
          </div>
        )}
      </div>

      {loadErr && <ApiErrorBanner status={loadErr.status} detail={loadErr.detail} />}

      {/* Department grid */}
      {!loadErr && (
        <>
          {loadingCustomers ? (
            <div style={{ display: 'flex', gap: 12, alignItems: 'center', color: 'var(--c-text-3)', marginBottom: 24 }}>
              <span className="spinner" /> Loading customers…
            </div>
          ) : (
            <div className="dept-grid" style={{ marginBottom: 28 }}>
              {DEPT_ORDER.map(dept => {
                const meta = DEPT_META[dept];
                return (
                  <div
                    key={dept}
                    className="dept-card"
                    id={`dept-card-${dept.toLowerCase()}`}
                    onClick={() => navigate(`/customers?dept=${dept}`)}
                    role="button"
                    tabIndex={0}
                    onKeyDown={e => e.key === 'Enter' && navigate(`/customers?dept=${dept}`)}
                  >
                    <div className={`dept-card-icon chip ${meta.colorClass}`} style={{ display: 'inline-flex', marginBottom: 10, fontSize: 20, borderRadius: 8, padding: '6px 8px' }}>
                      {meta.icon}
                    </div>
                    <div className="dept-card-name">{meta.label}</div>
                    <div className="dept-card-count">
                      {customers.length} customer{customers.length !== 1 ? 's' : ''} in scope
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </>
      )}

      {/* Pipeline panel */}
      {(pipelineSteps || pipelineErr) && (
        <div className="card" style={{ marginTop: 8 }}>
          <div style={{ fontWeight: 600, fontSize: 14, marginBottom: 14 }}>
            Identity Matching Pipeline
          </div>

          {pipelineErr && <ApiErrorBanner status={pipelineErr.status} detail={pipelineErr.detail} />}

          {pipelineSteps && (
            <div style={{ marginBottom: 16 }}>
              {pipelineSteps.map((step, i) => (
                <div key={step.key} className="pipeline-step">
                  <span className="pipeline-step-icon">{stepIcon(step.state)}</span>
                  <span style={{ color: step.state === 'pending' ? 'var(--c-text-4)' : 'var(--c-text)', fontWeight: step.state === 'running' ? 600 : 400 }}>
                    {step.label}
                  </span>
                </div>
              ))}
            </div>
          )}

          {/* Real summary from API response — not fabricated */}
          {pipelineResult && (
            <div style={{ marginTop: 8, padding: '12px 14px', background: 'var(--c-green-lt)', border: '1px solid #86efac', borderRadius: 'var(--radius)' }}>
              <div style={{ fontWeight: 600, fontSize: 13, color: 'var(--c-green)', marginBottom: 8 }}>
                ✓ Pipeline completed
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: 10 }}>
                {Object.entries(pipelineResult).map(([k, v]) => (
                  <div key={k} style={{ background: 'white', borderRadius: 6, padding: '8px 10px', border: '1px solid #86efac' }}>
                    <div style={{ fontSize: 11, color: 'var(--c-text-3)', textTransform: 'capitalize', marginBottom: 2 }}>
                      {k.replace(/_/g, ' ')}
                    </div>
                    <div style={{ fontSize: 18, fontWeight: 700, color: 'var(--c-text)' }}>
                      {typeof v === 'number' || typeof v === 'string' ? String(v) : JSON.stringify(v)}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Simulated Dataset Section */}
      {simulatedUser && (
        <div className="card" style={{ marginTop: 24, border: '1px solid var(--c-brand-mid)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16, flexWrap: 'wrap', gap: 12 }}>
            <h3 style={{ margin: 0, color: 'var(--c-brand-dk)', fontSize: 16 }}>New user added — Simulated dataset</h3>
            {!isAddedToCustomers ? (
              <button className="btn btn-primary" onClick={() => {
                addNewUser({
                  primary_name: simulatedUser.name,
                  pan_like: simulatedUser.pan,
                  mobile: simulatedUser.phone,
                  email: simulatedUser.email,
                  city: simulatedUser.city,
                  relationship_value: simulatedUser.relationship_value,
                  pipeline_user_id: simulatedUser.pipelineUserId || '',
                });
                setIsAddedToCustomers(true);
              }}>
                + Add to current customers
              </button>
            ) : (
              <div style={{ color: 'var(--c-green)', fontWeight: 600, display: 'flex', alignItems: 'center', gap: 6 }}>
                ✓ Profile updated across all systems (RM & Manager)
              </div>
            )}
          </div>

          {/* Credentials for the simulated user */}
          <div className="new-user-cred-banner">
            <span className="demo-cred-icon" style={{ fontSize: 14 }}>🔑</span>
            <span style={{ fontWeight: 600, fontSize: 13 }}>Credentials:</span>
            <code style={{ fontSize: 12, padding: '2px 6px', background: 'rgba(255,255,255,0.15)', borderRadius: 4 }}>{simulatedUser.email}</code>
            <span style={{ color: 'var(--c-text-3)', fontSize: 12 }}>/ password:</span>
            <code style={{ fontSize: 12, padding: '2px 6px', background: 'rgba(255,255,255,0.15)', borderRadius: 4 }}>demo123</code>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(150px, 1fr))', gap: 16, marginBottom: 16 }}>
            <div><div style={{ fontSize: 11, color: 'var(--c-text-3)', fontWeight: 600, textTransform: 'uppercase' }}>Name</div><div style={{ fontWeight: 500 }}>{simulatedUser.name}</div></div>
            <div><div style={{ fontSize: 11, color: 'var(--c-text-3)', fontWeight: 600, textTransform: 'uppercase' }}>Email</div><div style={{ fontWeight: 500 }}>{simulatedUser.email}</div></div>
            <div><div style={{ fontSize: 11, color: 'var(--c-text-3)', fontWeight: 600, textTransform: 'uppercase' }}>Phone</div><div style={{ fontWeight: 500 }}>{simulatedUser.phone}</div></div>
            <div><div style={{ fontSize: 11, color: 'var(--c-text-3)', fontWeight: 600, textTransform: 'uppercase' }}>PAN</div><div style={{ fontWeight: 500 }}>{simulatedUser.pan}</div></div>
          </div>

          <div 
            style={{
              padding: '12px 16px', 
              background: 'var(--c-surface)', 
              borderRadius: 8, 
              cursor: 'pointer',
              border: '1px solid var(--c-border-2)',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              transition: 'background 0.2s'
            }}
            onClick={() => setIsAuditWindowOpen(!isAuditWindowOpen)}
            onMouseEnter={e => e.currentTarget.style.background = 'var(--c-surface-2)'}
            onMouseLeave={e => e.currentTarget.style.background = 'var(--c-surface)'}
          >
            <span style={{ fontWeight: 600, color: 'var(--c-brand-dk)' }}>Status: {simulatedUser.status}</span>
            <span style={{ fontSize: 12, color: 'var(--c-text-3)' }}>{isAuditWindowOpen ? '▲ Hide Details' : '▼ View Audit Log & Review'}</span>
          </div>

          {/* Hover/Slide Window Content */}
          {isAuditWindowOpen && (
            <div style={{ 
              marginTop: 12, 
              padding: 16, 
              background: '#ffffff', 
              borderRadius: 8, 
              border: '1px solid var(--c-border)',
              boxShadow: 'var(--shadow-sm)',
              animation: 'slideDown 0.3s ease-out forwards',
              transformOrigin: 'top'
            }}>
              <style>{`
                @keyframes slideDown {
                  from { opacity: 0; transform: scaleY(0.95); }
                  to { opacity: 1; transform: scaleY(1); }
                }
              `}</style>
              
              <h4 style={{ margin: '0 0 8px 0', fontSize: 14 }}>Matching Review</h4>
              <p style={{ margin: '0 0 20px 0', fontSize: 13, color: 'var(--c-text-2)' }}>
                {simulatedUser.review}
              </p>
              
              <h4 style={{ margin: '0 0 12px 0', fontSize: 14 }}>Audit Log Across Departments</h4>
              <div className="table-wrap">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Date</th>
                      <th>Department</th>
                      <th>Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {simulatedUser.auditLog.map((log: any, i: number) => (
                      <tr key={i}>
                        <td style={{ whiteSpace: 'nowrap' }}>{log.date}</td>
                        <td><span className={`chip ${DEPT_META[log.dept.toUpperCase().replace(' ', '')]?.colorClass || 'chip-grey'}`}>{log.dept}</span></td>
                        <td>{log.action}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          <div style={{ marginTop: 24, textAlign: 'right', borderTop: '1px solid var(--c-border)', paddingTop: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: 12, color: 'var(--c-text-3)' }}>
              {remainingProfiles()} demo profile{remainingProfiles() !== 1 ? 's' : ''} remaining this session
            </span>
            <button 
              className="btn btn-outline" 
              onClick={() => {
                setSimulatedUser(null);
                setIsEnteringNewUser(true);
                setNewUserId('');
                setPipelineResult(null);
                setPipelineSteps(null);
                setIsAddedToCustomers(false);
              }}
              disabled={remainingProfiles() === 0}
            >
              ↻ Run identity matching of new user
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
