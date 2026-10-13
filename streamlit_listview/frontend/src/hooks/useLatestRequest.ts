import { useCallback, useRef } from "react";

/**
 * Numbers requests that finish frames after they start, so a request can tell
 * whether a later one has overtaken it. The returned `begin` starts a request
 * and returns a function that answers whether that request is still the
 * latest. `begin` keeps its identity across renders.
 *
 * The scroll hooks share one counter (see useScrollToId): a scroll that waits
 * for the browser must not move the list after a later scroll has.
 */
export function useLatestRequest(): () => () => boolean {
  const latest = useRef(0);
  return useCallback(() => {
    latest.current += 1;
    const request = latest.current;
    return () => latest.current === request;
  }, []);
}
