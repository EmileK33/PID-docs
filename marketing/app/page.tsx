// Marketing landing page stub ("/").
//
// S3-H delivers the real landing experience under app/(marketing)/page.tsx;
// per its acceptance criteria, that route group coexists with this stub without
// a Next.js duplicate-route build error.
export default function HomePage() {
  return (
    <main style={{ padding: '2rem', fontFamily: 'system-ui, sans-serif' }}>
      <h1>PID Analyzer (stub)</h1>
      <p>Marketing landing — Phase-0 scaffold placeholder.</p>
    </main>
  );
}
