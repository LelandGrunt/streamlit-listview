import { useEffect, useState } from "react";
import type { RefObject } from "react";

export type ColorScheme = "light" | "dark";

/**
 * Resolve the ACTIVE STREAMLIT THEME's color scheme ("light" | "dark") as seen
 * by the component, independent of the OS `prefers-color-scheme`.
 *
 * Streamlit applies `color-scheme` on the app root ([data-testid="stApp"])
 * from its active theme; that value inherits through the component's shadow
 * host into our tree, so reading the computed `color-scheme` of any element in
 * the component reflects Streamlit's theme — even when the OS scheme disagrees
 * (e.g. a dark Streamlit theme under a light OS). This is what lets the help
 * tooltip pick the same surface Streamlit's own tooltip uses (bgColor in light,
 * secondaryBackground in dark) rather than guessing from the OS.
 *
 * A theme switch mutates the app root, not the component, so we observe that
 * element (plus <html>) and re-read on attribute changes to stay live without a
 * Python rerun. Defaults to "light" until the first read (the help popover is
 * only shown on hover, well after mount, so there is no visible flash).
 *
 * Note: we cannot use the CSS `light-dark()` function here — the production
 * bundler (lightningcss) rewrites it into a `prefers-color-scheme` polyfill
 * whose helper custom properties are declared on the document `:root` and so
 * never reach the component's shadow tree, leaving the surface transparent.
 */
/**
 * Resolve a CSS `color-scheme` computed value to "light" | "dark".
 *
 * The value can be "normal" | "light" | "dark" | "light dark" | "dark light" |
 * "only light" | "only dark". The first concrete scheme listed is the preferred
 * one, so the two-value forms resolve to their leading keyword (NOT a naive
 * substring match on "dark", which would read "light dark" as dark). "normal"
 * and unrecognized/empty values fall back to "light".
 */
function resolveScheme(colorScheme: string): ColorScheme {
  for (const token of colorScheme.toLowerCase().split(/\s+/)) {
    if (token === "light" || token === "dark") {
      return token;
    }
  }
  return "light";
}

export function useColorScheme(ref: RefObject<HTMLElement | null>): ColorScheme {
  const [scheme, setScheme] = useState<ColorScheme>("light");

  useEffect(() => {
    const el = ref.current;
    if (!el) {
      return;
    }
    const read = () => {
      const cs = getComputedStyle(el).colorScheme || "";
      setScheme(resolveScheme(cs));
    };
    read();

    const doc = el.ownerDocument;
    const targets = [
      doc.querySelector('[data-testid="stApp"]'),
      doc.documentElement,
    ].filter((n): n is Element => n != null);
    const observer = new MutationObserver(read);
    for (const node of targets) {
      observer.observe(node, {
        attributes: true,
        attributeFilter: ["class", "style", "data-theme"],
      });
    }
    return () => observer.disconnect();
  }, [ref]);

  return scheme;
}
