import {
  FrontendRenderer,
  FrontendRendererArgs,
} from "@streamlit/component-v2-lib";
import { StrictMode } from "react";
import { createRoot, Root } from "react-dom/client";

import Listview from "./Listview";
import type { ListviewData, ListviewState } from "./types";
import { isHostConnected, isInSidebar } from "./utils/container";
import "./listview.css";

// One React root per component instance (parentElement). Streamlit may mount
// multiple listviews on the same page; each gets its own cached root so a
// re-invocation re-renders the existing tree instead of creating a new one.
const reactRoots: WeakMap<FrontendRendererArgs["parentElement"], Root> =
  new WeakMap();

const ListviewRoot: FrontendRenderer<ListviewState, ListviewData> = (args) => {
  const { data, parentElement, setStateValue } = args;

  // Query the root node defined by the Python `html=` scaffold
  // (<div class="listview-root">).
  const rootElement = parentElement.querySelector(".listview-root");

  if (!rootElement) {
    throw new Error("Unexpected: .listview-root element not found");
  }

  // Reuse a cached React root for this instance, or create one on first call.
  // @see https://react.dev/reference/react-dom/client/createRoot
  let reactRoot = reactRoots.get(parentElement);
  if (!reactRoot) {
    reactRoot = createRoot(rootElement);
    reactRoots.set(parentElement, reactRoot);
  }

  // Render / re-render. We never call setStateValue here — the initial
  // selection is seeded from Python via the V2 `default=` mount parameter;
  // writing it on first render would force an extra rerun and fire
  // on_selection_change for a non-user change.
  //
  // Which Streamlit container we mounted into. Resolved here, from the only
  // handle on the host position, so the flag reaches the root on the FIRST
  // render — the sidebar theme swaps the two surface tokens, and a value that
  // arrived a frame late would flash the main-body colors on every mount.
  // Re-derived per invocation rather than cached: a rerun is free, and a keyed
  // widget that moves between the sidebar and the main body remounts anyway.
  reactRoot.render(
    <StrictMode>
      <Listview
        data={data}
        setStateValue={setStateValue}
        inSidebar={isInSidebar(parentElement)}
      />
    </StrictMode>,
  );

  // Cleanup. Streamlit calls it in two situations, and only one of them ends
  // the instance:
  //
  // 1. The component unmounts. React has already taken the host out of the
  //    document, so the tree is unmounted and the cached root dropped; a later
  //    mount starts fresh.
  // 2. Streamlit's loader effect (useHandleJsContent) cancelled a run after
  //    this module had initialized — `adoptCleanup` then runs the cleanup at
  //    once — and its next run calls this renderer again on the SAME
  //    parentElement. The effect re-runs on every change of its data or its
  //    theme, and the sidebar hands it a new theme object on every render
  //    (ThemedSidebar builds one without memoizing), so one click on a sidebar
  //    listview runs it about three times within 10 ms, each run cancelling
  //    the one before. A cancel that lands between a script's `load` event and
  //    its `import()` completing takes this path. Unmounting here replaced the
  //    tree on the next run: the click lost the keyboard focus, the search
  //    text, the collapsed groups and the scroll position, on about one click
  //    in six in st.sidebar (measured 2026-10-13, Streamlit 1.65).
  //
  // The host tells the two apart: it is still in the document in case 2, and
  // the next run then re-renders into the cached root, which keeps the state.
  return () => {
    if (isHostConnected(parentElement)) {
      return;
    }
    const root = reactRoots.get(parentElement);
    if (root) {
      root.unmount();
      reactRoots.delete(parentElement);
    }
  };
};

export default ListviewRoot;
