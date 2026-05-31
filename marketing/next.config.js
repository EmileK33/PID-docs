/** @type {import('next').NextConfig} */
// Next.js 14+ App Router config for the marketing site (separate deployment
// from the SPA per §1.8 — SSR required for NFR-17 SEO).
const nextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
};

module.exports = nextConfig;
