import { describe, it, expect } from "vitest";
import { existsSync, readdirSync, readFileSync } from "node:fs";
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

  it("ships the licenses of the bundled packages", () => {
    const text = readFileSync(
      resolve(buildDir, "THIRD_PARTY_LICENSES.md"),
      "utf8",
    );
    expect(text).toMatch(/^## react - \d+\.\d+\.\d+ \(MIT\)$/m);
  });

  it("keeps the render chunks' content-visibility rule through the CSS minifier", () => {
    // lightningcss rewrites what it understands (it breaks prefers-color-scheme
    // and light-dark() in the shadow tree, see CLAUDE.md), so the declarations
    // the off-screen skipping depends on are checked in the built sheet itself.
    const name = readdirSync(buildDir).find((f) =>
      /^index-.*\.css$/.test(f),
    ) as string;
    const built = readFileSync(resolve(buildDir, name), "utf8");
    expect(built).toMatch(/\.listview-chunk\{[^}]*content-visibility:auto/);
    expect(built).toMatch(
      /\.listview-chunk\{[^}]*contain-intrinsic-block-size:calc\(/,
    );
  });
});
