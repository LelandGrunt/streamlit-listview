import {
  FrontendRenderer,
  FrontendRendererArgs,
} from "@streamlit/component-v2-lib";
import { StrictMode } from "react";
import { createRoot, Root } from "react-dom/client";

import Listview from "./Listview";
import type { ListviewData, ListviewState } from "./types";
import { isInSidebar } from "./utils/container";
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

  // Cleanup on unmount: unmount the tree and drop the cached root so a later
  // remount starts fresh.
  return () => {
    const root = reactRoots.get(parentElement);
    if (root) {
      root.unmount();
      reactRoots.delete(parentElement);
    }
  };
};

export default ListviewRoot;
