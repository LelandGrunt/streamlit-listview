import { act, renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { useCollapse } from "./useCollapse";

const NAMES = ["Fruit", "Vegetable"];

describe("useCollapse", () => {
  it("nothing is collapsed when collapsibleGroups is false (even if collapsedGroups set)", () => {
    const { result } = renderHook(() =>
      useCollapse({ collapsibleGroups: false, collapsedGroups: "all", groupNames: NAMES }),
    );
    expect(result.current.isCollapsed("Fruit")).toBe(false);
    expect(result.current.isCollapsed("Vegetable")).toBe(false);
  });

  it('collapsedGroups="all" collapses every known group initially', () => {
    const { result } = renderHook(() =>
      useCollapse({ collapsibleGroups: true, collapsedGroups: "all", groupNames: NAMES }),
    );
    expect(result.current.isCollapsed("Fruit")).toBe(true);
    expect(result.current.isCollapsed("Vegetable")).toBe(true);
  });

  it("an array collapses only listed groups; a name with no such group stays open", () => {
    // "Nope" is not discarded, only pending — it would apply if a group of that
    // name ever appeared (see the late-arriving-options tests below).
    const { result } = renderHook(() =>
      useCollapse({
        collapsibleGroups: true,
        collapsedGroups: ["Fruit", "Nope"],
        groupNames: NAMES,
      }),
    );
    expect(result.current.isCollapsed("Fruit")).toBe(true);
    expect(result.current.isCollapsed("Vegetable")).toBe(false);
    expect(result.current.isCollapsed("Nope")).toBe(false);
  });

  it("null collapsedGroups starts everything expanded", () => {
    const { result } = renderHook(() =>
      useCollapse({ collapsibleGroups: true, collapsedGroups: null, groupNames: NAMES }),
    );
    expect(result.current.isCollapsed("Fruit")).toBe(false);
  });

  it("toggle flips a group; expand forces it open", () => {
    const { result } = renderHook(() =>
      useCollapse({ collapsibleGroups: true, collapsedGroups: null, groupNames: NAMES }),
    );
    act(() => result.current.toggle("Fruit"));
    expect(result.current.isCollapsed("Fruit")).toBe(true);
    act(() => result.current.toggle("Fruit"));
    expect(result.current.isCollapsed("Fruit")).toBe(false);

    act(() => result.current.toggle("Vegetable"));
    expect(result.current.isCollapsed("Vegetable")).toBe(true);
    act(() => result.current.expand("Vegetable"));
    expect(result.current.isCollapsed("Vegetable")).toBe(false);
  });

  it("expand on an already-open group is a no-op", () => {
    const { result } = renderHook(() =>
      useCollapse({ collapsibleGroups: true, collapsedGroups: null, groupNames: NAMES }),
    );
    act(() => result.current.expand("Fruit"));
    expect(result.current.isCollapsed("Fruit")).toBe(false);
  });

  it("a seed made at mount survives the reconcile effect and later reruns", () => {
    // The reconcile effect also runs on mount; it must not prune the names the
    // initializer just seeded (the groups were already "seen" at that point).
    const { result, rerender } = renderHook(
      ({ groupNames }) =>
        useCollapse({ collapsibleGroups: true, collapsedGroups: ["Fruit"], groupNames }),
      { initialProps: { groupNames: [...NAMES] } },
    );
    expect(result.current.isCollapsed("Fruit")).toBe(true);
    rerender({ groupNames: [...NAMES] }); // same names, fresh array identity
    expect(result.current.isCollapsed("Fruit")).toBe(true);
  });

  it("applies collapsedGroups to groups whose options only arrive on a later rerun", () => {
    // A keyed instance does not remount, so options fetched async / behind a
    // "load data" button reach the hook with groupNames still empty. The config
    // must apply when the groups first show up, not be silently inert.
    const { result, rerender } = renderHook(
      ({ groupNames }) =>
        useCollapse({ collapsibleGroups: true, collapsedGroups: ["Fruit"], groupNames }),
      { initialProps: { groupNames: [] as string[] } },
    );
    expect(result.current.isCollapsed("Fruit")).toBe(false); // nothing to collapse yet
    rerender({ groupNames: NAMES });
    expect(result.current.isCollapsed("Fruit")).toBe(true);
    expect(result.current.isCollapsed("Vegetable")).toBe(false); // not configured
  });

  it('collapsedGroups="all" applies to a group seen for the first time after mount', () => {
    const { result, rerender } = renderHook(
      ({ groupNames }) =>
        useCollapse({ collapsibleGroups: true, collapsedGroups: "all", groupNames }),
      { initialProps: { groupNames: [] as string[] } },
    );
    rerender({ groupNames: ["Fruit"] });
    expect(result.current.isCollapsed("Fruit")).toBe(true);
    rerender({ groupNames: ["Fruit", "Vegetable"] }); // Vegetable is new
    expect(result.current.isCollapsed("Vegetable")).toBe(true);
  });

  it("a manual toggle is never undone when the options change", () => {
    // Once a group has been seen the user owns it: neither the expanded nor the
    // collapsed hand-set state may be re-seeded from the config afterwards.
    const { result, rerender } = renderHook(
      ({ groupNames }) =>
        useCollapse({ collapsibleGroups: true, collapsedGroups: ["Fruit"], groupNames }),
      { initialProps: { groupNames: [...NAMES] } },
    );
    act(() => result.current.expand("Fruit")); // user opens the seeded-collapsed group
    act(() => result.current.toggle("Vegetable")); // and closes another by hand
    rerender({ groupNames: [...NAMES, "Dairy"] }); // options change (a group is added)
    expect(result.current.isCollapsed("Fruit")).toBe(false);
    expect(result.current.isCollapsed("Vegetable")).toBe(true);
    expect(result.current.isCollapsed("Dairy")).toBe(false); // new, not configured
  });

  it("a group that disappears then reappears comes back open (stale name pruned)", () => {
    // Documented contract: groups appearing in later reruns default to open. A
    // group seeded collapsed that vanishes and returns must NOT stay collapsed.
    const { result, rerender } = renderHook(
      ({ groupNames }) =>
        useCollapse({ collapsibleGroups: true, collapsedGroups: ["Fruit"], groupNames }),
      { initialProps: { groupNames: ["Fruit", "Vegetable"] } },
    );
    expect(result.current.isCollapsed("Fruit")).toBe(true);
    rerender({ groupNames: ["Vegetable"] }); // Fruit removed
    rerender({ groupNames: ["Fruit", "Vegetable"] }); // Fruit reappears
    expect(result.current.isCollapsed("Fruit")).toBe(false);
  });

  it("keeps the seed pending while collapsibleGroups is off and applies it on the flip to on", () => {
    // Groups sighted while the feature is off must not count as "seen": nothing
    // could be applied to them then (the config is inert), so recording the
    // sighting would burn the one-time seed and leave collapsed_groups silently
    // dead when a keyed instance later turns collapsible_groups on.
    const { result, rerender } = renderHook(
      ({ collapsibleGroups }) =>
        useCollapse({
          collapsibleGroups,
          collapsedGroups: ["Fish"],
          groupNames: ["Fish", "Fowl"],
        }),
      { initialProps: { collapsibleGroups: false } },
    );
    expect(result.current.isCollapsed("Fish")).toBe(false); // feature off
    rerender({ collapsibleGroups: true });
    expect(result.current.isCollapsed("Fish")).toBe(true); // seed finally applies
    expect(result.current.isCollapsed("Fowl")).toBe(false); // not configured
  });

  it("seeds a group whose options only arrive after the flip to collapsible", () => {
    const { result, rerender } = renderHook(
      ({ collapsibleGroups, groupNames }) =>
        useCollapse({ collapsibleGroups, collapsedGroups: ["Fish"], groupNames }),
      {
        initialProps: { collapsibleGroups: false, groupNames: [] as string[] },
      },
    );
    rerender({ collapsibleGroups: true, groupNames: ["Fish"] });
    expect(result.current.isCollapsed("Fish")).toBe(true);
  });

  it("a group the user expanded while collapsible stays expanded across an off/on flip", () => {
    // The group was seen while its header was a toggle, so the user owns it: the
    // flip back to on must restore the hand-set state, not re-apply the seed.
    const { result, rerender } = renderHook(
      ({ collapsibleGroups }) =>
        useCollapse({
          collapsibleGroups,
          collapsedGroups: ["Fish"],
          groupNames: ["Fish"],
        }),
      { initialProps: { collapsibleGroups: true } },
    );
    expect(result.current.isCollapsed("Fish")).toBe(true); // seeded at mount
    act(() => result.current.expand("Fish")); // user takes ownership
    rerender({ collapsibleGroups: false });
    rerender({ collapsibleGroups: true });
    expect(result.current.isCollapsed("Fish")).toBe(false); // not re-seeded
  });

  it("returns a referentially stable object across re-renders with unchanged inputs", () => {
    // The container memoizes off this object identity (focusableItems); a fresh
    // object every render would defeat that memo and re-filter on every render.
    const props = {
      collapsibleGroups: true,
      collapsedGroups: null as string[] | "all" | null,
      groupNames: NAMES,
    };
    const { result, rerender } = renderHook(() => useCollapse(props));
    const first = result.current;
    rerender();
    expect(result.current).toBe(first);
  });
});
