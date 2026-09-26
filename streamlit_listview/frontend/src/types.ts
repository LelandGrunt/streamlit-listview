/**
 * An option id as it crosses the Python/JSON boundary: exactly a string or a
 * number, because Python's `_validate_id` admits exactly `str` or `int` (bool,
 * float, None and everything else are rejected there). ONE declaration, imported
 * everywhere an id is typed — a private `type Id = string | number` per file
 * still typechecks after a change to this union, so the compiler would not find
 * the copies left behind.
 */
export type Id = string | number;

export interface ListviewItem {
  id: Id;
  label: string; // display text; format_func already applied server-side
  group?: string;
  disabled?: boolean;
}

export type SelectionMode = "single" | "multi";
export type LabelVisibility = "visible" | "hidden" | "collapsed";

export interface ListviewData {
  label: string;
  help: string | null;
  items: ListviewItem[];
  selection_mode: SelectionMode;
  default_ids: Id[]; // initial-render selection display (A) + jump-to-default scroll (C); source of truth is the V2 default= state, never written back
  state_selection: Id[] | null; // the persisted st.session_state selection (keyed instances; null when absent) — re-seeds a remount that kept the Python-side widget state, e.g. a sidebar/main move
  enable_search: boolean;
  pin_search: boolean;
  search_placeholder: string;
  collapsible_groups: boolean;
  collapsed_groups: string[] | "all" | null;
  accept_new_options: boolean;
  max_selections: number | null;
  placeholder: string | null;
  height: number;
  item_height: number | null;
  content_font_size: number | null;
  width: "stretch" | number;
  show_grid_lines: boolean;
  select_all: boolean;
  disabled: boolean;
  label_visibility: LabelVisibility;
}

export interface ListviewState {
  selection: Id[]; // selected ids, in selection order
  [key: string]: unknown; // satisfies FrontendState = Record<string, unknown>
}
