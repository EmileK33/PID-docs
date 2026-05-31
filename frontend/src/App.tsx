// Root SPA component. Wires the lazy route tree from router.tsx, wrapped in
// <AuthProvider> so Nav/GraceBanner/ProtectedRoute can call useAuth().
//
// [LOAD-BEARING entry point] S1-F wraps pages with <Layout>/<ProtectedRoute>
// at the route level (in router.tsx). AuthProvider lives here so the whole
// tree (including Layout's Nav/GraceBanner) is inside the auth context.
import type { ReactElement } from 'react';
import { RouterProvider } from 'react-router-dom';

import { AuthProvider } from './auth/AuthContext';
import { router } from './router';

export default function App(): ReactElement {
  return (
    <AuthProvider>
      <RouterProvider router={router} />
    </AuthProvider>
  );
}
