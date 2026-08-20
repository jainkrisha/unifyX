import React from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export function LandingPage() {
  const { token } = useAuth();

  return (
    <div className="landing">
      <div className="landing-logo">UnifyX</div>
      <p className="landing-tagline">
        Customer Intelligence Platform — unified identity across financial source systems
      </p>

      {/* PS-04 mandatory security posture badges — visible to everyone on the landing page */}
      <div className="landing-badges">
        <div className="landing-badge">
          <span>🔐</span>
          Role-based access control
        </div>
        <div className="landing-badge">
          <span>🎭</span>
          PII masked by default
        </div>
        <div className="landing-badge">
          <span>📋</span>
          Every change audited
        </div>
      </div>

      <div className="landing-actions">
        {token ? (
          <Link to="/departments" className="btn btn-primary btn-lg">
            Go to Dashboard →
          </Link>
        ) : (
          <>
            <Link to="/login" className="btn btn-primary btn-lg" id="landing-signin-btn">
              Sign in
            </Link>
            <Link to="/signup" className="btn btn-outline btn-lg" id="landing-signup-btn">
              Sign up
            </Link>
          </>
        )}
      </div>

      <div style={{ marginTop: 48, maxWidth: 520, textAlign: 'center' }}>
        <p style={{ fontSize: 12, color: 'var(--c-text-4)', lineHeight: 1.7 }}>
          Roles: <strong>RM</strong> sees own customers only · <strong>Manager</strong> sees their RM hierarchy ·{' '}
          <strong>Admin</strong> sees all records and can run the identity-matching pipeline.
          All scoping is enforced on the backend; the UI reflects what the API returns.
        </p>
      </div>
    </div>
  );
}
