/**
 * Slash-command registry (CR-AUFG-07-20).
 *
 * The initial command set routes to existing AI operations (spec §40). Each
 * command references an inventory `operation_id` (spec §57/§81) and dispatches
 * through {@link SlashCommandDispatchContext} — it never calls transport/API
 * directly (spec §42).
 */
import type {
  AISlashCommandDefinition,
  SlashCommandAvailability,
  SlashCommandAvailabilityInput,
} from "./contracts";

export type {
  AISlashCommandDefinition,
  SlashCommandAvailability,
  SlashCommandAvailabilityInput,
  SlashCommandDispatchContext,
  SlashCommandDispatchFn,
} from "./contracts";

/**
 * Operation ids the slash commands are allowed to reference (spec §81:
 * inventory-consistency gate). Sourced from
 * `scripts/checks/ai_operation_inventory.yaml`.
 *
 * `writing.explain` does not exist as a dedicated operation; `/explain` routes
 * to the free assistant chat (`chat.free_assistant`) with the selection as the
 * question — a documented UI-command variant over an existing operation.
 */
export const KNOWN_OPERATION_IDS: ReadonlySet<string> = new Set<string>([
  "writing.continue",
  "writing.generation",
  "writing.rewrite",
  "writing.co_author",
  "chat.free_assistant",
]);

/**
 * Default availability resolver derived from `requiresSelection`.
 *
 * - Unwired host handler → `unavailable` (actionable disabled guidance).
 * - Selection command without a selection → `no-selection`.
 * - Otherwise → `available`.
 */
export function defaultAvailability(
  requiresSelection: boolean,
): (input: SlashCommandAvailabilityInput) => SlashCommandAvailability {
  return ({ hasSelection, wired }: SlashCommandAvailabilityInput): SlashCommandAvailability => {
    if (!wired) return "unavailable";
    if (requiresSelection && !hasSelection) return "no-selection";
    return "available";
  };
}

/** Label/description key helper to keep definitions terse and consistent. */
function key(suffix: string): string {
  return `slashCommands.${suffix}`;
}

/**
 * The initial slash-command set (spec §40).
 *
 * Order is intentionally display-friendly (selection-free first, then
 * selection-required). Order is preserved by the menu when the query is empty.
 */
export const AI_SLASH_COMMANDS: readonly AISlashCommandDefinition[] = [
  {
    id: "continue",
    operationId: "writing.continue",
    labelKey: key("continue.label"),
    descriptionKey: key("continue.description"),
    aliases: ["extend", "keep-writing"],
    requiresSelection: false,
    availability: defaultAvailability(false),
    dispatch: (ctx) => ctx.continueWriting(),
  },
  {
    id: "draft",
    operationId: "writing.generation",
    labelKey: key("draft.label"),
    descriptionKey: key("draft.description"),
    aliases: ["generate", "write", "new-draft"],
    requiresSelection: false,
    availability: defaultAvailability(false),
    dispatch: (ctx) => ctx.generateDraft(),
  },
  {
    id: "rewrite",
    operationId: "writing.rewrite",
    labelKey: key("rewrite.label"),
    descriptionKey: key("rewrite.description"),
    aliases: ["rephrase", "improve"],
    requiresSelection: true,
    availability: defaultAvailability(true),
    dispatch: (ctx) => ctx.rewriteSelection(),
  },
  {
    id: "coauthor",
    operationId: "writing.co_author",
    labelKey: key("coauthor.label"),
    descriptionKey: key("coauthor.description"),
    aliases: ["co-author", "collaborate"],
    requiresSelection: true,
    availability: defaultAvailability(true),
    dispatch: (ctx) => ctx.coAuthorSelection(),
  },
  {
    id: "chat",
    operationId: "chat.free_assistant",
    labelKey: key("chat.label"),
    descriptionKey: key("chat.description"),
    aliases: ["ask", "assistant"],
    requiresSelection: false,
    availability: defaultAvailability(false),
    dispatch: (ctx) => ctx.askChat(),
  },
  {
    id: "explain",
    operationId: "chat.free_assistant",
    labelKey: key("explain.label"),
    descriptionKey: key("explain.description"),
    aliases: ["clarify", "why"],
    requiresSelection: true,
    availability: defaultAvailability(true),
    dispatch: (ctx) => ctx.explainSelection(),
  },
];
