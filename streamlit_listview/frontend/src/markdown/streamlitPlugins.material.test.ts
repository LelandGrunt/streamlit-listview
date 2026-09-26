import { describe, it, expect } from "vitest";
import {
  createRemarkMaterialIcons,
  createRemarkStreamlitLogo,
  materialIconPreprocess,
} from "./streamlitPlugins";
import { findElement, renderHast as renderHastWith, textOf } from "../test/hast";

const renderHast = (src: string) =>
  renderHastWith(src, [
    createRemarkMaterialIcons(),
    createRemarkStreamlitLogo(),
  ]);

describe("materialIconPreprocess", () => {
  it("rewrites :material/<name>: to a colon-free token that renders as an icon", () => {
    // Output must carry no ':' form for remark-directive to fragment; it
    // round-trips to a material-icon span via createRemarkMaterialIcons.
    const out = materialIconPreprocess("a :material/check: b");
    expect(out).not.toContain(":material");
    const span = findElement(renderHast(out), "span");
    expect(span).toBeDefined();
    expect(textOf(span)).toBe("check");
  });
  it("leaves source without material icons unchanged", () => {
    expect(materialIconPreprocess("nothing here")).toBe("nothing here");
  });
});

describe("createRemarkMaterialIcons", () => {
  it("renders the material span with the icon name as ligature text", () => {
    const span = findElement(
      renderHast(materialIconPreprocess(":material/check:")),
      "span",
    );
    expect(span).toBeDefined();
    const style = String(span?.properties?.style ?? "");
    expect(style).toContain("Material Symbols Rounded");
    expect(style).toContain("font-feature-settings");
    expect(textOf(span)).toBe("check");
    expect(span?.properties?.role).toBe("img");
    // mdast-util-to-hast keeps `ariaLabel`; react-markdown renders it as aria-label.
    expect(span?.properties?.ariaLabel).toBe("check icon");
  });
});

describe("createRemarkStreamlitLogo", () => {
  it("replaces :streamlit: with an inline streamlit-logo image", () => {
    // The logo token is neutralised to a sentinel by materialIconPreprocess
    // before parsing, then findAndReplace'd into the image.
    const img = findElement(renderHast(materialIconPreprocess(":streamlit:")), "img");
    expect(img).toBeDefined();
    expect(img?.properties?.alt).toBe("Streamlit logo");
  });
});
