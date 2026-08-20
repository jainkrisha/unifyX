import React, { ReactNode } from 'react';
import { Navigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

interface Props {
  children: ReactNode;
  requiredRole?: 'ADMIN' | 'MANAGER' | 'RM';
}

/** Redirects unauthenticated users to /login.
 *  If requiredRole is set and the user doesn't match, shows a 403 banner
 *  (the backend enforces it too — this is just a UX convenience, not the security boundary). */
export function ProtectedRoute({ children, requiredRole }: Props) {
  const { token, user } = useAuth();

  if (!token || !user) {
    return <Navigate to="/login" replace />;
  }

  if (requiredRole && user.role !== requiredRole) {
    return (
      <div className="page-content">
        <div className="banner banner-error" role="alert" style={{ marginTop: 24 }}>
          <span className="banner-icon">🔒</span>
          <div>
            <strong>Access denied</strong>
            <br />
            This page requires the <strong>{requiredRole}</strong> role. You are signed in as{' '}
            <strong>{user.role}</strong>. The backend will also 403 any direct API calls.
          </div>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
