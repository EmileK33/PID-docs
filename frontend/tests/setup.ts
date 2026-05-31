// Vitest setup — runs before every test file.
import '@testing-library/jest-dom/vitest';
import { cleanup } from '@testing-library/react';
import { afterEach } from 'vitest';

// React Testing Library auto-cleanup (unmounts trees, runs effect cleanups).
afterEach(() => {
  cleanup();
});
