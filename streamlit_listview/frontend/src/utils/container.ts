/**
 * Which Streamlit container the component instance was mounted into.
 *
 * Only the sidebar is distinguished, and only because Streamlit's sidebar theme
 * SWAPS two color tokens: inside `[data-testid="stSidebar"]`,
 * `--st-background-color` and `--st-secondary-background-color` trade values
 * (light: #ffffff/#f0f2f6 become #f0f2f6/#ffffff; dark: #0e1117/#262730 become
 * #262730/#0e1117). Every other `--st-*` color is identical in both containers.
 * A V2 instance gets its custom properties from the theme context at its own
 * mount point, so a sidebar listview inherits the swapped pair automatically —
 * which rendered its rows on the group-header surface and vice versa. The sheet
 * un-swaps them for this container (see the `[data-in-sidebar="true"]` block in
 * listview.css), so the widget keeps matching st.selectbox, whose control fill
 * is `--st-secondary-background-color` in BOTH containers.
 */

/**
 * True iff this component instance is mounted inside Streamlit's sidebar.
 *
 * `parentElement` is the open `ShadowRoot` under `isolate_styles=True` (the
 * default) and a plain element otherwise, so the lookup starts by hopping to
 * the shadow host: `closest()` does NOT cross a shadow boundary, and without
 * the hop it answers null in the sidebar too — the widget would silently keep
 * its main-body colors rather than fail visibly.
 *
 * `[data-testid="stSidebar"]` is a Streamlit-internal test id rather than a
 * documented API. It is stable, and this repo's e2e suite already targets it;
 * were it renamed upstream the widget would fall back to the main-body colors,
 * which degrades rather than breaks.
 */
export function isInSidebar(parentElement: ShadowRoot | HTMLElement): boolean {
  const host =
    parentElement instanceof ShadowRoot ? parentElement.host : parentElement;
  return host.closest('[data-testid="stSidebar"]') !== null;
}
