/**
 * Slash-command contracts (CR-AUFG-07-20).
 *
 * Frontend-only discovery layer over existing AI operations. This file holds
 * the contract types only — no runtime behaviour, no transport, no React — so
 * it is trivially testable and free of heavy imports.
 *
 * Spec: docs/features/ai-ux/CR-AUFG-07-20-slash-commands-ai-actions.md
 *   - `AISlashCommandDefinition` is the authoritative contract (spec §18/§57).
 *   - Commands reference existing AI Operation Inventory `operation_id` values
 *     (spec §57/§81) and dispatch through {@link SlashCommandDispatchContext},
 *     never to transport/API directly (spec §42).
 */

/**
 * Availability outcome for a slash command in the current editor context.
 *
 * - `available`: the command can run now.
 * - `no-selection`: the command requires a text selection and none exists.
 * - `unavailable`: the host surface did not wire this operation's handler.
 */
export type SlashCommandAvailability = "available" | "no-selection" | "unavailable";

/** Inputs to {@link AISlashCommandDefinition.availability}. */
export interface SlashCommandAvailabilityInput {
  /** Whether the editor currently has a non-empty text selection. */
  readonly hasSelection: boolean;
  /** Whether the host wired the handler this command needs. */
  readonly wired: boolean;
}

/**
 * The typed surface a slash command dispatches against. The host (TipTapEditor)
 * assembles this from existing operation hooks/panels; the registry never calls
 * transport directly (spec §42). Loading/cancel/error stay owned by the routed
 * operation (spec §71).
 */
export interface SlashCommandDispatchContext {
  /** writing.rewrite — open the governed rewrite flow for the selection. */
  readonly rewriteSelection: () => void;
  /** writing.continue — continue writing from the caret. */
  readonly continueWriting: () => void;
  /** writing.generation — open the full-draft generation panel. */
  readonly generateDraft: () => void;
  /** writing.co_author — open the co-author flow for the selection. */
  readonly coAuthorSelection: () => void;
  /** chat.free_assistant — open the assistant chat, optionally prefilled. */
  readonly askChat: (prefilledQuestion?: string) => void;
  /** chat.free_assistant — ask the assistant to explain the selection. */
  readonly explainSelection: () => void;
}

/** Dispatch signature shared by every command definition. */
export type SlashCommandDispatchFn = (ctx: SlashCommandDispatchContext) => void;

/**
 * Authoritative slash-command definition (spec §18/§57).
 */
export interface AISlashCommandDefinition {
  /** Stable canonical id (also used for filtering and i18n key suffixes). */
  readonly id: string;
  /** References an existing AI Operation Inventory operation_id (spec §57). */
  readonly operationId: string;
  /** i18n key under `studio.slashCommands.*` for the visible label. */
  readonly labelKey: string;
  /** i18n key under `studio.slashCommands.*` for the description. */
  readonly descriptionKey: string;
  /** Additional matchable aliases (locale-independent tokens). */
  readonly aliases: readonly string[];
  /** Whether a text selection is required to run this command. */
  readonly requiresSelection: boolean;
  /** Computes availability in the current editor context. */
  readonly availability: (input: SlashCommandAvailabilityInput) => SlashCommandAvailability;
  /** Routes to an existing governed operation via the dispatch context. */
  readonly dispatch: SlashCommandDispatchFn;
}
