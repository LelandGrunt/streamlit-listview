import { describe, it, expect } from "vitest";
import { containsEmojiShortcodes } from "./detect";

describe("containsEmojiShortcodes", () => {
  it("detects a :shortcode:", () => {
    expect(containsEmojiShortcodes("party time :tada:")).toBe(true);
  });

  it("detects shortcodes with + and - and _", () => {
    expect(containsEmojiShortcodes(":+1:")).toBe(true);
    expect(containsEmojiShortcodes(":heavy_check_mark:")).toBe(true);
  });

  it("ignores the Streamlit :material/...: and :streamlit: directives", () => {
    expect(containsEmojiShortcodes(":material/home:")).toBe(false);
    expect(containsEmojiShortcodes(":streamlit:")).toBe(false);
  });

  it("returns false for plain colon-free text", () => {
    expect(containsEmojiShortcodes("no shortcodes here")).toBe(false);
  });
});
