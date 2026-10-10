import { act, renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { useCollapse, type GroupKey } from "./useCollapse";

const NAMES = ["Fruit", "Vegetable"];

describe("useCollapse", () => {
  it("nothing is collapsed when collapsibleGroups is false (even if collapsedGroups set)", () => {
    const { result } = renderHook(() =>
      useCollapse({
        collapsibleGroups: false,
        collapsedGroups: "all",
        groupKeys: NAMES,
      }),
    );
    expect(result.current.isCollapsed("Fruit")).toBe(false);
    expect(result.current.isCollapsed("Vegetable")).toBe(false);
  });

  it('collapsedGroups="all" collapses every known group initially', () => {
    const { result } = renderHook(() =>
      useCollapse({
        collapsibleGroups: true,
        collapsedGroups: "all",
        groupKeys: NAMES,
      }),
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
        groupKeys: NAMES,
      }),
    );
    expect(result.current.isCollapsed("Fruit")).toBe(true);
    expect(result.current.isCollapsed("Vegetable")).toBe(false);
    expect(result.current.isCollapsed("Nope")).toBe(false);
  });

  it("null collapsedGroups starts everything expanded", () => {
    const { result } = renderHook(() =>
      useCollapse({
        collapsibleGroups: true,
        collapsedGroups: null,
        groupKeys: NAMES,
      }),
    );
    expect(result.current.isCollapsed("Fruit")).toBe(false);
  });

  it("toggle flips a group; expand forces it open", () => {
    const { result } = renderHook(() =>
      useCollapse({
        collapsibleGroups: true,
        collapsedGroups: null,
        groupKeys: NAMES,
      }),
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
      useCollapse({
        collapsibleGroups: true,
        collapsedGroups: null,
        groupKeys: NAMES,
      }),
    );
    act(() => result.current.expand("Fruit"));
    expect(result.current.isCollapsed("Fruit")).toBe(false);
  });

  it("a seed made at mount survives the reconcile effect and later reruns", () => {
    // The reconcile effect also runs on mount; it must not prune the names the
    // initializer just seeded (the groups were already "seen" at that point).
    const { result, rerender } = renderHook(
      ({ groupKeys }) =>
        useCollapse({
          collapsibleGroups: true,
          collapsedGroups: ["Fruit"],
          groupKeys,
        }),
      { initialProps: { groupKeys: [...NAMES] } },
    );
    expect(result.current.isCollapsed("Fruit")).toBe(true);
    rerender({ groupKeys: [...NAMES] }); // same names, fresh array identity
    expect(result.current.isCollapsed("Fruit")).toBe(true);
  });

  it("applies collapsedGroups to groups whose options only arrive on a later rerun", () => {
    // A keyed instance does not remount, so options fetched async / behind a
    // "load data" button reach the hook with groupKeys still empty. The config
    // must apply when the groups first show up, not be silently inert.
    const { result, rerender } = renderHook(
      ({ groupKeys }) =>
        useCollapse({
          collapsibleGroups: true,
          collapsedGroups: ["Fruit"],
          groupKeys,
        }),
      { initialProps: { groupKeys: [] as string[] } },
    );
    expect(result.current.isCollapsed("Fruit")).toBe(false); // nothing to collapse yet
    rerender({ groupKeys: NAMES });
    expect(result.current.isCollapsed("Fruit")).toBe(true);
    expect(result.current.isCollapsed("Vegetable")).toBe(false); // not configured
  });

  it('collapsedGroups="all" applies to a group seen for the first time after mount', () => {
    const { result, rerender } = renderHook(
      ({ groupKeys }) =>
        useCollapse({
          collapsibleGroups: true,
          collapsedGroups: "all",
          groupKeys,
        }),
      { initialProps: { groupKeys: [] as string[] } },
    );
    rerender({ groupKeys: ["Fruit"] });
    expect(result.current.isCollapsed("Fruit")).toBe(true);
    rerender({ groupKeys: ["Fruit", "Vegetable"] }); // Vegetable is new
    expect(result.current.isCollapsed("Vegetable")).toBe(true);
  });

  it("a manual toggle is never undone when the options change", () => {
    // Once a group has been seen the user owns it: neither the expanded nor the
    // collapsed hand-set state may be re-seeded from the config afterwards.
    const { result, rerender } = renderHook(
      ({ groupKeys }) =>
        useCollapse({
          collapsibleGroups: true,
          collapsedGroups: ["Fruit"],
          groupKeys,
        }),
      { initialProps: { groupKeys: [...NAMES] } },
    );
    act(() => result.current.expand("Fruit")); // user opens the seeded-collapsed group
    act(() => result.current.toggle("Vegetable")); // and closes another by hand
    rerender({ groupKeys: [...NAMES, "Dairy"] }); // options change (a group is added)
    expect(result.current.isCollapsed("Fruit")).toBe(false);
    expect(result.current.isCollapsed("Vegetable")).toBe(true);
    expect(result.current.isCollapsed("Dairy")).toBe(false); // new, not configured
  });

  it("a group that disappears then reappears comes back open (stale name pruned)", () => {
    // Documented contract: groups appearing in later reruns default to open. A
    // group seeded collapsed that vanishes and returns must NOT stay collapsed.
    const { result, rerender } = renderHook(
      ({ groupKeys }) =>
        useCollapse({
          collapsibleGroups: true,
          collapsedGroups: ["Fruit"],
          groupKeys,
        }),
      { initialProps: { groupKeys: ["Fruit", "Vegetable"] } },
    );
    expect(result.current.isCollapsed("Fruit")).toBe(true);
    rerender({ groupKeys: ["Vegetable"] }); // Fruit removed
    rerender({ groupKeys: ["Fruit", "Vegetable"] }); // Fruit reappears
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
          groupKeys: ["Fish", "Fowl"],
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
      ({ collapsibleGroups, groupKeys }) =>
        useCollapse({
          collapsibleGroups,
          collapsedGroups: ["Fish"],
          groupKeys,
        }),
      {
        initialProps: { collapsibleGroups: false, groupKeys: [] as string[] },
      },
    );
    rerender({ collapsibleGroups: true, groupKeys: ["Fish"] });
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
          groupKeys: ["Fish"],
        }),
      { initialProps: { collapsibleGroups: true } },
    );
    expect(result.current.isCollapsed("Fish")).toBe(true); // seeded at mount
    act(() => result.current.expand("Fish")); // user takes ownership
    rerender({ collapsibleGroups: false });
    rerender({ collapsibleGroups: true });
    expect(result.current.isCollapsed("Fish")).toBe(false); // not re-seeded
  });

  it('"all" collapses the block without a group (key null), and so does a list holding null', () => {
    const all = renderHook(() =>
      useCollapse({
        collapsibleGroups: true,
        collapsedGroups: "all",
        groupKeys: ["Fruit", null],
      }),
    );
    expect(all.result.current.isCollapsed(null)).toBe(true);
    // The hook matches keys exactly: the container maps ungrouped_label in the
    // caller's list to null, so a string never names the null block here.
    const named = renderHook(() =>
      useCollapse({
        collapsibleGroups: true,
        collapsedGroups: ["Other", "Fruit"],
        groupKeys: ["Fruit", null],
      }),
    );
    expect(named.result.current.isCollapsed(null)).toBe(false);
    expect(named.result.current.isCollapsed("Fruit")).toBe(true);
    const mapped = renderHook(() =>
      useCollapse({
        collapsibleGroups: true,
        collapsedGroups: [null],
        groupKeys: ["Fruit", null],
      }),
    );
    expect(mapped.result.current.isCollapsed(null)).toBe(true);
    expect(mapped.result.current.isCollapsed("Fruit")).toBe(false);
  });

  it("keeps the block without a group apart from a group named like its header", () => {
    const { result } = renderHook(() =>
      useCollapse({
        collapsibleGroups: true,
        collapsedGroups: null,
        groupKeys: ["Other", null],
      }),
    );
    act(() => result.current.toggle(null));
    expect(result.current.isCollapsed(null)).toBe(true);
    expect(result.current.isCollapsed("Other")).toBe(false);
  });

  it("an expand counts as a sighting, so the seed cannot close a group opened before it appears", () => {
    // An add under accept_new_options opens the block without a group in the
    // event that creates it; the key arrives with the next render. Under "all"
    // the first-sighting seed would close the block over the row just added.
    const { result, rerender } = renderHook(
      ({ groupKeys }) =>
        useCollapse({
          collapsibleGroups: true,
          collapsedGroups: "all",
          groupKeys,
        }),
      { initialProps: { groupKeys: ["Fruit"] as GroupKey[] } },
    );
    act(() => result.current.expand(null));
    rerender({ groupKeys: ["Fruit", null] });
    expect(result.current.isCollapsed(null)).toBe(false);
    expect(result.current.isCollapsed("Fruit")).toBe(true);
  });

  it("an expand while collapsibleGroups is off spends no seed", () => {
    // Like every sighting, an expand counts only while the header is a toggle.
    const { result, rerender } = renderHook(
      ({ collapsibleGroups, groupKeys }) =>
        useCollapse({ collapsibleGroups, collapsedGroups: "all", groupKeys }),
      {
        initialProps: {
          collapsibleGroups: false,
          groupKeys: ["Fruit"] as GroupKey[],
        },
      },
    );
    act(() => result.current.expand(null));
    rerender({ collapsibleGroups: true, groupKeys: ["Fruit", null] });
    expect(result.current.isCollapsed(null)).toBe(true);
  });

  it("returns a referentially stable object across re-renders with unchanged inputs", () => {
    // The container memoizes off this object identity (focusableItems); a fresh
    // object every render would defeat that memo and re-filter on every render.
    const props = {
      collapsibleGroups: true,
      collapsedGroups: null as string[] | "all" | null,
      groupKeys: NAMES,
    };
    const { result, rerender } = renderHook(() => useCollapse(props));
    const first = result.current;
    rerender();
    expect(result.current).toBe(first);
  });
});
