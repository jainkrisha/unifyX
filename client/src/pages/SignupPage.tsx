import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { ApiErrorBanner } from '../components/ApiErrorBanner';

/**
 * Sign-up page — kept simple because the API's POST /auth/users requires ADMIN role.
 * This page explains the constraint so it's not confusing in a demo.
 * An Admin can use this form via the app (they'd need to be logged in as Admin),
 * or you can point to it for context; the self-registration flow is intentionally
 * gated at the backend.
 */
export function SignupPage() {
  return (
    <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'var(--c-surface)', padding: 20 }}>
      <div className="card" style={{ width: '100%', maxWidth: 420 }}>
        <div style={{ textAlign: 'center', marginBottom: 24 }}>
          <div style={{ fontSize: 22, fontWeight: 800, color: 'var(--c-brand)', letterSpacing: -0.5, marginBottom: 4 }}>UnifyX</div>
          <p style={{ fontSize: 13, color: 'var(--c-text-3)' }}>Create an account</p>
        </div>

        <div className="banner banner-warn" style={{ marginBottom: 20 }}>
          <span className="banner-icon">🔐</span>
          <div style={{ fontSize: 13 }}>
            <strong>Admin-controlled registration</strong>
            <br />
            New user accounts require ADMIN approval. The backend's{' '}
            <code>POST /auth/users</code> endpoint requires an ADMIN JWT — self-registration is intentionally
            blocked as a security requirement (PS-04).
            <br /><br />
            Contact your system administrator to create your account.
          </div>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginTop: 8 }}>
          <div style={{ padding: '10px 14px', background: 'var(--c-surface)', borderRadius: 'var(--radius)', border: '1px solid var(--c-border)' }}>
            <div style={{ fontSize: 12, color: 'var(--c-text-3)', marginBottom: 4 }}>Demo credentials (ask your Admin)</div>
            <div style={{ fontSize: 13 }}>Admin, Manager, and RM accounts are pre-seeded via <code>bootstrap.py</code></div>
          </div>
        </div>

        <p style={{ textAlign: 'center', marginTop: 24, fontSize: 13, color: 'var(--c-text-3)' }}>
          Already have an account? <Link to="/login">Sign in</Link>
        </p>
        <p style={{ textAlign: 'center', marginTop: 8, fontSize: 13, color: 'var(--c-text-3)' }}>
          <Link to="/">← Back to home</Link>
        </p>
      </div>
    </div>
  );
}
