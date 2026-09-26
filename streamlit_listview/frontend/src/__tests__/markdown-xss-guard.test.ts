import { describe, it, expect } from "vitest";
import { readFileSync, readdirSync } from "node:fs";
import { resolve, join, relative } from "node:path";

/*
 * Security guard test — locks down the component's highest-leverage XSS controls
 * so a future refactor cannot silently re-introduce a raw-HTML sink. This is a
 * source-text invariant check (it never imports the component), matching the
 * style of single-file-build.test.ts / notice.test.ts.
 *
 * Invariants asserted:
 *   1. No production source renders raw HTML — never `dangerouslySetInnerHTML`,
 *      never react-markdown's `allowDangerousHtml`, never an import of the
 *      raw-HTML renderers `rehype-raw` / `html-react-parser`.
 *   2. Markdown.tsx keeps `transformUri` wired as react-markdown's `urlTransform`
 *      — the single URL/scheme gate for every rendered link.
 *   3. `rehype-raw` / `html-react-parser` are not even declared dependencies, so
 *      they cannot be reached at all.
 *
 * These are the controls verified clean by the repo security review; this test
 * makes a regression fail loudly in CI rather than ship a raw-HTML XSS sink.
 */

const SRC_DIR = resolve(import.meta.dirname, "..");
const MARKDOWN_TSX = resolve(SRC_DIR, "components/Markdown.tsx");
const PACKAGE_JSON = resolve(SRC_DIR, "../package.json");

/** All shipped `.ts`/`.tsx` under src/, excluding tests, fixtures and ambient types. */
function productionSources(dir: string): string[] {
  const out: string[] = [];
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = join(dir, entry.name);
    if (entry.isDirectory()) {
      if (entry.name === "__tests__" || entry.name === "test") continue;
      out.push(...productionSources(full));
      continue;
    }
    if (!/\.tsx?$/.test(entry.name)) continue;
    if (/\.test\.tsx?$/.test(entry.name)) continue;
    if (/\.d\.ts$/.test(entry.name)) continue;
    out.push(full);
  }
  return out;
}

const SOURCES = productionSources(SRC_DIR);

/** Files whose text matches `re`, reported relative to src/ for readable failures. */
function offenders(re: RegExp): string[] {
  return SOURCES.filter((f) => re.test(readFileSync(f, "utf8"))).map((f) =>
    relative(SRC_DIR, f),
  );
}

describe("markdown XSS guard — no raw-HTML sink", () => {
  it("collected at least the markdown renderer (sanity: scan is non-empty)", () => {
    expect(SOURCES.length).toBeGreaterThan(0);
    expect(SOURCES.map((f) => relative(SRC_DIR, f))).toContain(
      relative(SRC_DIR, MARKDOWN_TSX),
    );
  });

  it("no production source uses dangerouslySetInnerHTML", () => {
    expect(offenders(/dangerouslySetInnerHTML/)).toEqual([]);
  });

  it("no production source enables react-markdown's allowDangerousHtml", () => {
    expect(offenders(/allowDangerousHtml/)).toEqual([]);
  });

  it("no production source imports a raw-HTML renderer (rehype-raw / html-react-parser)", () => {
    expect(offenders(/from\s+["']rehype-raw["']/)).toEqual([]);
    expect(offenders(/from\s+["']html-react-parser["']/)).toEqual([]);
  });
});

describe("markdown XSS guard — transformUri is the sole URL gate", () => {
  const markdown = readFileSync(MARKDOWN_TSX, "utf8");

  it("Markdown.tsx wires transformUri as react-markdown's urlTransform", () => {
    expect(markdown).toMatch(/urlTransform=\{\s*transformUri\s*\}/);
  });

  it("Markdown.tsx imports transformUri from the links module", () => {
    expect(markdown).toMatch(
      /import\s+\{[^}]*\btransformUri\b[^}]*\}\s+from\s+["'][^"']*links["']/,
    );
  });
});

describe("markdown XSS guard — dependencies", () => {
  it("does not declare rehype-raw or html-react-parser as dependencies", () => {
    const pkg = JSON.parse(readFileSync(PACKAGE_JSON, "utf8"));
    const declared = Object.keys({
      ...(pkg.dependencies ?? {}),
      ...(pkg.devDependencies ?? {}),
    });
    expect(declared).not.toContain("rehype-raw");
    expect(declared).not.toContain("html-react-parser");
  });
});
