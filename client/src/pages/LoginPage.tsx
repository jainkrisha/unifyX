import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { ApiError } from '../api/client';
import { ApiErrorBanner } from '../components/ApiErrorBanner';

export function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<{ status?: number; detail: string } | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const res = await login(email, password);
      // Role comes back from server — redirect based on server-authoritative role
      navigate('/departments', { replace: true });
    } catch (err) {
      if (err instanceof ApiError) {
        setError({ status: err.status, detail: err.detail });
      } else {
        setError({ detail: 'Network error — is the backend running?' });
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'var(--c-surface)', padding: 20 }}>
      <div className="card" style={{ width: '100%', maxWidth: 400 }}>
        {/* Brand */}
        <div style={{ textAlign: 'center', marginBottom: 28 }}>
          <div style={{ fontSize: 22, fontWeight: 800, color: 'var(--c-brand)', letterSpacing: -0.5, marginBottom: 4 }}>UnifyX</div>
          <p style={{ fontSize: 13, color: 'var(--c-text-3)' }}>Sign in to your account</p>
        </div>

        {/* Security note: role is NOT chosen here */}
        <div className="banner banner-info" style={{ marginBottom: 20 }}>
          <span className="banner-icon">ℹ️</span>
          <span style={{ fontSize: 12 }}>
            Your access scope is determined by your role on the server — you don't select a role here.
          </span>
        </div>

        {error && (
          <div style={{ marginBottom: 16 }}>
            <ApiErrorBanner status={error.status} detail={error.detail} />
          </div>
        )}

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div className="form-group">
            <label className="form-label" htmlFor="login-email">Email</label>
            <input
              id="login-email"
              className="form-input"
              type="email"
              autoComplete="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              required
              placeholder="you@example.com"
            />
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="login-password">Password</label>
            <input
              id="login-password"
              className="form-input"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              required
              placeholder="••••••••"
            />
          </div>

          <button
            id="login-submit-btn"
            type="submit"
            className="btn btn-primary"
            style={{ marginTop: 4, justifyContent: 'center' }}
            disabled={loading}
          >
            {loading ? <><span className="spinner" /> Signing in…</> : 'Sign in'}
          </button>
        </form>

        <p style={{ textAlign: 'center', marginTop: 20, fontSize: 13, color: 'var(--c-text-3)' }}>
          <Link to="/">← Back to home</Link>
        </p>
      </div>
    </div>
  );
}
