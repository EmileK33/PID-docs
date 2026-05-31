// Layout — app chrome wrapper.
//
// Renders <Nav> at the top, <GraceBanner> below it (self-hiding when not in a
// grace period), then page children inside the max-width `.app-container`.
import type { ReactElement, ReactNode } from 'react';

import { GraceBanner } from './GraceBanner';
import { Nav } from './Nav';

export function Layout({ children }: { children: ReactNode }): ReactElement {
  return (
    <div className="app-shell">
      <Nav />
      <GraceBanner />
      <main className="app-container">{children}</main>
    </div>
  );
}

export default Layout;
