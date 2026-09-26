import "@testing-library/jest-dom/vitest";

// JSDOM does not implement scrollIntoView. Add a no-op stub so that tests can
// spy on it with vi.spyOn(Element.prototype, "scrollIntoView").
if (!Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = () => {};
}

// Tell React 18's scheduler that we are in an act()-aware test environment.
// Without this flag, React prints a warning that act() is not configured when
// tests call `await act(async () => { ... })` to flush renders and state
// updates. The flag does not change React's flushing behaviour itself; the
// synchronous drain is produced by the act() wrappers in the individual tests.
// @see https://reactjs.org/blog/2022/03/08/react-18-upgrade-guide.html#configuring-your-testing-environment
// eslint-disable-next-line @typescript-eslint/no-explicit-any
(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;
