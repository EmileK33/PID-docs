// Application router — single declarative route array, lazy-loaded pages.
//
// [LOAD-BEARING] This is the "do not touch entry point" router, with ONE
// documented exception: S3-* page sessions ARE permitted to edit this file to
// register their real pages. To keep that conflict-free, every route lives in
// the single `routes` array below with clearly marked `// SESSION: S3-x`
// insertion slots. Add lines at your slot; do not restructure the array.
//
// Every page is lazy-imported via React.lazy so each route code-splits.
import { lazy, Suspense, type ReactElement } from 'react';
import {
  createBrowserRouter,
  Navigate,
  type RouteObject,
} from 'react-router-dom';

// Scaffold stubs. S3 sessions replace these with real page modules by editing
// the matching `element` below (e.g. S3-A swaps RegisterStub → pages/auth/Register).
const RegisterStub = lazy(() =>
  import('./pages/_stubs').then((m) => ({ default: m.RegisterStub })),
);
const LoginStub = lazy(() =>
  import('./pages/_stubs').then((m) => ({ default: m.LoginStub })),
);
const VerifyEmailStub = lazy(() =>
  import('./pages/_stubs').then((m) => ({ default: m.VerifyEmailStub })),
);
const DashboardStub = lazy(() =>
  import('./pages/_stubs').then((m) => ({ default: m.DashboardStub })),
);
const UploadStub = lazy(() =>
  import('./pages/_stubs').then((m) => ({ default: m.UploadStub })),
);
const ReviewStub = lazy(() =>
  import('./pages/_stubs').then((m) => ({ default: m.ReviewStub })),
);
const AccountStub = lazy(() =>
  import('./pages/_stubs').then((m) => ({ default: m.AccountStub })),
);
const SubscriptionStub = lazy(() =>
  import('./pages/_stubs').then((m) => ({ default: m.SubscriptionStub })),
);
const TeamsStub = lazy(() =>
  import('./pages/_stubs').then((m) => ({ default: m.TeamsStub })),
);
const TeamMembersStub = lazy(() =>
  import('./pages/_stubs').then((m) => ({ default: m.TeamMembersStub })),
);
const TeamInviteAcceptStub = lazy(() =>
  import('./pages/_stubs').then((m) => ({ default: m.TeamInviteAcceptStub })),
);
const ComparisonStub = lazy(() =>
  import('./pages/_stubs').then((m) => ({ default: m.ComparisonStub })),
);
const NotFoundStub = lazy(() =>
  import('./pages/_stubs').then((m) => ({ default: m.NotFoundStub })),
);

function withSuspense(element: ReactElement): ReactElement {
  return <Suspense fallback={<div>Loading…</div>}>{element}</Suspense>;
}

// SINGLE declarative route array. §1.6 SPA routes.
export const routes: RouteObject[] = [
  // The marketing landing "/" is served by the separate Next.js app; in the
  // SPA, "/" redirects to the dashboard.
  { path: '/', element: <Navigate to="/dashboard" replace /> },

  // SESSION: S3-A — auth pages
  { path: '/register', element: withSuspense(<RegisterStub />) },
  { path: '/login', element: withSuspense(<LoginStub />) },
  { path: '/verify-email', element: withSuspense(<VerifyEmailStub />) },

  // SESSION: S3-B — drawing library
  { path: '/dashboard', element: withSuspense(<DashboardStub />) },

  // SESSION: S3-C — upload flow
  { path: '/upload', element: withSuspense(<UploadStub />) },

  // SESSION: S3-D — review canvas
  { path: '/drawings/:id/review', element: withSuspense(<ReviewStub />) },

  // SESSION: S3-E — account & consent
  { path: '/account', element: withSuspense(<AccountStub />) },

  // SESSION: S3-F — subscription & upgrade
  { path: '/subscription', element: withSuspense(<SubscriptionStub />) },

  // --- P1 routes ---
  { path: '/teams', element: withSuspense(<TeamsStub />) },
  { path: '/teams/:id/members', element: withSuspense(<TeamMembersStub />) },
  { path: '/teams/invite/accept', element: withSuspense(<TeamInviteAcceptStub />) },
  { path: '/comparisons/:id', element: withSuspense(<ComparisonStub />) },

  // Fallback
  { path: '*', element: withSuspense(<NotFoundStub />) },
];

export const router = createBrowserRouter(routes);
