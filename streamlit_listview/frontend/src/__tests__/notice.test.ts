import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

// NOTICE lives at the worktree root: ../../../../NOTICE relative to this file
// (src/__tests__ -> src -> frontend -> listview -> worktree root).
const notice = readFileSync(
  resolve(import.meta.dirname, "../../../../NOTICE"),
  "utf8",
);

describe("NOTICE attribution", () => {
  it("attributes the ported Streamlit code under Apache-2.0 with the source URL", () => {
    expect(notice).toContain("Streamlit");
    expect(notice).toMatch(/Apache License,?\s*Version 2\.0/i);
    expect(notice).toContain(
      "StreamlitMarkdown.tsx",
    );
    expect(notice).toContain(
      "https://github.com/streamlit/streamlit",
    );
  });

  it("attributes the react-feather HelpCircle glyph under MIT", () => {
    expect(notice).toContain("react-feather");
    expect(notice).toContain("HelpCircle");
    expect(notice).toMatch(/MIT/);
  });
});
