import { describe, it, expect } from "vitest";
import { existsSync, readdirSync } from "node:fs";
import { resolve } from "node:path";

// Verifies the V2 single-file invariant AFTER a production build:
// exactly one index-*.js and one index-*.css in build/. The markdown plugins
// are statically imported (no dynamic import()), so adding them must NOT
// introduce a second JS chunk.
const buildDir = resolve(import.meta.dirname, "../../build");

describe("single-file build output", () => {
  it("has a build/ directory (run `npm run build` first)", () => {
    expect(existsSync(buildDir)).toBe(true);
  });

  it("emits exactly one index-*.js", () => {
    const js = readdirSync(buildDir).filter((f) => /^index-.*\.js$/.test(f));
    expect(js).toHaveLength(1);
  });

  it("emits exactly one index-*.css", () => {
    const css = readdirSync(buildDir).filter((f) => /^index-.*\.css$/.test(f));
    expect(css).toHaveLength(1);
  });
});
