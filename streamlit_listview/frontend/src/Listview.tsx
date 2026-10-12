import { useCallback, useId, useMemo, useRef, useState } from "react";
import type { CSSProperties, FC, MouseEvent } from "react";
import type { FrontendRendererArgs } from "@streamlit/component-v2-lib";
import type { Id, ListviewData, ListviewItem, ListviewState } from "./types";
import { WidgetLabel } from "./components/WidgetLabel";
import { SearchField } from "./components/SearchField";
import { NewOptionInput } from "./components/NewOptionInput";
import { ListviewHeader } from "./components/ListviewHeader";
import { ListviewBody } from "./components/ListviewBody";
import { ListBlocks } from "./components/ListBlocks";
import { useSelection } from "./hooks/useSelection";
import { useKeyboardNav } from "./hooks/useKeyboardNav";
import { useFilter } from "./hooks/useFilter";
import { useScrollToItem } from "./hooks/useScrollToItem";
import { useColorScheme } from "./hooks/useColorScheme";
import { useRowHeight } from "./hooks/useRowHeight";
import { useResetChunkHeights } from "./hooks/useResetChunkHeights";
import { useNewOptionRows } from "./hooks/useNewOptionRows";
import { useAddNewOption } from "./hooks/useAddNewOption";
import { useGroupCollapse } from "./hooks/useGroupCollapse";
import { useRenderBlocks } from "./hooks/useRenderBlocks";
import { useSelectAll } from "./hooks/useSelectAll";
import { useScrollToGroup, useScrollToId } from "./hooks/useScrollToId";
import type { GroupKey } from "./hooks/useCollapse";
import { reuseUnchangedItems } from "./utils/items";

export interface ListviewProps {
  data: ListviewData;
  setStateValue: FrontendRendererArgs<ListviewState>["setStateValue"];
  /**
   * Whether this instance is mounted in Streamlit's sidebar, which swaps the
   * two background tokens the sheet paints its surfaces from (see
   * `utils/container.ts`). Resolved in `index.tsx` from the renderer's
   * `parentElement` rather than by a hook here, so the flag is on the root
   * before first paint: an effect-based read would land a frame late and flash
   * the main-body colors on every mount.
   */
  inSidebar?: boolean;
}

/** The root's class names: the base class plus the disabled and no-grid modifiers (listview.css). */
function rootClassNameFor(
  widgetDisabled: boolean,
  showGridLines: boolean,
): string {
  return (
    "listview" +
    (widgetDisabled ? " listview--disabled" : "") +
    (showGridLines ? "" : " listview--no-grid")
  );
}

/**
 * The container component: it composes the hooks and the presentational
 * components. The rows the list shows come from `useNewOptionRows`
 * (`allItems`), `useFilter`, `useGroupCollapse` and `useRenderBlocks`; the
 * selection lives in `useSelection`.
 */
export const Listview: FC<ListviewProps> = ({
  data,
  setStateValue,
  inSidebar,
}) => {
  const widgetDisabled = data.disabled;

  const [query, setQuery] = useState("");
  const searchInputRef = useRef<HTMLInputElement>(null);
  const bodyRef = useRef<HTMLDivElement>(null);
  const listboxRef = useRef<HTMLDivElement>(null);
  const rootRef = useRef<HTMLDivElement>(null);
  // "light" | "dark" from the active Streamlit theme (not the OS scheme), so
  // the help tooltip can match Streamlit's themed tooltip surface.
  const colorScheme = useColorScheme(rootRef);

  // The caller's options, with every item unchanged since the previous render
  // kept as the previous render's OBJECT — and the previous array itself when
  // nothing changed. Every rerun that changes this listview's payload ships the
  // options as freshly parsed JSON: a parameter change, a click on a keyed
  // listview, the first rerun after a keyed listview mounts. Reading
  // `data.items` directly made each such rerun recompute every memo below that
  // is keyed on the items and re-render every row: O(N) per rerun for a list
  // whose options never moved.
  // Read the options through `items` only, never `data.items`. A deliberate
  // render-body ref write, like the itemClickRef pattern below.
  const prevItemsRef = useRef<ListviewItem[]>(data.items);
  /* eslint-disable react/refs -- a deliberate render-body ref, see above */
  const items = reuseUnchangedItems(prevItemsRef.current, data.items);
  prevItemsRef.current = items;
  /* eslint-enable react/refs */

  // What a fresh mount seeds the selection from: the persisted Python-side
  // selection when this mount is a remount that kept the widget state (a keyed
  // instance moved between st.sidebar and the main body — the element id drops
  // the container), else the caller's `default`. Consumed only by mount-time
  // initializers, so a later change to either field never re-seeds (see
  // useSelection). `??`, not `||`: an empty persisted selection is a cleared
  // selection that must survive the move, not a fallback to `default`.
  const seedSelection = data.state_selection ?? data.default_ids;

  const selection = useSelection({
    items,
    selectionMode: data.selection_mode,
    maxSelections: data.max_selections,
    acceptNewOptions: data.accept_new_options,
    initialSelection: seedSelection,
    setStateValue,
  });

  // The accept_new_options rows, and every row the list renders.
  const { newOptionItems, allItems, rememberAdded } = useNewOptionRows({
    items,
    acceptNewOptions: data.accept_new_options,
    seedSelection,
    selection: selection.selection,
  });

  // The query the list filters by: the field's text while the field shows,
  // none while a rerun has turned search off. A keyed instance keeps `query`
  // across that rerun, and a filter whose field is gone showed a subset with
  // nothing on screen to say so or to clear it. The text stays, so the field
  // brings it back when search returns.
  const activeQuery = data.enable_search ? query : "";
  const { visibleItems, isFiltering } = useFilter({
    items: allItems,
    query: activeQuery,
  });

  const ungroupedLabel = data.ungrouped_label;
  const { isGrouped, asTree, collapse, expandBlock } = useGroupCollapse({
    items,
    ungroupedLabel,
    newOptionItems,
    collapsibleGroups: data.collapsible_groups,
    collapsedGroups: data.collapsed_groups,
  });

  const {
    renderBlocks,
    renderGroups,
    rowPosition,
    listSize,
    blockPlace,
    navNodes,
  } = useRenderBlocks({
    allItems,
    visibleItems,
    isFiltering,
    ungroupedLabel,
    isGrouped,
    asTree,
    collapse,
  });

  const selectAllToggle = useSelectAll({
    selectAll: data.select_all,
    widgetDisabled,
    allItems,
    renderGroups,
    selection,
  });

  const onSelect = useCallback(
    (id: Id) => {
      // Defense-in-depth: unreachable while disabled (the listbox drops its
      // keydown handler), so this guard never trips via the UI.
      /* v8 ignore next 3 */
      if (widgetDisabled) {
        return;
      }
      selection.toggle(id);
    },
    [widgetDisabled, selection],
  );

  const onEscape = useCallback(() => {
    // Defense-in-depth: unreachable while disabled (search input + listbox
    // keydown are both inert then), so this guard never trips via the UI.
    /* v8 ignore next 3 */
    if (widgetDisabled) {
      return;
    }
    // Escape targets the search BOX first whenever it holds any text — the same
    // `value.length > 0` that shows SearchField's × button — and only then the
    // selection. Not `isFiltering`: that folds (trims) the query, so a box
    // holding only spaces counted as "not filtering" and Escape skipped the
    // visibly non-empty box to wipe the selection instead — committing state
    // and firing on_change while the spaces (and the × button) stayed put.
    // The two mistakes are not symmetric: clearing text is free, clearing the
    // selection is a state write the user did not ask for. `useFilter` keeps
    // sole ownership of "a query is active" for filtering; this is "the box is
    // non-empty", which is the box's own definition. A box that is not shown
    // holds nothing: the hidden text filters nothing, so Escape skips it.
    if (activeQuery.length > 0) {
      setQuery("");
    } else {
      selection.clear();
    }
  }, [widgetDisabled, activeQuery, selection]);

  const onSlash = useCallback(() => {
    searchInputRef.current?.focus();
  }, []);

  // A list shorter than `height` leaves empty space below its last row, and that
  // space is .listview-body itself — not focusable — so a click there moved focus
  // nowhere and the frame never lit up, where st.text_area focuses on the same
  // click. Forward it to the listbox. Only a click on the body ITSELF: rows and
  // the in-flow search field are children that already focus their own target,
  // and taking it would pull the caret out of an input. ListviewBody attaches
  // it only while the widget is enabled.
  // preventScroll: the listbox is taller than the frame it scrolls in.
  const onBodyClick = useCallback((event: MouseEvent<HTMLDivElement>) => {
    if (event.target === event.currentTarget) {
      (listboxRef.current as HTMLDivElement).focus({ preventScroll: true });
    }
  }, []);

  // The first row's height, published on the listbox for the size estimate of
  // the render chunks the browser skips (see ROW_CHUNK_SIZE in
  // hooks/useRenderBlocks.ts). A layout effect, so it lands before the first
  // paint and before useScrollToItem's rAF measures where a default row lies.
  // scrollToId measures the first row again through the returned function
  // before it measures a row of its own.
  const remeasureRowHeight = useRowHeight(listboxRef);

  // DOM scroll for a row id, shared by jump-to-default, keyboard navigation
  // and the reveal of an added row; and for a header the keyboard lands on.
  const scrollToId = useScrollToId(bodyRef, remeasureRowHeight);
  const scrollToGroup = useScrollToGroup(bodyRef);

  // Keyboard focus moves only need the row brought just inside the frame:
  // "nearest" leaves an already-visible row exactly where it is, so arrowing
  // between visible rows never jogs the list under the user, while a step past
  // either edge scrolls by exactly one row.
  const scrollFocusIntoView = useCallback(
    (id: Id) => scrollToId(id, "nearest"),
    [scrollToId],
  );

  const nav = useKeyboardNav({
    nodes: navNodes,
    onSelect,
    onToggleGroup: collapse.toggle,
    onSlash: data.enable_search ? onSlash : undefined,
    onEscape,
    // Keyboard focus is virtual (aria-activedescendant), and browsers only
    // auto-scroll for real DOM focus — so the ring has to be scrolled into view
    // here, through the same helper the jump-to-default path uses.
    scrollToId: scrollFocusIntoView,
    scrollToGroup,
  });

  // Stable identity (empty deps) via a latest-values ref, so the memoized
  // ListItem rows can bail out when only a sibling row's selected/focused state
  // changed. selection.toggle and nav.setFocusToId are recreated every render
  // (they close over the current selection/focus), so depending on them
  // directly would give every row a new onSelect prop and defeat the memo.
  const itemClickRef = useRef({
    widgetDisabled,
    setFocusToId: nav.setFocusToId,
    toggle: selection.toggle,
  });
  // eslint-disable-next-line react/refs -- a deliberate render-body ref, see above
  itemClickRef.current = {
    widgetDisabled,
    setFocusToId: nav.setFocusToId,
    toggle: selection.toggle,
  };
  const onItemClick = useCallback((id: Id) => {
    const {
      widgetDisabled: disabled,
      setFocusToId,
      toggle,
    } = itemClickRef.current;
    // Defense-in-depth: ListItem already blocks clicks while disabled, so this
    // never fires then.
    /* v8 ignore next 3 */
    if (disabled) {
      return;
    }
    setFocusToId(id);
    toggle(id);
  }, []);

  // A click on a header opens or closes its group and, like a click on a row,
  // moves the keyboard focus there, so the arrows resume from the header.
  const onHeaderClick = (group: GroupKey) => {
    nav.setFocusToGroup(group);
    collapse.toggle(group);
  };

  const onAddNewOption = useAddNewOption({
    widgetDisabled,
    allItems,
    selection,
    maxSelections: data.max_selections,
    newOptionKind: data.new_option_kind,
    expandBlock,
    scrollToId,
    rememberAdded,
  });

  // After a commit that changed the blocks, a skipped chunk whose rows changed
  // forgets the height the browser remembered from its last render (see
  // useResetChunkHeights): otherwise a search after scrolling left every chunk
  // scrolled past at the height of the rows it no longer holds.
  useResetChunkHeights(listboxRef, renderBlocks);

  useScrollToItem({
    defaultIds: data.default_ids,
    items: allItems,
    ensureGroupExpanded: expandBlock,
    scrollToId,
  });

  const rootStyle = useMemo<CSSProperties>(() => {
    const style: Record<string, string> = {
      "--listview-height": `${data.height}px`,
      "--listview-width": data.width === "stretch" ? "100%" : `${data.width}px`,
    };
    if (data.item_height != null) {
      style["--listview-item-height"] = `${data.item_height}px`;
    }
    if (data.content_font_size != null) {
      style["--listview-content-font-size"] = `${data.content_font_size}px`;
    }
    return style as CSSProperties;
  }, [data.height, data.width, data.item_height, data.content_font_size]);

  // The listbox's accessible name (WCAG 4.1.2). Without it a screen reader
  // announced only "list box, N items": the visible label is deliberately
  // aria-hidden, and the help trigger names itself, not the widget (and is absent
  // when help is None or label_visibility is not "visible"). aria-labelledby
  // rather than a duplicated aria-label string, so the name is whatever the label
  // markdown actually renders; WidgetLabel owns the span it points at.
  const labelId = useId();

  // Placed by ListviewHeader (pin_search) or ListviewBody (in flow).
  const searchField = data.enable_search ? (
    <SearchField
      value={query}
      placeholder={data.search_placeholder}
      disabled={widgetDisabled}
      onChange={setQuery}
      onEscape={onEscape}
      inputRef={searchInputRef}
    />
  ) : null;

  return (
    <div
      className={rootClassNameFor(widgetDisabled, data.show_grid_lines)}
      data-testid="stListview"
      data-color-scheme={colorScheme}
      data-in-sidebar={inSidebar ? "true" : undefined}
      style={rootStyle}
      ref={rootRef}
    >
      <WidgetLabel
        label={data.label}
        help={data.help}
        labelVisibility={data.label_visibility}
        disabled={widgetDisabled}
        textId={labelId}
      />

      <ListviewHeader
        enableSearch={data.enable_search}
        pinSearch={data.pin_search}
        searchField={searchField}
        selectAll={data.select_all}
        toggle={selectAllToggle}
      />

      <ListviewBody
        bodyRef={bodyRef}
        listboxRef={listboxRef}
        widgetDisabled={widgetDisabled}
        onBodyClick={onBodyClick}
        enableSearch={data.enable_search}
        pinSearch={data.pin_search}
        searchField={searchField}
        labelId={labelId}
        selectionMode={data.selection_mode}
        asTree={asTree}
        focusedId={nav.focusedId}
        focusedGroup={nav.focusedGroup}
        onKeyDown={nav.onKeyDown}
      >
        <ListBlocks
          renderBlocks={renderBlocks}
          empty={allItems.length === 0}
          placeholder={data.placeholder}
          ungroupedLabel={ungroupedLabel}
          collapsibleGroups={data.collapsible_groups}
          asTree={asTree}
          rowPosition={rowPosition}
          listSize={listSize}
          blockPlace={blockPlace}
          isSelected={selection.isSelected}
          isMuted={selection.isMuted}
          widgetDisabled={widgetDisabled}
          focusedId={nav.focusedId}
          focusedGroup={nav.focusedGroup}
          onItemClick={onItemClick}
          onHeaderClick={onHeaderClick}
        />
      </ListviewBody>

      {/* The add field sits in a footer below the scroll frame, not at the end
          of it: there it read as the last row of the last group, and it
          scrolled out of view with the rows. */}
      {data.accept_new_options && (
        <div className="listview-footer">
          <NewOptionInput disabled={widgetDisabled} onAdd={onAddNewOption} />
        </div>
      )}
    </div>
  );
};

export default Listview;
