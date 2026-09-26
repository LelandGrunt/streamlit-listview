import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { Markdown } from "./Markdown";

describe("Markdown inline rendering (both tiers)", () => {
  for (const tier of ["label", "help"] as const) {
    it(`renders bold/italic/strikethrough/inline-code in the ${tier} tier`, () => {
      const { container } = render(
        <Markdown tier={tier} source="**b** _i_ ~~s~~ `c`" />,
      );
      expect(container.querySelector("strong")?.textContent).toBe("b");
      expect(container.querySelector("em")?.textContent).toBe("i");
      expect(container.querySelector("del")?.textContent).toBe("s");
      expect(container.querySelector("code")?.textContent).toBe("c");
    });

    it(`renders a link with target=_blank rel=noopener in the ${tier} tier`, () => {
      render(<Markdown tier={tier} source="[site](https://example.com)" />);
      const a = screen.getByRole("link", {
        name: "site",
      }) as HTMLAnchorElement;
      expect(a).toHaveAttribute("href", "https://example.com");
      expect(a).toHaveAttribute("target", "_blank");
      expect(a).toHaveAttribute("rel", "noopener noreferrer");
    });

    it(`sanitizes a javascript: href to # in the ${tier} tier`, () => {
      render(<Markdown tier={tier} source="[x](javascript:alert(1))" />);
      const a = screen.getByRole("link", { name: "x" }) as HTMLAnchorElement;
      // urlTransform={transformUri} runs BEFORE the `a` override, so the
      // dangerous scheme is normalized to "#" (not stripped to an empty href).
      expect(a).toHaveAttribute("href", "#");
    });

    it(`renders an image with src + alt in the ${tier} tier`, () => {
      const { container } = render(
        <Markdown tier={tier} source="![alt text](https://example.com/p.png)" />,
      );
      const img = container.querySelector("img") as HTMLImageElement | null;
      expect(img).not.toBeNull();
      expect(img).toHaveAttribute("src", "https://example.com/p.png");
      expect(img).toHaveAttribute("alt", "alt text");
    });
  }
});

describe("Markdown wrapper", () => {
  it("wraps output in a .listview-markdown element (label + help)", () => {
    const label = render(<Markdown tier="label" source="hi" />);
    expect(label.container.querySelector(".listview-markdown")).not.toBeNull();
    const help = render(<Markdown tier="help" source="hi" />);
    expect(help.container.querySelector(".listview-markdown")).not.toBeNull();
  });
});

describe("Markdown label tier suppresses block elements", () => {
  it("strips and unwraps a heading to its inline text", () => {
    const { container } = render(<Markdown tier="label" source="# Heading" />);
    expect(container.querySelector("h1")).toBeNull();
    expect(container.textContent).toContain("Heading");
  });

  it("strips lists / tables / blockquotes / hr in the label tier", () => {
    const { container } = render(
      <Markdown
        tier="label"
        source={"- a\n- b\n\n> quote\n\n---\n\n| h |\n| - |\n| c |"}
      />,
    );
    expect(container.querySelector("ul")).toBeNull();
    expect(container.querySelector("li")).toBeNull();
    expect(container.querySelector("blockquote")).toBeNull();
    expect(container.querySelector("hr")).toBeNull();
    expect(container.querySelector("table")).toBeNull();
  });

  it("renders a leading '# ', '- ', '> ' LITERALLY in the label tier", () => {
    const heading = render(<Markdown tier="label" source="# Not a heading" />);
    expect(heading.container.textContent).toContain("# Not a heading");

    const list = render(<Markdown tier="label" source="- not a bullet" />);
    expect(list.container.textContent).toContain("- not a bullet");

    const quote = render(<Markdown tier="label" source="> not a quote" />);
    expect(quote.container.textContent).toContain("> not a quote");
  });
});

describe("Markdown help tier renders block elements", () => {
  it("renders headings, lists, tables, blockquotes and hr", () => {
    const { container } = render(
      <Markdown
        tier="help"
        source={"# Title\n\n- a\n- b\n\n> quote\n\n---\n\n| h |\n| - |\n| c |"}
      />,
    );
    expect(container.querySelector("h1")?.textContent).toContain("Title");
    expect(container.querySelectorAll("li").length).toBe(2);
    expect(container.querySelector("blockquote")).not.toBeNull();
    expect(container.querySelector("hr")).not.toBeNull();
    expect(container.querySelector("table")).not.toBeNull();
  });
});

describe("Markdown colored / badge / small / shimmer directives", () => {
  it("renders :red[x] as a colored-text span", () => {
    const { container } = render(<Markdown tier="help" source=":red[hi]" />);
    const span = container.querySelector(".listview-md-color");
    expect(span).not.toBeNull();
    expect(span?.classList.contains("listview-md-color--red")).toBe(true);
    expect(span?.textContent).toBe("hi");
  });

  it("renders :blue-badge[x] as a badge span", () => {
    const { container } = render(
      <Markdown tier="help" source=":blue-badge[x]" />,
    );
    const span = container.querySelector(".listview-md-badge");
    expect(span).not.toBeNull();
    expect(span?.classList.contains("listview-md-badge--blue")).toBe(true);
    expect(span?.textContent).toBe("x");
  });

  it("renders :small[x] as a small span", () => {
    const { container } = render(<Markdown tier="help" source=":small[x]" />);
    const span = container.querySelector(".listview-md-small");
    expect(span).not.toBeNull();
    expect(span?.textContent).toBe("x");
  });

  it("renders :shimmer[x] as a shimmer span", () => {
    const { container } = render(<Markdown tier="help" source=":shimmer[x]" />);
    const span = container.querySelector(".listview-md-shimmer");
    expect(span).not.toBeNull();
    expect(span?.textContent).toBe("x");
  });
});

describe("Markdown material icons (preprocess + plugin integration)", () => {
  it("renders :material/check: as a material-icon span carrying the icon name", () => {
    const { container } = render(
      <Markdown tier="help" source=":material/check:" />,
    );
    // materialIconPreprocess neutralises :material/check: to a colon-free
    // sentinel BEFORE parsing, so createRemarkMaterialIcons matches and emits
    // the span.
    const icon = container.querySelector('span[role="img"]');
    expect(icon).not.toBeNull();
    expect(icon?.textContent).toBe("check");
  });

  it("renders material icons in the label tier too", () => {
    const { container } = render(
      <Markdown tier="label" source=":material/check:" />,
    );
    const icon = container.querySelector('span[role="img"]');
    expect(icon).not.toBeNull();
    expect(icon?.textContent).toBe("check");
  });
});

describe("Markdown icon/logo adjacency (token glued to a following word)", () => {
  it("renders :material/<name>: when immediately followed by a word", () => {
    const { container } = render(
      <Markdown tier="label" source=":material/check:Done" />,
    );
    const icon = container.querySelector('span[role="img"]');
    expect(icon).not.toBeNull();
    expect(icon?.textContent).toBe("check");
    // the literal token (with the corrupting / -> _ rewrite) must not leak
    expect(container.textContent).not.toContain(":material");
    expect(container.textContent).toContain("Done");
  });

  it("renders :material/<name>: when immediately followed by a digit", () => {
    const { container } = render(
      <Markdown tier="label" source=":material/star:5 stars" />,
    );
    expect(container.querySelector('span[role="img"]')).not.toBeNull();
    expect(container.textContent).not.toContain(":material");
    expect(container.textContent).toContain("5 stars");
  });

  it("renders a hyphenated material icon name", () => {
    const { container } = render(
      <Markdown tier="label" source=":material/foo-bar:" />,
    );
    const icon = container.querySelector('span[role="img"]');
    expect(icon).not.toBeNull();
    expect(icon?.textContent).toBe("foo-bar");
  });

  it("renders an icon token inside inline code as the literal source (no sentinel/icon leak)", () => {
    // findAndReplace does not descend into code nodes, so the preprocess sentinel
    // must be restored to the readable source the user typed — never leak a
    // Private-Use control char into the DOM.
    const { container } = render(
      <Markdown tier="help" source={"`:material/check:`"} />,
    );
    expect(container.querySelector("code")?.textContent).toBe(":material/check:");
    expect(container.querySelector('span[role="img"]')).toBeNull();
  });

  it("renders :streamlit: inside inline code as the literal source", () => {
    const { container } = render(
      <Markdown tier="help" source={"`:streamlit:`"} />,
    );
    expect(container.querySelector("code")?.textContent).toBe(":streamlit:");
    expect(container.querySelector("img")).toBeNull();
  });

  it("renders :streamlit: as a logo image, isolated and glued to a word", () => {
    const isolated = render(<Markdown tier="label" source=":streamlit:" />);
    expect(
      isolated.container.querySelector('img[alt="Streamlit logo"]'),
    ).not.toBeNull();

    const glued = render(<Markdown tier="label" source=":streamlit:app" />);
    expect(
      glued.container.querySelector('img[alt="Streamlit logo"]'),
    ).not.toBeNull();
    expect(glued.container.textContent).toContain("app");
    expect(glued.container.textContent).not.toContain(":streamlit");
  });
});

describe("Markdown math (KaTeX intentionally dropped for bundle size)", () => {
  it("renders inline math as literal text, never a .katex element", () => {
    const { container } = render(
      <Markdown source="energy $E=mc^2$" tier="help" />,
    );
    expect(container.querySelector(".katex")).toBeNull();
    expect(container.textContent).toContain("$E=mc^2$");
  });

  it("renders display math as literal text, never a .katex element", () => {
    const { container } = render(<Markdown source={"$$x$$"} tier="help" />);
    expect(container.querySelector(".katex")).toBeNull();
    expect(container.textContent).toContain("$$x$$");
  });
});

describe("Markdown emoji (remark-emoji, conditional)", () => {
  it("converts a :shortcode: to its emoji glyph", () => {
    const { container } = render(<Markdown source="party :tada:" tier="help" />);
    expect(container.textContent).toContain("\u{1F389}"); // 🎉
    expect(container.textContent).not.toContain(":tada:");
  });

  it("leaves a non-shortcode colon sequence untouched (emoji plugin excluded)", () => {
    const { container } = render(<Markdown source="ratio 3:4 wins" tier="help" />);
    expect(container.textContent).toContain("3:4");
  });
});

describe("Markdown unknown directive fallback", () => {
  it("renders an unknown :foo[x] as literal text, not a span", () => {
    const { container } = render(<Markdown tier="help" source=":foo[x]" />);
    expect(container.textContent).toContain(":foo");
    expect(container.querySelector(".listview-md-color")).toBeNull();
    expect(container.querySelector(".listview-md-badge")).toBeNull();
  });

  it("renders an unsupported LEAF directive verbatim, never a <div> in the label tier", () => {
    // ::badge[Hello] used to reach mdast-util-to-hast's unknown-node fallback and
    // emit a block <div> inside the inline-only label <span>.
    const { container } = render(
      <Markdown tier="label" source="::badge[Hello]" />,
    );
    expect(container.querySelector("div")).toBeNull();
    expect(container.textContent).toBe("::badge[Hello]");
  });

  it("renders an unsupported CONTAINER directive verbatim, never a <div>", () => {
    const { container } = render(
      <Markdown tier="label" source={":::note\ncontent\n:::"} />,
    );
    expect(container.querySelector("div")).toBeNull();
    expect(container.textContent).toContain(":::note");
    expect(container.textContent).toContain("content");
  });

  it("keeps the text of a childless palette directive", () => {
    const { container } = render(<Markdown tier="label" source="Ampel :red" />);
    expect(container.querySelector(".listview-md-color")).toBeNull();
    expect(container.textContent).toBe("Ampel :red");
  });
});

describe("Markdown data: URL handling (image source vs anchor href)", () => {
  it("keeps a data:image/ source on an inline image", () => {
    const png = "data:image/png;base64,iVBORw0KGgo=";
    const { container } = render(
      <Markdown tier="help" source={`![i](${png})`} />,
    );
    expect(container.querySelector("img")).toHaveAttribute("src", png);
  });

  it("neutralizes a data:image/svg+xml ANCHOR href to #", () => {
    // An SVG document reached through a[href] is a script context, unlike the
    // same URL loaded by <img> — so the image allowance must not cover hrefs.
    const { container } = render(
      <Markdown
        tier="help"
        source="[click](data:image/svg+xml,%3Csvg%20onload%3Dalert(1)%3E)"
      />,
    );
    expect(container.querySelector("a")).toHaveAttribute("href", "#");
  });
});
