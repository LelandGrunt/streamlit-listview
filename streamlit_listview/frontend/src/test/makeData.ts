import type { ListviewData } from "../types";

/**
 * The ONE test-data factory for a complete `ListviewData` payload: every field
 * at its test default, overrides last. Previously copied verbatim into three
 * test files, whose payload defaults had nothing keeping them aligned.
 *
 * Deliberately NOT used by src/__tests__/types.test.ts — its inline literal
 * asserts the wire-format key set, which a spread from here would satisfy
 * vacuously.
 */
export function makeData(overrides: Partial<ListviewData> = {}): ListviewData {
  return {
    label: "Pick one",
    help: null,
    items: [
      { id: "a", label: "Apple", group: "Fruit" },
      { id: "b", label: "Banana", group: "Fruit" },
      { id: "c", label: "Carrot", group: "Veg" },
      { id: "d", label: "Disabled", group: "Veg", disabled: true },
    ],
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
    show_grid_lines: true,
    select_all: false,
    disabled: false,
    label_visibility: "visible",
    ...overrides,
  };
}
