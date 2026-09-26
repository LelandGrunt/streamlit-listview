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
});
