import { useCallback, useEffect, useMemo, useRef, useState } from "react";

export interface UseCollapseArgs {
  collapsibleGroups: boolean;
  /** Initial collapsed set: "all", a list of group names, or null (all open). */
  collapsedGroups: string[] | "all" | null;
  /** Distinct group names currently present; `collapsedGroups` is applied to each the first time it appears here. */
  groupNames: string[];
}

export interface UseCollapseResult {
  isCollapsed: (name: string) => boolean;
  toggle: (name: string) => void;
  expand: (name: string) => void;
}

/**
 * Which of `names` the Python config wants collapsed. Shared by the mount seed
 * and the first-sighting seed in the effect below, so a group is treated the
 * same way whenever it happens to show up.
 */
function configCollapsed(args: UseCollapseArgs, names: string[]): string[] {
  if (!args.collapsibleGroups || args.collapsedGroups == null) {
    return [];
  }
  if (args.collapsedGroups === "all") {
    return names;
  }
  // array: only names with a group to apply them to right now. A name without
  // one is not discarded — it stays pending and applies if such a group ever
  // appears (that is how a config name outlives an empty first render).
  const wanted = new Set(args.collapsedGroups);
  return names.filter((n) => wanted.has(n));
}

/**
 * Per-group open/closed state. `collapsed_groups` is initial state only, applied
 * to each group the FIRST time that group is seen: at mount for the groups the
 * options already contain, and on the rerun that first brings a group in for the
 * rest — a keyed instance never remounts, so options produced by an async/cached
 * fetch or a "load data" button reach the hook with `groupNames` still empty, and
 * a config resolved once at mount would be inert for the whole session. Once a
 * group has been seen the user owns it: a manual toggle is never overridden, and
 * a group that disappears and comes back defaults to open. When
 * `collapsibleGroups` is false, nothing is ever collapsed.
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
  const { collapsibleGroups, groupNames } = args;
  const [collapsed, setCollapsed] = useState<Set<string>>(
    () => new Set(configCollapsed(args, groupNames)),
  );

  // Group names the config has already been applied to — seeded with the first
  // render's names, the ones the initializer above just handled, so the mount run
  // of the effect below re-seeds nothing. Only when the headers are toggles: a
  // mount with the feature off applied nothing, so recording its names here would
  // burn their one-time seed (see the docstring). Names are never removed: a
  // group that vanishes and returns still counts as seen, so it comes back OPEN
  // instead of being collapsed by the config a second time.
  const seenGroups = useRef<Set<string>>(
    new Set(collapsibleGroups ? groupNames : []),
  );

  // Reconcile the collapsed set with the groups that currently exist, in one pass:
  //  - groups seen for the first time get `collapsedGroups` applied, which is
  //    what keeps the config alive when the options arrive on a later rerun;
  //  - names of groups that no longer exist are pruned, so a group that
  //    disappears and later reappears defaults to OPEN. Without this the set
  //    retains stale names forever and a vanished-then-returned group would come
  //    back collapsed.
  // Groups already seen are left exactly as they are, so a user's manual
  // expand/collapse survives any later options change. Seeding only ever adds
  // names of groups that exist, so the two halves never fight each other (in
  // particular the mount run cannot prune away what the initializer just seeded).
  // Returns `prev` unchanged when nothing moves, so React skips the re-render in
  // the common (stable) case.
  useEffect(() => {
    const seen = seenGroups.current;
    const firstSeen = groupNames.filter((name) => !seen.has(name));
    // Record a sighting only while the header is a toggle, mirroring the ref
    // initializer above: while the feature is off, toCollapse is [] and marking
    // these names seen would spend their seed on a render that applied nothing.
    if (collapsibleGroups) {
      for (const name of firstSeen) {
        seen.add(name);
      }
    }
    const toCollapse = configCollapsed(args, firstSeen);
    setCollapsed((prev) => {
      const known = new Set(groupNames);
      let changed = false;
      const next = new Set<string>();
      for (const name of prev) {
        if (known.has(name)) {
          next.add(name);
        } else {
          changed = true;
        }
      }
      // A first sighting is by construction absent from `prev` (a name only gets
      // in via the seed for its own first sighting or a user toggle of a group
      // that had already rendered), so each of these is a real change.
      for (const name of toCollapse) {
        next.add(name);
        changed = true;
      }
      return changed ? next : prev;
    });
    // `collapsedGroups` (via `args`) intentionally excluded from the deps: it is
    // initial state only, so a config change on a keyed instance must never
    // re-collapse groups the user already owns. Reading the latest config via
    // closure therefore only affects groups not yet seen. `collapsibleGroups` IS
    // a dep: the flip to on is when unseen groups' headers first become toggles,
    // and the seed must apply on that rerun even if `groupNames` happens to keep
    // its identity across it.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [collapsibleGroups, groupNames]);

  const isCollapsed = useCallback(
    (name: string) => collapsibleGroups && collapsed.has(name),
    [collapsibleGroups, collapsed],
  );

  const toggle = useCallback((name: string) => {
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (next.has(name)) {
        next.delete(name);
      } else {
        next.add(name);
      }
      return next;
    });
  }, []);

  const expand = useCallback((name: string) => {
    setCollapsed((prev) => {
      if (!prev.has(name)) {
        return prev;
      }
      const next = new Set(prev);
      next.delete(name);
      return next;
    });
  }, []);

  // Stable object identity (members are themselves stable unless their inputs
  // change), so consumers that memoize off `collapse` (e.g. the container's
  // focusableItems) are not invalidated on every render.
  return useMemo(
    () => ({ isCollapsed, toggle, expand }),
    [isCollapsed, toggle, expand],
  );
}
