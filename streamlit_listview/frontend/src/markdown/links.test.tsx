import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { LinkWithTargetBlank, transformUri } from "./links";

describe("transformUri", () => {
  it("passes through a normal http(s) href unchanged", () => {
    expect(transformUri("https://example.com/x?a=1")).toBe(
      "https://example.com/x?a=1",
    );
  });

  it("passes through a relative href unchanged", () => {
    expect(transformUri("/docs/page")).toBe("/docs/page");
  });

  it("neutralizes a javascript: href to #", () => {
    expect(transformUri("javascript:alert(1)")).toBe("#");
  });

  it("neutralizes a vbscript: href to #", () => {
    expect(transformUri("vbscript:msgbox(1)")).toBe("#");
  });

  it("neutralizes an uppercase scheme to #", () => {
    expect(transformUri("JaVaScRiPt:alert(1)")).toBe("#");
  });

  it("neutralizes a scheme obfuscated with C0 control chars", () => {
    // A NUL (U+0000) and a TAB (U+0009) injected mid-scheme are stripped by the
    // C0-control regex, collapsing the scheme word back to "javascript:".
    // Written with explicit \u0000 / \t escapes so the fixture survives copy/paste.
    expect(transformUri("java\u0000scr\tipt:alert(1)")).toBe("#");
  });

  it("does NOT strip an embedded space (U+0020 is not a C0 control char)", () => {
    // A literal space is NOT in the C0 range, so the scheme is not collapsed and
    // the href is returned unchanged (matches Streamlit's sanitizer behavior).
    expect(transformUri("java script:alert(1)")).toBe("java script:alert(1)");
  });

  it("neutralizes a file: href to #", () => {
    expect(transformUri("file:///etc/passwd")).toBe("#");
  });

  it("neutralizes a blob: href to #", () => {
    expect(transformUri("blob:https://example.com/9b2c")).toBe("#");
  });

  it("neutralizes a non-image data: href to #", () => {
    expect(transformUri("data:text/html,<script>alert(1)</script>")).toBe("#");
  });

  it("passes through a data:image/ IMAGE SOURCE unchanged (inline images / the logo)", () => {
    // react-markdown calls the transform as urlTransform(value, key, node); the
    // data:image/ allowance applies to the `src` attribute only.
    const png = "data:image/png;base64,iVBORw0KGgo=";
    expect(transformUri(png, "src")).toBe(png);
  });

  it("neutralizes a non-image data: IMAGE SOURCE to # as well", () => {
    // The allowance is data:image/ only; any other media type is blocked even on
    // an image source.
    expect(
      transformUri("data:text/html,<script>alert(1)</script>", "src"),
    ).toBe("#");
  });

  it("neutralizes a data:image/ ANCHOR href to # (SVG in a[href] is a script context)", () => {
    expect(
      transformUri("data:image/svg+xml,%3Csvg%20onload%3Dalert(1)%3E", "href"),
    ).toBe("#");
  });

  it("neutralizes a data:image/ URL when no attribute key is supplied", () => {
    // The key-less call comes from LinkWithTargetBlank (an anchor), so an absent
    // key must deny rather than fall back to the image allowance.
    expect(transformUri("data:image/png;base64,iVBORw0KGgo=")).toBe("#");
  });
});

describe("LinkWithTargetBlank", () => {
  it("renders an external link with target=_blank rel=noopener noreferrer", () => {
    render(
      <LinkWithTargetBlank href="https://example.com">
        site
      </LinkWithTargetBlank>,
    );
    const a = screen.getByRole("link", { name: "site" }) as HTMLAnchorElement;
    expect(a).toHaveAttribute("href", "https://example.com");
    expect(a).toHaveAttribute("target", "_blank");
    expect(a).toHaveAttribute("rel", "noopener noreferrer");
  });

  it("renders a same-page #anchor without target/rel", () => {
    render(
      <LinkWithTargetBlank href="#section">jump</LinkWithTargetBlank>,
    );
    const a = screen.getByRole("link", { name: "jump" }) as HTMLAnchorElement;
    expect(a).toHaveAttribute("href", "#section");
    expect(a).not.toHaveAttribute("target");
    expect(a).not.toHaveAttribute("rel");
  });

  it("preserves an explicitly supplied target/rel", () => {
    render(
      <LinkWithTargetBlank href="https://example.com" target="_self" rel="nofollow">
        x
      </LinkWithTargetBlank>,
    );
    const a = screen.getByRole("link", { name: "x" }) as HTMLAnchorElement;
    expect(a).toHaveAttribute("target", "_self");
    expect(a).toHaveAttribute("rel", "nofollow");
  });

  it("omits href for an href-less anchor (no href=undefined attribute)", () => {
    render(<LinkWithTargetBlank>bare</LinkWithTargetBlank>);
    const a = screen.getByText("bare") as HTMLAnchorElement;
    expect(a.tagName).toBe("A");
    expect(a).not.toHaveAttribute("href");
    expect(a).toHaveAttribute("target", "_blank");
  });

  it("does not forward the react-markdown `node` prop to the DOM", () => {
    render(
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      <LinkWithTargetBlank href="https://example.com" node={{} as any}>
        n
      </LinkWithTargetBlank>,
    );
    const a = screen.getByRole("link", { name: "n" }) as HTMLAnchorElement;
    expect(a).not.toHaveAttribute("node");
  });
});
