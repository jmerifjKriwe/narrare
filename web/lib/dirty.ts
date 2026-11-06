/** Same value: identity for primitives, the serialised form for plain data.
 *  A form field is a string today; an array or a nested object still counts as
 *  unchanged when its content is unchanged, so a snapshot taken with `[1]`
 *  does not read dirty against a fresh `[1]`. */
function sameValue(left: unknown, right: unknown): boolean {
  if (Object.is(left, right)) return true;
  if (typeof left !== "object" || typeof right !== "object" || left === null || right === null) {
    return false;
  }
  return JSON.stringify(left) === JSON.stringify(right);
}

/** The fields whose value differs from the form's load-time snapshot. */
export function dirtyFields<T extends Record<string, unknown>>(
  current: T,
  snapshot: T,
): (keyof T)[] {
  return (Object.keys(current) as (keyof T)[]).filter(
    (key) => !sameValue(current[key], snapshot[key]),
  );
}
