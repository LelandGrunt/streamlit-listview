import type { ComponentProps, ReactElement } from "react";
import type { ExtraProps } from "react-markdown";

/*
 * Ported from Streamlit's StreamlitMarkdown.tsx (Apache-2.0).
 * See the NOTICE file at the repo root for attribution.
 *
 * - LinkWithTargetBlank: anchor renderer used as react-markdown's `a` override.
 *   External links open in a new tab and get rel="noopener noreferrer";
 *   same-page "#..." anchors render as a plain <a> (no target/rel).
 * - transformUri: URL sanitizer. Markdown.tsx passes it as react-markdown's
 *   `urlTransform` prop, which REPLACES react-markdown's built-in
 *   defaultUrlTransform — so its protocol safelist no longer runs and this
 *   function is the only gate. It neutralizes script-capable / local-resource
 *   schemes (javascript:, vbscript:, file:, blob:, and data: except an image
 *   source's data:image/) to "#", while staying otherwise permissive to match
 *   Streamlit's own sanitizer. LinkWithTargetBlank also calls it defensively.
 */

const DANGEROUS_URL_SCHEMES = ["javascript:", "vbscript:", "file:", "blob:"];
// C0 control characters (U+0000..U+001F) can be injected mid-scheme to dodge a
// naive prefix check (e.g. a NUL or TAB inside the word "javascript"); strip
// them before comparing. This is the faithful Streamlit regex /[\x00-\x1F]/g,
// written with explicit \u escapes so it survives copy/paste intact. A literal
// space (U+0020) is NOT a C0 control char and is intentionally left alone.
const C0_CONTROL_CHARS_REGEX = /[\u0000-\u001F]/g;

/**
 * `key` is react-markdown's UrlTransform second argument: the URL attribute being
 * rewritten ("href", "src", …). It is optional because LinkWithTargetBlank calls
 * this defensively with the href alone — and an absent key must deny, since that
 * call site is an anchor.
 */
export function transformUri(href: string, key?: string): string {
  const normalizedHref = href
    .replace(C0_CONTROL_CHARS_REGEX, "")
    .toLowerCase()
    .trim();
  if (
    DANGEROUS_URL_SCHEMES.some((scheme) => normalizedHref.startsWith(scheme))
  ) {
    return "#";
  }
  // data: URIs can carry executable markup (data:text/html, SVG documents), so
  // data:image/... is allowed for an IMAGE SOURCE only — inline ![](data:image/…)
  // embeds and the :streamlit: logo need it, and an <img> renders an SVG document
  // without a script context. The very same URL in an anchor href IS a script
  // context once navigated to, so `key` gates the allowance on the attribute
  // react-markdown is rewriting; a[href] (and the key-less defensive call) falls
  // through to the "#" sentinel. Since raw HTML stays escaped, the only elements
  // that can carry a `src` here are <img> and our own logo image. Hardening, not
  // a live hole: browsers already block top-level data: navigation.
  if (
    normalizedHref.startsWith("data:") &&
    !(key === "src" && normalizedHref.startsWith("data:image/"))
  ) {
    return "#";
  }
  return href;
}

// react-markdown injects a `node` prop (the hast node) into every component
// override; it must not be spread onto the DOM element. Tiny inline `omit`
// avoids pulling in lodash (keeps the single-file bundle lean).
function omitNode<T extends { node?: unknown }>(
  props: T,
): Omit<T, "node"> {
  const { node: _node, ...rest } = props;
  return rest;
}

export type LinkWithTargetBlankProps = ComponentProps<"a"> & ExtraProps;

export function LinkWithTargetBlank(
  props: LinkWithTargetBlankProps,
): ReactElement {
  const { href } = props;

  // Same-page anchor: render plain, no new-tab behavior.
  if (href?.startsWith("#")) {
    const { children, ...rest } = props;
    return <a {...omitNode(rest)}>{children}</a>;
  }

  const { title, children, target, rel, href: _href, ...rest } = props;
  return (
    <a
      href={href ? transformUri(href) : undefined}
      title={title}
      target={target || "_blank"}
      rel={rel || "noopener noreferrer"}
      {...omitNode(rest)}
    >
      {children}
    </a>
  );
}
