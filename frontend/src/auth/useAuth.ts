// useAuth — read the auth context. Throws if used outside <AuthProvider>.
//
// [LOAD-BEARING] Consumed by Nav, ProtectedRoute, GraceBanner and every
// authenticated S3-* page.
import { useContext } from 'react';

import { AuthContext, type AuthContextValue } from './AuthContext';

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error('useAuth must be used within an <AuthProvider>');
  }
  return ctx;
}

export default useAuth;
