import React from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import './index.css';

import { AuthProvider } from './context/AuthContext';
import { ProtectedRoute } from './components/ProtectedRoute';
import { TopBar } from './components/TopBar';

import { LandingPage }       from './pages/LandingPage';
import { LoginPage }         from './pages/LoginPage';
import { SignupPage }        from './pages/SignupPage';
import { DepartmentsPage }   from './pages/DepartmentsPage';
import { CustomersListPage } from './pages/CustomersListPage';
import { Customer360Page }   from './pages/Customer360';
import { ReviewQueuePage }   from './pages/ReviewQueue';
import { ConfigurationPage } from './pages/Configuration';
import { AuditLogPage }      from './pages/AuditLogPage';
import { Opportunities }     from './pages/Opportunities';

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <div className="app-shell">
      <TopBar />
      <main>{children}</main>
    </div>
  );
}

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          {/* Public */}
          <Route path="/"       element={<LandingPage />} />
          <Route path="/login"  element={<LoginPage />} />
          <Route path="/signup" element={<SignupPage />} />

          {/* Protected — any authenticated role */}
          <Route path="/departments" element={
            <ProtectedRoute>
              <Shell><DepartmentsPage /></Shell>
            </ProtectedRoute>
          } />

          <Route path="/customers" element={
            <ProtectedRoute>
              <Shell><CustomersListPage /></Shell>
            </ProtectedRoute>
          } />

          <Route path="/customers/:id" element={
            <ProtectedRoute>
              <Shell><Customer360Page /></Shell>
            </ProtectedRoute>
          } />

          <Route path="/opportunities" element={
            <ProtectedRoute>
              <Shell><Opportunities /></Shell>
            </ProtectedRoute>
          } />

          <Route path="/review-queue" element={
            <ProtectedRoute>
              <Shell><ReviewQueuePage /></Shell>
            </ProtectedRoute>
          } />

          {/* Admin-only routes — backend also enforces 403 */}
          <Route path="/config" element={
            <ProtectedRoute requiredRole="ADMIN">
              <Shell><ConfigurationPage /></Shell>
            </ProtectedRoute>
          } />

          <Route path="/audit-log" element={
            <ProtectedRoute requiredRole="ADMIN">
              <Shell><AuditLogPage /></Shell>
            </ProtectedRoute>
          } />

          {/* Fallback */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}

createRoot(document.getElementById('root')!).render(<App />);
