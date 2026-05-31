// Root SPA component. Wires the lazy route tree from router.tsx.
//
// [LOAD-BEARING entry point] After merge this is a "do not touch" file. S1-F
// wraps pages with <Layout>/<ProtectedRoute> at the route level (in router.tsx),
// not here.
import type { ReactElement } from 'react';
import { RouterProvider } from 'react-router-dom';

import { router } from './router';

export default function App(): ReactElement {
  return <RouterProvider router={router} />;
}
