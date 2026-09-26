import { describe, it, expect } from "vitest";

import { isInSidebar } from "./container";

/**
 * Build the production DOM shape: a Streamlit container holding the
 * `display: contents` wrapper, the shadow host, and an open shadow root — which
 * is what `isolate_styles=True` hands the renderer as `parentElement`.
 */
function mountHost(containerTestId: string | null): ShadowRoot {
  const container = document.createElement("section");
  if (containerTestId !== null) {
    container.setAttribute("data-testid", containerTestId);
  }
  const host = document.createElement("div");
  host.setAttribute("data-testid", "stBidiComponentIsolated");
  container.appendChild(host);
  document.body.appendChild(container);
  return host.attachShadow({ mode: "open" });
}

describe("isInSidebar", () => {
  it("is true for a shadow root whose host sits inside the sidebar", () => {
    expect(isInSidebar(mountHost("stSidebar"))).toBe(true);
  });

  it("is false for a shadow root whose host sits in the main body", () => {
    expect(isInSidebar(mountHost("stMain"))).toBe(false);
  });

  // `closest()` does not cross a shadow boundary, so a lookup that forgets to
  // hop to `ShadowRoot.host` first returns null for BOTH containers and the
  // widget silently keeps its main-body colors in the sidebar. Asserting the
  // sidebar case above from a real ShadowRoot is what pins the hop.
  it("is true for a plain element host inside the sidebar (isolate_styles=False)", () => {
    const container = document.createElement("section");
    container.setAttribute("data-testid", "stSidebar");
    const parent = document.createElement("div");
    container.appendChild(parent);
    document.body.appendChild(container);
    expect(isInSidebar(parent)).toBe(true);
  });

  it("is false for a plain element host in the main body", () => {
    const container = document.createElement("section");
    container.setAttribute("data-testid", "stMain");
    const parent = document.createElement("div");
    container.appendChild(parent);
    document.body.appendChild(container);
    expect(isInSidebar(parent)).toBe(false);
  });

  // A detached tree has no Streamlit container above it at all. This is the
  // shape the unit tests themselves mount, so it must answer false rather than
  // throw on the missing ancestor.
  it("is false for a detached element", () => {
    expect(isInSidebar(document.createElement("div"))).toBe(false);
  });
});
