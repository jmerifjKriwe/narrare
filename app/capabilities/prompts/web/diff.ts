/**
 * One aligned pair of the side-by-side diff: a side without a line has none.
 *
 * A changed line renders as a removal row followed by an addition row (a gap
 * in each column) rather than a paired row — the LCS stays dependency-free by
 * design (WP4 follow-up #397). Pairing would need a smarter diff.
 */
export type DiffRow = { left: string | null; right: string | null };

/**
 * The two texts as aligned line pairs, by the longest common subsequence —
 * the whole of the diff view, dependency-free by the plan's constraint.
 * Templates are short, so the quadratic table stays cheap.
 */
export function sideBySide(bundled: string, override: string): DiffRow[] {
  const left = bundled.split("\n");
  const right = override.split("\n");
  const common: number[][] = Array.from({ length: left.length + 1 }, () =>
    new Array<number>(right.length + 1).fill(0),
  );
  for (let i = left.length - 1; i >= 0; i--) {
    for (let j = right.length - 1; j >= 0; j--) {
      common[i][j] =
        left[i] === right[j]
          ? common[i + 1][j + 1] + 1
          : Math.max(common[i + 1][j], common[i][j + 1]);
    }
  }
  const rows: DiffRow[] = [];
  let i = 0;
  let j = 0;
  while (i < left.length && j < right.length) {
    if (left[i] === right[j]) {
      rows.push({ left: left[i], right: right[j] });
      i++;
      j++;
    } else if (common[i + 1][j] >= common[i][j + 1]) {
      rows.push({ left: left[i], right: null });
      i++;
    } else {
      rows.push({ left: null, right: right[j] });
      j++;
    }
  }
  while (i < left.length) {
    rows.push({ left: left[i], right: null });
    i++;
  }
  while (j < right.length) {
    rows.push({ left: null, right: right[j] });
    j++;
  }
  return rows;
}
