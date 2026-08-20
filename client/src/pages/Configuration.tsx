import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { configApi, adminApi, ConfigEntry, ApiError } from '../api/client';
import { ApiErrorBanner } from '../components/ApiErrorBanner';

const CATEGORIES = [
  'MATCH_WEIGHTS', 'THRESHOLDS', 'SOURCE_PRECEDENCE',
  'ELIGIBILITY_RULES', 'SCORING_WEIGHTS', 'REVIEW_RULES', 'NORMALIZATION_RULES',
];

export function ConfigurationPage() {
  const navigate = useNavigate();
  const [entries, setEntries] = useState<ConfigEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<{ status?: number; detail: string } | null>(null);
  const [catFilter, setCatFilter] = useState<string>('');

  // Per-row edit state
  const [editValues, setEditValues] = useState<Record<number, string>>({});
  const [saving, setSaving] = useState<Record<number, boolean>>({});
  const [saveErrs, setSaveErrs] = useState<Record<number, string>>({});
  const [savedIds, setSavedIds] = useState<Set<number>>(new Set());

  // Post-save pipeline prompt
  const [showPipelinePrompt, setShowPipelinePrompt] = useState(false);
  const [pipelineRunning, setPipelineRunning] = useState(false);
  const [pipelineResult, setPipelineResult] = useState<string | null>(null);

  function load() {
    setLoading(true);
    setError(null);
    configApi.list(catFilter || undefined)
      .then(data => {
        setEntries(data);
        // Initialize edit values with current JSON
        const init: Record<number, string> = {};
        data.forEach(e => { init[e.id] = JSON.stringify(e.value, null, 2); });
        setEditValues(init);
      })
      .catch(err => {
        if (err instanceof ApiError) setError({ status: err.status, detail: err.detail });
        else setError({ detail: String(err) });
      })
      .finally(() => setLoading(false));
  }

  useEffect(load, [catFilter]);

  async function handleSave(entry: ConfigEntry) {
    setSaving(p => ({ ...p, [entry.id]: true }));
    setSaveErrs(p => ({ ...p, [entry.id]: '' }));
    try {
      const parsed = JSON.parse(editValues[entry.id]);
      const updated = await configApi.update(entry.id, parsed);
      setEntries(prev => prev.map(e => e.id === entry.id ? updated : e));
      setSavedIds(prev => new Set([...prev, entry.id]));
      setShowPipelinePrompt(true);
      setTimeout(() => setSavedIds(prev => { const s = new Set(prev); s.delete(entry.id); return s; }), 2000);
    } catch (e) {
      if (e instanceof SyntaxError) {
        setSaveErrs(p => ({ ...p, [entry.id]: 'Invalid JSON — please fix before saving.' }));
      } else if (e instanceof ApiError) {
        setSaveErrs(p => ({ ...p, [entry.id]: `${e.status}: ${e.detail}` }));
      } else {
        setSaveErrs(p => ({ ...p, [entry.id]: String(e) }));
      }
    } finally {
      setSaving(p => ({ ...p, [entry.id]: false }));
    }
  }

  async function handleRunPipeline() {
    setPipelineRunning(true);
    setPipelineResult(null);
    try {
      const res = await adminApi.runPipeline();
      const s = res.summary ?? {};
      const parts = Object.entries(s).map(([k, v]) => `${k.replace(/_/g, ' ')}: ${v}`);
      setPipelineResult('✓ Pipeline complete — ' + (parts.join(', ') || 'done'));
      setShowPipelinePrompt(false);
    } catch (e) {
      if (e instanceof ApiError) setPipelineResult(`✗ ${e.status}: ${e.detail}`);
      else setPipelineResult(`✗ ${String(e)}`);
    } finally {
      setPipelineRunning(false);
    }
  }

  const grouped: Record<string, ConfigEntry[]> = {};
  entries.forEach(e => {
    if (!grouped[e.category]) grouped[e.category] = [];
    grouped[e.category].push(e);
  });

  return (
    <div className="page-content">
      <div className="page-header" style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
        <div>
          <h1 className="page-title">Configuration</h1>
          <p className="page-subtitle">Admin only — edit matching weights, thresholds, and eligibility rules</p>
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <select
            className="form-input"
            style={{ width: 200 }}
            value={catFilter}
            onChange={e => setCatFilter(e.target.value)}
            id="config-category-filter"
          >
            <option value="">All categories</option>
            {CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
          </select>
          <button className="btn btn-outline btn-sm" onClick={load}>↻</button>
        </div>
      </div>

      {/* Post-save: re-run prompt — two-click demo scenario */}
      {showPipelinePrompt && !pipelineResult && (
        <div className="banner banner-info" style={{ marginBottom: 16 }}>
          <span className="banner-icon">💡</span>
          <div style={{ flex: 1 }}>
            <strong>Config saved.</strong> Re-run the matching pipeline to see the effect of your change.
          </div>
          <button
            id="config-rerun-pipeline-btn"
            className="btn btn-primary btn-sm"
            onClick={handleRunPipeline}
            disabled={pipelineRunning}
          >
            {pipelineRunning ? <><span className="spinner" /> Running…</> : '⚡ Run pipeline now'}
          </button>
        </div>
      )}

      {pipelineResult && (
        <div className={`banner ${pipelineResult.startsWith('✓') ? 'banner-success' : 'banner-error'}`} style={{ marginBottom: 16 }}>
          <span className="banner-icon">{pipelineResult.startsWith('✓') ? '✓' : '✗'}</span>
          {pipelineResult}
        </div>
      )}

      {error && <ApiErrorBanner status={error.status} detail={error.detail} />}

      {loading && (
        <div style={{ display: 'flex', gap: 10, color: 'var(--c-text-3)' }}>
          <span className="spinner" /> Loading config…
        </div>
      )}

      {!loading && !error && Object.entries(grouped).map(([cat, rows]) => (
        <div key={cat} style={{ marginBottom: 28 }}>
          <div className="section-heading">{cat}</div>
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th style={{ width: 200 }}>Key</th>
                  <th>Value (JSON)</th>
                  <th style={{ width: 80 }}>Version</th>
                  <th style={{ width: 120 }}></th>
                </tr>
              </thead>
              <tbody>
                {rows.map(entry => {
                  const isDirty = JSON.stringify(JSON.parse(editValues[entry.id] || 'null')) !== JSON.stringify(entry.value);
                  return (
                    <tr key={entry.id}>
                      <td>
                        <strong style={{ fontSize: 13 }}>{entry.key}</strong>
                      </td>
                      <td>
                        <div className="config-value-cell">
                          <textarea
                            id={`config-val-${entry.id}`}
                            className="form-input config-textarea"
                            value={editValues[entry.id] ?? ''}
                            onChange={e => setEditValues(p => ({ ...p, [entry.id]: e.target.value }))}
                            rows={Math.min(8, (editValues[entry.id] ?? '').split('\n').length + 1)}
                          />
                        </div>
                        {saveErrs[entry.id] && (
                          <div style={{ color: 'var(--c-red)', fontSize: 12, marginTop: 4 }}>{saveErrs[entry.id]}</div>
                        )}
                      </td>
                      <td>
                        <span className="chip chip-grey">v{entry.version}</span>
                      </td>
                      <td>
                        {savedIds.has(entry.id) ? (
                          <span style={{ color: 'var(--c-green)', fontSize: 12, fontWeight: 600 }}>✓ Saved</span>
                        ) : (
                          <button
                            id={`config-save-${entry.id}`}
                            className={`btn btn-sm ${isDirty ? 'btn-primary' : 'btn-outline'}`}
                            disabled={saving[entry.id] || !isDirty}
                            onClick={() => handleSave(entry)}
                          >
                            {saving[entry.id] ? <span className="spinner" /> : 'Save'}
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      ))}
    </div>
  );
}
