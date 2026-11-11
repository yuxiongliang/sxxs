import { join } from 'node:path';
import { defineConfig } from 'vitest/config';

/**
 * Browser-free lane for pure logic (access rules and friends).
 *
 * `vitest.config.ts` runs everything inside Playwright's browser mode with a DOM
 * setup file (`tests/setupTests.ts` imports `vitest-browser-react`), so plain
 * functions cannot run there in a Node worker. Files named `*.node.test.ts` are
 * excluded from that lane and run here instead: fast, no browser, no DOM.
 */
export default defineConfig({
  resolve: {
    alias: {
      '@': join(__dirname, 'src'),
      '@root': join(__dirname),
      '@@': join(__dirname, 'src', '.umi'),
    },
  },
  test: {
    globals: true,
    environment: 'node',
    include: ['src/**/*.node.test.ts'],
    exclude: ['node_modules', 'dist', 'src/.umi/**', 'src/.umi-production/**'],
    passWithNoTests: true,
  },
});
