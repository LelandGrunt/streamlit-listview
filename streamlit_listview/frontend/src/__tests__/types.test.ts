import { describe, it, expect, expectTypeOf } from "vitest";
import type {
  Id,
  ListviewItem,
  SelectionMode,
  LabelVisibility,
  ListviewData,
  ListviewState,
} from "../types";

describe("types wire format", () => {
  it("Id is the one exported str-or-int union every id field is typed with", () => {
    // Mirrors Python's _validate_id (exactly str or int). Declared once and
    // imported, so a change to what an id may be is a single edit the compiler
    // then carries to every field — a private per-file alias would keep
    // typechecking against its own stale copy.
    expectTypeOf<Id>().toEqualTypeOf<string | number>();
    expectTypeOf<ListviewItem["id"]>().toEqualTypeOf<Id>();
    expectTypeOf<ListviewData["default_ids"]>().toEqualTypeOf<Id[]>();
    expectTypeOf<ListviewData["state_selection"]>().toEqualTypeOf<Id[] | null>();
    expectTypeOf<ListviewState["selection"]>().toEqualTypeOf<Id[]>();
  });

  it("ListviewItem carries id+label, optional group/disabled", () => {
    const item: ListviewItem = { id: "a", label: "Apple" };
    expect(item.id).toBe("a");
    expect(item.label).toBe("Apple");
    expectTypeOf<ListviewItem["id"]>().toEqualTypeOf<string | number>();
    expectTypeOf<ListviewItem["group"]>().toEqualTypeOf<string | undefined>();
    expectTypeOf<ListviewItem["disabled"]>().toEqualTypeOf<boolean | undefined>();
  });

  it("SelectionMode / LabelVisibility are the documented literals", () => {
    expectTypeOf<SelectionMode>().toEqualTypeOf<"single" | "multi">();
    expectTypeOf<LabelVisibility>().toEqualTypeOf<
      "visible" | "hidden" | "collapsed"
    >();
  });

  it("ListviewData uses the exact snake_case keys from the wire format", () => {
    const data: ListviewData = {
      label: "Fruit",
      help: null,
      items: [{ id: "a", label: "Apple" }],
      selection_mode: "single",
      default_ids: [],
      state_selection: null,
      enable_search: false,
      pin_search: false,
      search_placeholder: "Search",
      collapsible_groups: false,
      collapsed_groups: null,
      accept_new_options: false,
      max_selections: null,
      placeholder: null,
      height: 300,
      item_height: null,
      content_font_size: null,
      width: "stretch",
      show_grid_lines: false,
      select_all: false,
      disabled: false,
      label_visibility: "visible",
    };
    // Object.keys order is insertion order; assert the full key set.
    expect(Object.keys(data).sort()).toEqual(
      [
        "accept_new_options",
        "collapsed_groups",
        "collapsible_groups",
        "content_font_size",
        "default_ids",
        "disabled",
        "enable_search",
        "height",
        "help",
        "item_height",
        "items",
        "label",
        "label_visibility",
        "max_selections",
        "pin_search",
        "placeholder",
        "search_placeholder",
        "select_all",
        "selection_mode",
        "show_grid_lines",
        "state_selection",
        "width",
      ].sort(),
    );
  });

  it("ListviewState carries selection as an id list", () => {
    const state: ListviewState = { selection: ["a", 1] };
    expect(state.selection).toEqual(["a", 1]);
    expectTypeOf<ListviewState["selection"]>().toEqualTypeOf<
      (string | number)[]
    >();
  });
});
