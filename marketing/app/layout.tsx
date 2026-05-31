// Root layout for the Next.js marketing site (App Router).
//
// [LOAD-BEARING entry point] After merge this becomes "do not touch". S3-H adds
// real marketing pages under app/(marketing)/, app/pricing/, etc. — those
// coexist with the app/page.tsx stub without a duplicate-route conflict.
import type { ReactNode } from 'react';

export const metadata = {
  title: 'PID Analyzer',
  description: 'Automated P&ID drawing analysis — symbol detection and table extraction.',
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
