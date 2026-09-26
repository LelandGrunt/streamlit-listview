import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

/**
 * Vitest configuration for the listview frontend unit tests.
 *
 * Kept separate from vite.config.ts (the library/build config) so the test
 * environment never affects the production bundle. Uses jsdom so React
 * components and hooks can be rendered with @testing-library/react.
 */
export default defineConfig({
  plugins: [react()],
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    include: ["src/**/*.{test,spec}.{ts,tsx}"],
    css: false,
    coverage: {
      provider: "v8",
      reporter: ["text", "html"],
      include: ["src/**/*.{ts,tsx}"],
      exclude: [
        "src/**/*.{test,spec}.{ts,tsx}", // the tests themselves
        "src/**/*.d.ts", // ambient type declarations
        "src/types.ts", // type-only module (no runtime code)
        "src/test/**", // test harness / setup
      ],
      // The suite is exhaustive; unreachable defense-in-depth guards carry
      // inline `/* v8 ignore */` markers, so 100% is the enforced floor.
      thresholds: {
        statements: 100,
        branches: 100,
        functions: 100,
        lines: 100,
      },
    },
  },
});
