import React from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export function TopBar() {
  const { user, logout, isAdmin, isManager } = useAuth();
  const navigate = useNavigate();

  function handleLogout() {
    logout();
    navigate('/');
  }

  const roleBadgeClass =
    isAdmin ? 'role-badge-admin' :
    isManager ? 'role-badge-manager' :
    'role-badge-rm';

  return (
    <header className="topbar">
      <div className="topbar-brand">
        <span className="topbar-brand-dot" />
        UnifyX
      </div>
      <nav className="topbar-nav">
        <NavLink to="/departments" className={({ isActive }) => isActive ? 'active' : ''}>Departments</NavLink>
        <NavLink to="/customers" className={({ isActive }) => isActive ? 'active' : ''}>Customers</NavLink>
        <NavLink to="/review-queue" className={({ isActive }) => isActive ? 'active' : ''}>Review Queue</NavLink>
        {isAdmin && <NavLink to="/config" className={({ isActive }) => isActive ? 'active' : ''}>Config</NavLink>}
        {isAdmin && <NavLink to="/audit-log" className={({ isActive }) => isActive ? 'active' : ''}>Audit Log</NavLink>}
      </nav>
      <div className="topbar-right">
        {user && (
          <>
            <span style={{ fontSize: 12, color: 'var(--c-text-3)' }}>{user.email}</span>
            <span className={`topbar-role-badge ${roleBadgeClass}`}>{user.role}</span>
            <button className="btn btn-ghost btn-sm" onClick={handleLogout}>Sign out</button>
          </>
        )}
      </div>
    </header>
  );
}
