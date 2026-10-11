import { useCallback, useEffect, useMemo, useRef, useState } from "react";

/**
 * A group as this hook tracks it: its name, or `null` for the block of rows
 * without a group, which carries a header of its own in a grouped list (see
 * `blocksFor` in utils/blocks.ts). `null` is no string, so no group name a caller
 * passes can collide with that block, not even one spelled like its header.
 */
export type GroupKey = string | null;

export interface UseCollapseArgs {
  collapsibleGroups: boolean;
  /**
   * Initial collapsed set: "all", a list of group keys, or null (all open). The
   * container maps ungrouped_label in the caller's list to `null`.
   */
  collapsedGroups: GroupKey[] | "all" | null;
  /**
   * The groups present now: every group name, plus `null` while the block
   * without a group carries a header. `collapsedGroups` is applied to each the
   * first time it appears here.
   */
  groupKeys: GroupKey[];
}

export interface UseCollapseResult {
  isCollapsed: (key: GroupKey) => boolean;
  toggle: (key: GroupKey) => void;
  /** Opens a group and counts it as seen (see the callback). */
  expand: (key: GroupKey) => void;
}

/**
 * Which of `keys` the Python config wants collapsed. Shared by the mount seed
 * and the first-sighting seed in the effect below, so a group is treated the
 * same way whenever it happens to show up.
 */
function configCollapsed(args: UseCollapseArgs, keys: GroupKey[]): GroupKey[] {
  if (!args.collapsibleGroups || args.collapsedGroups == null) {
    return [];
  }
  if (args.collapsedGroups === "all") {
    return keys;
  }
  // array: only names with a group to apply them to right now. A name without
  // one is not discarded — it stays pending and applies if such a group ever
  // appears (that is how a config name outlives an empty first render).
  const wanted = new Set<GroupKey>(args.collapsedGroups);
  return keys.filter((key) => wanted.has(key));
}

/**
 * Per-group open/closed state, keyed by `GroupKey`. `collapsed_groups` is
 * initial state only, applied to each group the FIRST time that group is seen:
 * at mount for the groups the options already contain, and on the rerun that
 * first brings a group in for the rest — a keyed instance never remounts, so
 * options produced by an async/cached fetch or a "load data" button reach the
 * hook with `groupKeys` still empty, and a config resolved once at mount would
 * be inert for the whole session. Once a group has been seen the user owns it:
 * a manual toggle is never overridden, and a group that disappears and comes
 * back defaults to open. When `collapsibleGroups` is false, nothing is ever
 * collapsed.
 *
 * A group is "seen" only while its header is a toggle (`collapsibleGroups`
 * true). While the feature is off the config is inert (configCollapsed returns
 * []), so counting those sightings would consume each group's one-time seed on a
 * render that could not apply it — flipping `collapsible_groups` on later for a
 * keyed instance would then find every group "seen" and the config silently
 * dead. Groups sighted only while the feature was off are therefore first-seen
 * on the flip to on (the seed applies then); groups the user could actually
 * toggle stay owned across off/on flips.
 */
export function useCollapse(args: UseCollapseArgs): UseCollapseResult {
  const { collapsibleGroups, groupKeys } = args;
  const [collapsed, setCollapsed] = useState<Set<GroupKey>>(
    () => new Set(configCollapsed(args, groupKeys)),
  );

  // Group keys the config has already been applied to — seeded with the first
  // render's keys, the ones the initializer above just handled, so the mount run
  // of the effect below re-seeds nothing. Only when the headers are toggles: a
  // mount with the feature off applied nothing, so recording its keys here would
  // burn their one-time seed (see the docstring). Keys are never removed: a
  // group that vanishes and returns still counts as seen, so it comes back OPEN
  // instead of being collapsed by the config a second time.
  const seenGroups = useRef<Set<GroupKey>>(
    new Set(collapsibleGroups ? groupKeys : []),
  );

  // Reconcile the collapsed set with the groups that currently exist, in one pass:
  //  - groups seen for the first time get `collapsedGroups` applied, which is
  //    what keeps the config alive when the options arrive on a later rerun;
  //  - keys of groups that no longer exist are pruned, so a group that
  //    disappears and later reappears defaults to OPEN. Without this the set
  //    retains stale keys forever and a vanished-then-returned group would come
  //    back collapsed.
  // Groups already seen are left exactly as they are, so a user's manual
  // expand/collapse survives any later options change. Seeding only ever adds
  // keys of groups that exist, so the two halves never fight each other (in
  // particular the mount run cannot prune away what the initializer just seeded).
  // Returns `prev` unchanged when nothing moves, so React skips the re-render in
  // the common (stable) case.
  useEffect(() => {
    const seen = seenGroups.current;
    const firstSeen = groupKeys.filter((key) => !seen.has(key));
    // Record a sighting only while the header is a toggle, mirroring the ref
    // initializer above: while the feature is off, toCollapse is [] and marking
    // these keys seen would spend their seed on a render that applied nothing.
    if (collapsibleGroups) {
      for (const key of firstSeen) {
        seen.add(key);
      }
    }
    const toCollapse = configCollapsed(args, firstSeen);
    setCollapsed((prev) => {
      const known = new Set(groupKeys);
      let changed = false;
      const next = new Set<GroupKey>();
      for (const key of prev) {
        if (known.has(key)) {
          next.add(key);
        } else {
          changed = true;
        }
      }
      // A first sighting is by construction absent from `prev` (a key only gets
      // in via the seed for its own first sighting or a user toggle of a group
      // that had already rendered), so each of these is a real change.
      for (const key of toCollapse) {
        next.add(key);
        changed = true;
      }
      return changed ? next : prev;
    });
    // `collapsedGroups` (via `args`) intentionally excluded from the deps: it is
    // initial state only, so a config change on a keyed instance must never
    // re-collapse groups the user already owns. Reading the latest config via
    // closure therefore only affects groups not yet seen. `collapsibleGroups` IS
    // a dep: the flip to on is when unseen groups' headers first become toggles,
    // and the seed must apply on that rerun even if `groupKeys` happens to keep
    // its identity across it.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [collapsibleGroups, groupKeys]);

  const isCollapsed = useCallback(
    (key: GroupKey) => collapsibleGroups && collapsed.has(key),
    [collapsibleGroups, collapsed],
  );

  const toggle = useCallback((key: GroupKey) => {
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  }, []);

  // Opens a group and records the sighting the effect above would otherwise make
  // later. That matters for a group that is not present yet: an add under
  // accept_new_options opens the block without a group in the same event that
  // brings the block in, and without the sighting the effect would seed it —
  // collapsed, under collapsed_groups="all" — on the next render and hide the
  // row just added. Recorded only while the header is a toggle, like every
  // sighting (see seenGroups).
  const expand = useCallback(
    (key: GroupKey) => {
      if (collapsibleGroups) {
        seenGroups.current.add(key);
      }
      setCollapsed((prev) => {
        if (!prev.has(key)) {
          return prev;
        }
        const next = new Set(prev);
        next.delete(key);
        return next;
      });
    },
    [collapsibleGroups],
  );

  // Stable object identity (members are themselves stable unless their inputs
  // change), so consumers that memoize off `collapse` (e.g. the container's
  // focusableItems) are not invalidated on every render.
  return useMemo(
    () => ({ isCollapsed, toggle, expand }),
    [isCollapsed, toggle, expand],
  );
}
