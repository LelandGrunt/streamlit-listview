import { describe, it, expect } from "vitest";
import { foldForMatch, plainTextLabel } from "./text";

describe("foldForMatch", () => {
  it("lowercases case-insensitively", () => {
    expect(foldForMatch("Apple")).toBe("apple");
    expect(foldForMatch("APPLE")).toBe(foldForMatch("apple"));
  });

  it("folds ß to ss, like Python's casefold (used by the sort)", () => {
    expect(foldForMatch("Straße")).toBe("strasse");
    expect(foldForMatch("STRASSE")).toBe(foldForMatch("Straße"));
  });

  it("drops leading/trailing whitespace but keeps internal whitespace", () => {
    // A typed " apple " means the row "apple"; "a  b" is still not "a b", so a
    // search and an accept_new_options add treat the two the same way.
    expect(foldForMatch("  Apple ")).toBe("apple");
    expect(foldForMatch("a  b")).toBe("a  b");
  });

  it("uses a locale-INDEPENDENT lowercase (the Turkish dotless-i trap)", () => {
    // toLocaleLowerCase in a tr locale folds "I" to "ı", which would break plain
    // ASCII matches; the fold must agree with Python's casefold everywhere.
    expect(foldForMatch("FILE")).toBe("file");
  });
});

describe("plainTextLabel", () => {
  it("strips emphasis, code and strikethrough markers", () => {
    expect(plainTextLabel("**Pick** a `fruit` ~~now~~")).toBe(
      "Pick a fruit now",
    );
  });

  it("unwraps colour/badge directives and their attribute block", () => {
    expect(plainTextLabel(":red[fruit]")).toBe("fruit");
    expect(plainTextLabel(":grey-badge[new]")).toBe("new");
    expect(plainTextLabel(":violet-background[hot]")).toBe("hot");
    expect(plainTextLabel(":color[Fruit]{foreground=#ff0000}")).toBe("Fruit");
  });

  it("leaves an unsupported directive literal, as the renderer does", () => {
    // :rainbow / :primary have no token in listview.css, so the markdown stack
    // renders them as literal text — the accessible name must say the same thing
    // the user sees rather than unwrapping to "Hi".
    expect(plainTextLabel(":rainbow[Hi]")).toBe(":rainbow[Hi]");
    expect(plainTextLabel(":primary[Hi]")).toBe(":primary[Hi]");
  });

  it("claims directives case-sensitively, as the renderer does", () => {
    // canonicalColor matches its lowercase palette exactly, so :RED[Hot] renders
    // as the literal text ":RED[Hot]" — announcing "Hot" would name formatting
    // the user cannot see.
    expect(plainTextLabel(":RED[Hot]")).toBe(":RED[Hot]");
  });

  it("reduces a claimed directive with EMPTY brackets to :name, as rendered", () => {
    // :red[] parses identically to a bare :red, so the renderer shows ":red";
    // deleting the whole token announced nothing where the user sees text.
    expect(plainTextLabel(":red[] Warning")).toBe(":red Warning");
    expect(plainTextLabel(":red[]{foreground=#f00} Warning")).toBe(
      ":red Warning",
    );
  });

  it("drops material icons and the :streamlit: logo, case-sensitively", () => {
    // materialIconPreprocess rewrites both tokens case-sensitively, so the
    // uppercase spellings render as literal text and must stay in the name.
    expect(plainTextLabel("Pick :material/check: one")).toBe("Pick one");
    expect(plainTextLabel("Made with :streamlit:")).toBe("Made with");
    expect(plainTextLabel(":MATERIAL/check:")).toBe(":MATERIAL/check:");
  });

  it("replaces a known :shortcode: with its emoji character, as rendered", () => {
    // remark-emoji swaps a KNOWN shortcode for the emoji glyph; the accessible
    // name carries the same character the user sees.
    expect(plainTextLabel("party :tada:")).toBe("party \u{1F389}");
    expect(plainTextLabel("Pick :material/check: one :smile:")).toBe(
      "Pick one \u{1F604}",
    );
  });

  it("leaves unknown colon tokens literal, as the renderer does", () => {
    // remark-emoji leaves a token it cannot resolve untouched — a blanket strip
    // announced "Standup 1245" for a label reading "Standup 12:30:45".
    expect(plainTextLabel("Standup 12:30:45")).toBe("Standup 12:30:45");
    expect(plainTextLabel(":notashortcode: stays")).toBe(
      ":notashortcode: stays",
    );
  });

  it("reduces links and images to their text", () => {
    expect(plainTextLabel("see [docs](https://example.com)")).toBe("see docs");
    expect(plainTextLabel("![alt](a.png) here")).toBe("alt here");
  });

  it("keeps intraword underscores and strips emphasis ones", () => {
    expect(plainTextLabel("Edit _the_ user_id field")).toBe(
      "Edit the user_id field",
    );
  });

  it("collapses runs of whitespace and trims", () => {
    expect(plainTextLabel("  a \n  b  ")).toBe("a b");
  });

  it("keeps the content of an inline code span as rendered", () => {
    // A code span renders its content verbatim: no emphasis, icon, emoji or
    // directive inside it. Stripping its markers left "`*`" with no name at
    // all (axe-core: aria-input-field-name) and announced "`__init__`" as
    // "init".
    expect(plainTextLabel("`*`")).toBe("*");
    expect(plainTextLabel("`__init__`")).toBe("__init__");
    expect(plainTextLabel("Columns (`*` = required)")).toBe(
      "Columns (* = required)",
    );
    expect(plainTextLabel("`:material/check:` and `:streamlit:`")).toBe(
      ":material/check: and :streamlit:",
    );
    expect(plainTextLabel("`:tada:` and `:red[x]`")).toBe(":tada: and :red[x]");
    expect(plainTextLabel("`[docs](https://example.com)`")).toBe(
      "[docs](https://example.com)",
    );
  });

  it("matches code span delimiters as CommonMark does", () => {
    // A span closes at the next backtick run of the SAME length, a run
    // without one renders literally, and one space is stripped from each end
    // of a span that has non-space content.
    expect(plainTextLabel("``a`b``")).toBe("a`b");
    expect(plainTextLabel("`` `x` ``")).toBe("`x`");
    expect(plainTextLabel("it`s")).toBe("it`s");
    expect(plainTextLabel("``a`")).toBe("``a`");
  });

  it("reduces a code span inside a link or directive to its content", () => {
    expect(plainTextLabel("see [`docs`](https://example.com)")).toBe(
      "see docs",
    );
    expect(plainTextLabel(":red[`hot`] item")).toBe("hot item");
  });

  it("keeps backslash-escaped punctuation, without the backslash", () => {
    expect(plainTextLabel(String.raw`5 \* 3`)).toBe("5 * 3");
    expect(plainTextLabel(String.raw`\_id\_`)).toBe("_id_");
    expect(plainTextLabel(String.raw`\[a](b)`)).toBe("[a](b)");
    expect(plainTextLabel(String.raw`\`x\``)).toBe("`x`");
    // A backslash before anything else stays, as it renders.
    expect(plainTextLabel(String.raw`C:\temp`)).toBe(String.raw`C:\temp`);
  });

  it("keeps a marker run with whitespace on both sides, which cannot emphasize", () => {
    expect(plainTextLabel("a ~ b")).toBe("a ~ b");
    expect(plainTextLabel("2 * 3")).toBe("2 * 3");
    expect(plainTextLabel("x _ y")).toBe("x _ y");
    expect(plainTextLabel("* item")).toBe("* item");
  });
});
