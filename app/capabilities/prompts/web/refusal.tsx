/**
 * The prompts surface's shared refusal face (W8 Task 12): the save gate's
 * 422 rendered in the states reference's exact copy family — the headline
 * names the refusal by its localized reason, and everything the wire answers
 * otherwise (the framework's validation body, an outage) stays on the honest
 * generic line. The backend's own English detail sentence never reaches the
 * face: the reason is the copy. The save, the preview and the live test
 * render the same face: one family, one spelling.
 */
import { useTranslation } from "@shell/lib/i18n";

import type { WireError } from "./promptsQuery";

/** The closed refusal vocabulary the render sandbox and the scope rules
 *  answer with — the same tuple the kernel's registry names. A reason
 *  outside it names itself raw rather than a wrong family. */
const REASONS: ReadonlySet<string> = new Set([
  "budget",
  "contract",
  "forbidden",
  "include-cycle",
  "include-depth",
  "include-missing",
  "novel-scope",
  "runtime",
  "syntax",
  "undefined-variable",
  "unknown-novel",
]);

/** The gate's refusal body when the wire answered one. FastAPI's
 *  HTTPException wraps the refusal in `detail` (`{detail: {reason, detail}}`
 *  — the API pins' shape), so both the wrapped and the bare spelling are
 *  accepted; the framework's validation body and every other failure answer
 *  null. */
function refusalOf(body: unknown): { reason: string; detail: string } | null {
  const candidates =
    typeof body === "object" && body !== null ? [body, (body as { detail?: unknown }).detail] : [body];
  for (const candidate of candidates) {
    if (typeof candidate !== "object" || candidate === null) continue;
    const shape = candidate as { reason?: unknown; detail?: unknown };
    if (typeof shape.reason === "string" && typeof shape.detail === "string" && shape.detail !== "") {
      return { reason: shape.reason, detail: shape.detail };
    }
  }
  return null;
}

export function RefusalFace({
  failure,
  testId = "refusal-face",
  prefix,
}: {
  failure: WireError;
  testId?: string;
  /** A face-specific line rendered inside the alert above the refusal —
   *  the live test's "the draft did not pass the save check". */
  prefix?: string;
}) {
  const t = useTranslation();
  const refusal = refusalOf(failure.body);
  const known = refusal !== null && REASONS.has(refusal.reason);
  const reasonLabel = refusal === null ? "" : known ? t(`prompts.refusal.reason.${refusal.reason}` as Parameters<typeof t>[0]) : refusal.reason;
  return (
    <div
      role="alert"
      data-testid={testId}
      className="rounded border border-danger/40 bg-panel p-3 text-label text-danger"
    >
      {prefix !== undefined && <p className="mb-1 font-semibold">{prefix}</p>}
      {refusal !== null && known ? (
        <p className="font-semibold">{t("prompts.refusal.headline", { reason: reasonLabel })}</p>
      ) : (
        <p>{t("prompts.errors.generic")}</p>
      )}
    </div>
  );
}
