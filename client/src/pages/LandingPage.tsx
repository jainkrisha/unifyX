import React from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export function LandingPage() {
  const { token } = useAuth();

  const renderHeaderActions = () => {
    if (token) {
      return (
        <Link to="/departments" className="lp-btn lp-btn-primary">
          Go to Dashboard →
        </Link>
      );
    }
    return (
      <>
        <Link to="/login" className="lp-btn lp-btn-ghost">Sign in</Link>
        <Link to="/signup" className="lp-btn lp-btn-primary">Sign up</Link>
      </>
    );
  };

  const renderHeroActions = () => {
    if (token) {
      return (
        <Link to="/departments" className="lp-btn lp-btn-primary btn-lg">
          Go to Dashboard →
        </Link>
      );
    }
    return (
      <>
        <Link to="/signup" className="lp-btn lp-btn-primary btn-lg" id="landing-signup-btn">Sign up ↗</Link>
        <Link to="/login" className="lp-btn lp-btn-ghost btn-lg" id="landing-signin-btn">Sign in</Link>
      </>
    );
  };

  const renderCtaActions = () => {
    if (token) {
      return (
        <Link to="/departments" className="lp-btn lp-btn-primary btn-lg">
          Go to Dashboard →
        </Link>
      );
    }
    return (
      <>
        <Link to="/signup" className="lp-btn lp-btn-primary btn-lg">Sign up ↗</Link>
        <Link to="/login" className="lp-btn lp-btn-ghost btn-lg" style={{ borderColor: '#3A4468', color: '#fff' }}>Sign in</Link>
      </>
    );
  };

  return (
    <div className="lp-container">
      <header>
        <div className="header-inner">
          <div className="logo">
            <span className="logo-mark">
              <svg viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2">
                <circle cx="12" cy="12" r="3" />
                <circle cx="5" cy="6" r="2" />
                <circle cx="19" cy="6" r="2" />
                <circle cx="5" cy="18" r="2" />
                <line x1="7" y1="7" x2="10" y2="10" />
                <line x1="17" y1="7" x2="14" y2="10" />
                <line x1="7" y1="17" x2="10" y2="14" />
              </svg>
            </span>
            UnifyX
          </div>
          <nav>
            <a href="#about">About</a>
            <a href="#how-it-works">How it works</a>
            <a href="#security">Security</a>
          </nav>
          <div className="header-actions">
            {renderHeaderActions()}
          </div>
        </div>
      </header>

      <section className="hero" style={{ borderTop: 'none' }}>
        <div className="eyebrow"><span className="dot"></span>Built for CODEISSANCE 2026 · PS-04</div>
        <h1 className="headline">One customer, scattered across five systems.<br /><span className="accent">Now one record, with proof.</span></h1>
        <p className="sub">UnifyX resolves fragmented identities across Equity, Mutual Funds, Insurance, Loans and Wealth into a single, explainable customer profile — and surfaces the next opportunity it unlocks.</p>
        <div className="hero-actions">
          {renderHeroActions()}
        </div>

        {/* Demo credentials — only visible when not logged in */}
        {!token && (
          <div className="demo-credentials-card" id="demo-credentials">
            <div className="demo-cred-header">
              <span className="demo-cred-icon">🔑</span>
              <span>Demo Credentials</span>
            </div>
            <div className="demo-cred-grid">
              {[
                { role: 'Admin',   email: 'admin@unifyx.com',   password: 'admin123',   badge: 'admin' },
                { role: 'Manager', email: 'manager@unifyx.com', password: 'manager123', badge: 'mgr' },
                { role: 'RM 1',    email: 'rm1@unifyx.com',     password: 'rm123',      badge: 'rm' },
                { role: 'RM 2',    email: 'rm2@unifyx.com',     password: 'rm123',      badge: 'rm' },
              ].map(cred => (
                <div key={cred.email} className="demo-cred-row">
                  <span className={`demo-cred-badge badge-${cred.badge}`}>{cred.role}</span>
                  <code className="demo-cred-email">{cred.email}</code>
                  <code className="demo-cred-pw">{cred.password}</code>
                </div>
              ))}
            </div>
            <div className="demo-cred-hint">Use these to sign in and explore different access scopes</div>
          </div>
        )}

        <div className="merge-stage">
          <div className="source-chips">
            <div className="chip eq"><span className="tag">Equity</span><span className="val mono">R. Sharma · PAN A1B2C3</span></div>
            <div className="chip ins"><span className="tag">Insurance</span><span className="val mono">Rohan S · PAN A1B2C3</span></div>
            <div className="chip mf"><span className="tag">Mutual funds</span><span className="val mono">Rohan Sharma · PAN A1B2C3</span></div>
          </div>
          <div className="arrow-col">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M5 12h14M13 6l6 6-6 6" /></svg>
            <span>match</span>
          </div>
          <div className="golden-card">
            <div className="tag"><span>Golden customer</span><span>GC-00417</span></div>
            <div className="name">Rohan Sharma</div>
            <div className="conf-row"><span className="mono">94%</span><div className="conf-bar"><div className="conf-fill"></div></div><span>confidence</span></div>
          </div>
        </div>
      </section>

      <div className="trust-row">
        <div className="trust-pill rbac"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="4" y="10" width="16" height="10" rx="2" /><path d="M8 10V7a4 4 0 1 1 8 0v3" /></svg>Role-based access control</div>
        <div className="trust-pill mask"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7-10-7-10-7z" /><circle cx="12" cy="12" r="3" /></svg>PII masked by default</div>
        <div className="trust-pill audit"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M9 11l3 3L22 4" /><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" /></svg>Every change audited</div>
      </div>

      <section id="about">
        <div className="section-head">
          <span className="kicker">About</span>
          <h2>Built for a problem banks can't join their way out of</h2>
          <p>The same customer often exists five times over — once per product line — with mismatched PANs, mobiles and names. UnifyX doesn't guess. It scores, explains, and asks for review when it isn't sure.</p>
        </div>
        <div className="about-grid">
          <div>
            <p>A diversified financial-services organization holds the same customer across Equity, Mutual Funds, Insurance, Loans and Wealth systems — with identifiers that are missing, inconsistently formatted, or in outright conflict.</p>
            <p>UnifyX standardizes those records, matches them deterministically where identifiers are exact and probabilistically where they aren't, and never merges a low-confidence pair silently. Every match, every conflict, and every recommendation carries a stated reason.</p>
          </div>
          <div className="stat-list">
            <div className="stat"><div className="num">5</div><div className="lbl">Source systems unified into one profile</div></div>
            <div className="stat"><div className="num">99.5%</div><div className="lbl">Held-out match accuracy, honestly reported — not rounded to a suspicious 100</div></div>
            <div className="stat"><div className="num">0.60</div><div className="lbl">Confidence threshold below which a match always routes to manual review, never auto-merges</div></div>
          </div>
        </div>
      </section>

      <section id="how-it-works">
        <div className="section-head">
          <span className="kicker">How it works</span>
          <h2>A pipeline, not a database join</h2>
          <p>Five stages, each config-driven, each one explaining its own decision.</p>
        </div>
        <div className="steps">
          <div className="step"><div className="n">01</div><div><h3>Normalize</h3><p>Mobile, email and identifiers are standardized before anything is compared.</p></div></div>
          <div className="step"><div className="n">02</div><div><h3>Match and score</h3><p>Exact PAN match where available; otherwise a trained confidence score from name, DOB, address and identifier signals.</p></div></div>
          <div className="step"><div className="n">03</div><div><h3>Resolve conflicts</h3><p>Disagreements between sources keep their provenance — auto-resolved by rule, or routed to a review queue.</p></div></div>
          <div className="step"><div className="n">04</div><div><h3>Build the golden profile</h3><p>Matched records combine into one customer, with every source system still traceable.</p></div></div>
          <div className="step"><div className="n">05</div><div><h3>Surface the opportunity</h3><p>Eligibility and scoring run against configurable rules — never a hardcoded recommendation.</p></div></div>
        </div>
      </section>

      <section id="security">
        <div className="section-head">
          <span className="kicker">Security</span>
          <h2>What you see depends on who you are</h2>
          <p>Access is scoped and enforced on the backend — the interface only reflects what the API already allows.</p>
        </div>
        <div className="role-grid">
          <div className="role-card rm"><span className="badge">RM</span><h3>Relationship manager</h3><p>Sees their own assigned customers only — profiles, matches, and opportunities for that book alone.</p></div>
          <div className="role-card mgr"><span className="badge">Manager</span><h3>Team manager</h3><p>Sees their reporting hierarchy — every RM under them, plus the shared review queue.</p></div>
          <div className="role-card admin"><span className="badge">Admin</span><h3>Administrator</h3><p>Sees all records, runs the matching pipeline, and is the only role that can change a threshold or rule.</p></div>
        </div>
      </section>

      <section className="cta-band">
        <h2>See your customers as one, not five</h2>
        <p>Sign in to run the pipeline, or create an account to explore the demo.</p>
        <div className="hero-actions" style={{ marginBottom: 0 }}>
          {renderCtaActions()}
        </div>
      </section>

      <footer>
        <div className="footer-inner">
          <div className="footer-top">
            <div className="logo">
              <span className="logo-mark">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <circle cx="12" cy="12" r="3" />
                  <circle cx="5" cy="6" r="2" />
                  <circle cx="19" cy="6" r="2" />
                  <circle cx="5" cy="18" r="2" />
                  <line x1="7" y1="7" x2="10" y2="10" />
                  <line x1="17" y1="7" x2="14" y2="10" />
                  <line x1="7" y1="17" x2="10" y2="14" />
                </svg>
              </span>
              UnifyX
            </div>
            <div className="footer-links">
              <div>
                <h4>Product</h4>
                <a href="#about">About</a>
                <a href="#how-it-works">How it works</a>
                <a href="#security">Security</a>
              </div>
              <div>
                <h4>Access</h4>
                <Link to="/login">Sign in</Link>
                <Link to="/signup">Sign up</Link>
              </div>
              <div>
                <h4>Roles</h4>
                <a href="#security">RM · own customers</a>
                <a href="#security">Manager · hierarchy</a>
                <a href="#security">Admin · all records</a>
              </div>
            </div>
          </div>
          <div className="footer-bottom">
            <span>UnifyX — built for CODEISSANCE 2026, PS-04</span>
            <span>Scoping enforced on the backend. The UI reflects what the API returns.</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
