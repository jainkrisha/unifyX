import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { authApi, LoginResponse } from '../api/client';

interface AuthState {
  token: string | null;
  user: { id: number; email: string; role: 'RM' | 'MANAGER' | 'ADMIN' } | null;
}

interface AuthContextValue extends AuthState {
  login: (email: string, password: string) => Promise<LoginResponse>;
  logout: () => void;
  isAdmin: boolean;
  isManager: boolean;
  isRM: boolean;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>(() => {
    const token = localStorage.getItem('unifyx_token');
    const raw = localStorage.getItem('unifyx_user');
    const user = raw ? JSON.parse(raw) : null;
    return { token, user };
  });

  async function login(email: string, password: string): Promise<LoginResponse> {
    const res = await authApi.login(email, password);
    // Role ALWAYS comes from server — never chosen by the client
    localStorage.setItem('unifyx_token', res.access_token);
    localStorage.setItem('unifyx_user', JSON.stringify({
      id: res.user_id,
      email: res.email,
      role: res.role,
    }));
    setState({
      token: res.access_token,
      user: { id: res.user_id, email: res.email, role: res.role },
    });
    return res;
  }

  function logout() {
    localStorage.removeItem('unifyx_token');
    localStorage.removeItem('unifyx_user');
    setState({ token: null, user: null });
  }

  const role = state.user?.role;
  return (
    <AuthContext.Provider value={{
      ...state,
      login,
      logout,
      isAdmin: role === 'ADMIN',
      isManager: role === 'MANAGER',
      isRM: role === 'RM',
    }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider');
  return ctx;
}
