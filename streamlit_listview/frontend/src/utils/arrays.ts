/**
 * The element at `index`, for an index the caller keeps inside the array.
 *
 * `noUncheckedIndexedAccess` types every `array[index]` as possibly undefined.
 * Where the code guarantees the index (a loop bound, a length check, a regex
 * group that always takes part), this helper states the guarantee once and
 * throws if it ever breaks, where a `!` would hide the break. Not for arrays
 * that hold `undefined` as a value.
 */
export function elementAt<T>(array: readonly T[], index: number): T {
  const element = array[index];
  if (element === undefined) {
    throw new RangeError(
      `index ${index} is outside an array of length ${array.length}`,
    );
  }
  return element;
}
