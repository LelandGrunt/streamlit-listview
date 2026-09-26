import { describe, it, expect, vi, afterEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import type { RefObject } from "react";
import { useColorScheme } from "./useColorScheme";

/** Build a RefObject pointing at a fresh (detached) element. */
function elementRef(): RefObject<HTMLElement> {
  return { current: document.createElement("div") };
}

/** Mock getComputedStyle so the hook reads a controlled color-scheme. */
function mockColorScheme(get: () => string) {
  vi.spyOn(window, "getComputedStyle").mockImplementation(
    () => ({ colorScheme: get() }) as unknown as CSSStyleDeclaration,
  );
}

describe("useColorScheme", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    document.body.innerHTML = "";
  });

  it("reports light when the inherited color-scheme is light", () => {
    mockColorScheme(() => "light");
    const { result } = renderHook(() => useColorScheme(elementRef()));
    expect(result.current).toBe("light");
  });

  it("reports dark when the inherited color-scheme is dark", () => {
    mockColorScheme(() => "dark");
    const { result } = renderHook(() => useColorScheme(elementRef()));
    expect(result.current).toBe("dark");
  });

  it("treats an empty/unsupported color-scheme as light", () => {
    mockColorScheme(() => "");
    const { result } = renderHook(() => useColorScheme(elementRef()));
    expect(result.current).toBe("light");
  });

  it("treats the two-value 'light dark' form as light (first concrete scheme wins)", () => {
    // `color-scheme: light dark` means the element supports both, preferring
    // light. A naive substring match on "dark" wrongly classified it as dark.
    mockColorScheme(() => "light dark");
    const { result } = renderHook(() => useColorScheme(elementRef()));
    expect(result.current).toBe("light");
  });

  it("treats 'dark light' as dark (first concrete scheme wins)", () => {
    mockColorScheme(() => "dark light");
    const { result } = renderHook(() => useColorScheme(elementRef()));
    expect(result.current).toBe("dark");
  });

  it("treats 'only dark' as dark", () => {
    mockColorScheme(() => "only dark");
    const { result } = renderHook(() => useColorScheme(elementRef()));
    expect(result.current).toBe("dark");
  });

  it("stays light (no throw) when the ref is null", () => {
    mockColorScheme(() => "dark");
    const { result } = renderHook(() =>
      useColorScheme({ current: null } as RefObject<HTMLElement | null>),
    );
    expect(result.current).toBe("light");
  });

  it("re-reads when the app root's attributes change (live theme switch)", async () => {
    const app = document.createElement("div");
    app.setAttribute("data-testid", "stApp");
    document.body.appendChild(app);

    let scheme = "light";
    mockColorScheme(() => scheme);

    const { result } = renderHook(() => useColorScheme(elementRef()));
    expect(result.current).toBe("light");

    // Streamlit applies the dark theme on the app root; the observer re-reads.
    scheme = "dark";
    app.setAttribute("class", "dark-theme");

    await waitFor(() => expect(result.current).toBe("dark"));
  });
});
