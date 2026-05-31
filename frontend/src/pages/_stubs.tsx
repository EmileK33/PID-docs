// Stub page components for every §1.6 SPA route.
//
// Each stub renders a single <h1>{routeName} (stub)</h1> placeholder. Real UX
// arrives in S3-A..S3-H, which create their own page modules under
// frontend/src/pages/** and frontend/src/features/** and swap them into
// router.tsx (the documented exception to "do not touch entry points").
//
// Do NOT add business logic here.
import type { ReactElement } from 'react';

function makeStub(routeName: string): () => ReactElement {
  return function StubPage(): ReactElement {
    return (
      <main style={{ padding: '2rem', fontFamily: 'system-ui, sans-serif' }}>
        <h1>{routeName} (stub)</h1>
        <p>This page is a Phase-0 scaffold placeholder.</p>
      </main>
    );
  };
}

// P0 routes
export const RegisterStub = makeStub('/register');
export const LoginStub = makeStub('/login');
export const VerifyEmailStub = makeStub('/verify-email');
export const DashboardStub = makeStub('/dashboard');
export const UploadStub = makeStub('/upload');
export const ReviewStub = makeStub('/drawings/:id/review');
export const AccountStub = makeStub('/account');
export const SubscriptionStub = makeStub('/subscription');

// P1 routes
export const TeamsStub = makeStub('/teams');
export const TeamMembersStub = makeStub('/teams/:id/members');
export const TeamInviteAcceptStub = makeStub('/teams/invite/accept');
export const ComparisonStub = makeStub('/comparisons/:id');

// Fallback
export const NotFoundStub = makeStub('404 Not Found');
