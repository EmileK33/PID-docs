// ProtectedRoute — gate authenticated routes.
//
// Renders children when AuthContext.user is set; otherwise redirects to
// /login?next={current pathname} (so the user returns where they were after
// signing in). While auth is still resolving, renders nothing.
import type { ReactElement, ReactNode } from 'react';
import { Navigate, useLocation } from 'react-router-dom';

import { useAuth } from '../auth/useAuth';

export function ProtectedRoute({ children }: { children: ReactNode }): ReactElement | null {
  const { user, loading } = useAuth();
  const location = useLocation();

  if (loading) return null;

  if (!user) {
    const next = encodeURIComponent(`${location.pathname}${location.search}`);
    return <Navigate to={`/login?next=${next}`} replace />;
  }

  return <>{children}</>;
}

export default ProtectedRoute;
