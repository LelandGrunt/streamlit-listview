import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

/*
 * License guard. The bundle carries the code of every npm package that the
 * frontend imports, and the wheel ships the bundle, so each package that can
 * reach the bundle needs a license that permits shipping it. Dev-only packages
 * (`dev: true` in the lockfile) never reach the bundle and are exempt. A
 * package with another license needs the maintainer's decision before it
 * joins ALLOWED. THIRD_PARTY_LICENSES.md, written by the build, carries the
 * license texts.
 */

const ALLOWED = new Set([
  "MIT",
  "ISC",
  "Apache-2.0",
  "BSD-2-Clause",
  "BSD-3-Clause",
  "0BSD",
]);

interface LockEntry {
  /** An SPDX expression. npm copies the legacy object form of a package's
   *  license field into the lockfile as it is. */
  license?: unknown;
  dev?: boolean;
  devOptional?: boolean;
}

/** Whether an SPDX expression permits shipping: one OR alternative whose AND
 *  terms are all allowed. */
function permits(expression: string): boolean {
  const bare = expression.trim().replace(/^\((.*)\)$/, "$1");
  // A mix of OR and AND, or a group inside, needs SPDX's precedence rules: a
  // maintainer decides such a package by hand.
  if (/[()]/.test(bare) || (bare.includes(" OR ") && bare.includes(" AND "))) {
    return false;
  }
  return bare
    .split(" OR ")
    .some((alternative) =>
      alternative.split(" AND ").every((term) => ALLOWED.has(term.trim())),
    );
}

/** The license field as the report spells it. */
function licenseText(license: unknown): string {
  if (license === undefined) {
    return "no license";
  }
  return typeof license === "string" ? license : JSON.stringify(license);
}

/** The packages that can ship without a permitted license, as "path (license)". */
function unshippable(packages: Record<string, LockEntry>): string[] {
  return Object.entries(packages)
    .filter(([path, entry]) => path !== "" && entry.dev !== true)
    .filter(
      ([, entry]) =>
        typeof entry.license !== "string" || !permits(entry.license),
    )
    .map(([path, entry]) => `${path} (${licenseText(entry.license)})`);
}

describe("license allowlist", () => {
  it("permits a listed license", () => {
    expect(permits("MIT")).toBe(true);
  });

  it("rejects an unlisted license", () => {
    expect(permits("GPL-3.0-only")).toBe(false);
  });

  it("permits an OR expression with one listed alternative", () => {
    expect(permits("(MIT OR GPL-3.0-only)")).toBe(true);
  });

  it("rejects an AND expression with an unlisted term", () => {
    expect(permits("(MIT AND GPL-3.0-only)")).toBe(false);
  });

  it("permits an AND expression of listed terms", () => {
    expect(permits("MIT AND ISC")).toBe(true);
  });

  it("rejects an expression that mixes OR and AND, for a maintainer to decide", () => {
    // The AND binds the whole OR group here: LGPL applies whichever
    // alternative a consumer picks, so reading MIT alone would pass copyleft.
    expect(permits("(MIT OR GPL-3.0-only) AND LGPL-2.1-only")).toBe(false);
    expect(permits("MIT OR (ISC AND Apache-2.0)")).toBe(false);
  });

  it("skips the root entry and the dev-only packages", () => {
    expect(
      unshippable({
        "": {},
        "node_modules/a": { license: "GPL-3.0-only", dev: true },
      }),
    ).toEqual([]);
  });

  it("checks a devOptional package as one that ships", () => {
    expect(
      unshippable({
        "node_modules/b": { license: "GPL-3.0-only", devOptional: true },
      }),
    ).toEqual(["node_modules/b (GPL-3.0-only)"]);
  });

  it("reports a shipped package without a license", () => {
    expect(unshippable({ "node_modules/c": {} })).toEqual([
      "node_modules/c (no license)",
    ]);
  });

  it("reports a license that is not an SPDX string, as the lockfile spells it", () => {
    // Older packages wrote `"license": {"type": ..., "url": ...}`; npm copies
    // the object into the lockfile as it is.
    expect(
      unshippable({ "node_modules/d": { license: { type: "MIT" } } }),
    ).toEqual(['node_modules/d ({"type":"MIT"})']);
  });

  it("finds a permitted license for every package that can ship", () => {
    const lock = JSON.parse(
      readFileSync(
        resolve(import.meta.dirname, "../../package-lock.json"),
        "utf8",
      ),
    ) as { packages: Record<string, LockEntry> };
    expect(unshippable(lock.packages)).toEqual([]);
  });
});
