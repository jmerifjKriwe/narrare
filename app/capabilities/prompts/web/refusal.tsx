/**
 * The prompts surface's shared refusal face (W8 Task 12): the save gate's
 * 422 rendered in the states reference's exact copy family — the headline
 * names the refusal by its localized reason, and, when the wire carried the
 * fact that names the cause, one localized place sentence underneath it.
 * Everything the wire answers otherwise (the framework's validation body, an
 * outage) stays on the honest generic line. The backend's own English detail
 * sentence never reaches the face: the reason and the catalog's place
 * sentence are the copy. The save, the preview and the live test render the
 * same face: one family, one spelling.
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

/** The fact each reason's place sentence reads. A reason absent here needs no
 *  fact, so its place sentence never renders even if a stray key rides on. */
const PLACE_FACT: Readonly<Record<string, "line" | "name">> = {
  "include-cycle": "name",
  "include-depth": "name",
  "include-missing": "name",
  syntax: "line",
  "undefined-variable": "name",
};

/** The gate's refusal body when the wire answered one. FastAPI's
 *  HTTPException wraps the refusal in `detail` (`{detail: {reason, detail}}`
 *  — the API pins' shape), so both the wrapped and the bare spelling are
 *  accepted; the framework's validation body and every other failure answer
 *  null. The fact keys ride only when the cause named itself. */
interface Refusal {
  reason: string;
  detail: string;
  line?: number;
  name?: string;
}

function refusalOf(body: unknown): Refusal | null {
  const candidates =
    typeof body === "object" && body !== null ? [body, (body as { detail?: unknown }).detail] : [body];
  for (const candidate of candidates) {
    if (typeof candidate !== "object" || candidate === null) continue;
    const shape = candidate as { reason?: unknown; detail?: unknown; line?: unknown; name?: unknown };
    if (typeof shape.reason === "string" && typeof shape.detail === "string" && shape.detail !== "") {
      return {
        reason: shape.reason,
        detail: shape.detail,
        ...(typeof shape.line === "number" ? { line: shape.line } : {}),
        ...(typeof shape.name === "string" && shape.name !== "" ? { name: shape.name } : {}),
      };
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

  function placeSentence(carried: Refusal): string | null {
    const fact = PLACE_FACT[carried.reason];
    if (fact === undefined) return null;
    const value = carried[fact];
    if (value === undefined) return null;
    const key = `prompts.refusal.place.${carried.reason}` as Parameters<typeof t>[0];
    return t(key, { [fact]: value });
  }

  const place = refusal !== null && known ? placeSentence(refusal) : null;
  return (
    <div
      role="alert"
      data-testid={testId}
      className="rounded border border-danger/40 bg-panel p-3 text-label text-danger"
    >
      {prefix !== undefined && <p className="mb-1 font-semibold">{prefix}</p>}
      {refusal !== null && known ? (
        <>
          <p className="font-semibold">{t("prompts.refusal.headline", { reason: reasonLabel })}</p>
          {place !== null && <p className="mt-1">{place}</p>}
        </>
      ) : (
        <p>{t("prompts.errors.generic")}</p>
      )}
    </div>
  );
}
