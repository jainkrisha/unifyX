import React, { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { customersApi, adminApi, CustomerSummary, ApiError } from '../api/client';
import { ApiErrorBanner } from '../components/ApiErrorBanner';

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
  }, [pipelineResult]); // re-fetch after a pipeline run

  // Build per-department counts from linked source_systems (we only have summaries here;
  // for the dept grid we just need to know which customers exist per role scope)
  const deptCounts: Record<string, number> = {};
  // Since the list endpoint gives CustomerSummary (no source_systems), show total customers
  // per dept as "N customers in scope" — the dept grid triggers navigation with filter
  DEPT_ORDER.forEach(d => { deptCounts[d] = customers.length; });

  // Scope note
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
    const steps = makePipelineSteps();
    setPipelineSteps(steps);

    // Simulate step progression client-side while single real request is in-flight
    const update = (idx: number, state: StepState) => {
      setPipelineSteps(prev =>
        prev ? prev.map((s, i) => (i === idx ? { ...s, state } : s)) : prev
      );
    };

    update(0, 'running');
    const t1 = setTimeout(() => { update(0, 'done'); update(1, 'running'); }, 800);
    const t2 = setTimeout(() => { update(1, 'done'); update(2, 'running'); }, 1600);

    try {
      const res = await adminApi.runPipeline();
      clearTimeout(t1); clearTimeout(t2);
      // Mark all done
      setPipelineSteps(makePipelineSteps().map(s => ({ ...s, state: 'done' })));
      setPipelineResult(res.summary ?? {});
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
          <button
            id="run-pipeline-btn"
            className="btn btn-primary"
            onClick={handleRunPipeline}
            disabled={pipelineRunning}
          >
            {pipelineRunning ? <><span className="spinner" /> Running pipeline…</> : '⚡ Run identity matching'}
          </button>
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
    </div>
  );
}
