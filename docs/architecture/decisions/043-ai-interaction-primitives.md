# ADR-043 — Shared AI Interaction Primitives

> **Status:** Implemented
> **Date:** 2026-06-08
> **Deciders:** Architecture Agent
> **Supersedes:** None
> **Related:** §16 AI-Interaction Standards (`ui-principles.md`), `connectSSE()` transport, CR-07 UX Audit

---

## Context

The CR-07 UX Audit (`_audit/results/content-review/cr-07-ux.md`) identified systemic
inconsistency across 8+ AI-powered frontend flows. Each flow independently implements
SSE client usage, cancel controls, error handling, loading states, connection-loss
recovery, and action labels — with varying completeness and correctness.

### Current State

**7 SSE consumer modules** in `packages/web/lib/api/`:

| Module | Functions | Domain |
|--------|-----------|--------|
| `generation-streams.ts` | `streamRewrite`, `streamExtend`, `streamGeneration` | Writing |
| `coauthor.ts` | `streamCoAuthor` | Writing: Co-Author |
| `chat.ts` | `chatApi.streamChat` | Chat |
| `suggest.ts` | `createSseSuggestionFetcher` | GhostText |
| `kb-sessions.ts` | `suggestField`, `requestInterview`, `requestEnhance` | KB Sessions |
| `timeline.ts` | `extractExpressionsSSE` | Timeline |
| `generation.ts` | `WritingSessionSocket` (WebSocket) | Sessions |

**1 transport layer**: `streaming.ts` (`connectSSE()`) — production-tested, stable.

**59 component locations** with manual `AbortController` patterns, inconsistent
error mapping, and no shared lifecycle state machine.

### Root Cause Analysis (2x "Why?")

**Symptom**: AI interaction flows have inconsistent UX — different loading behaviors,
different cancel patterns, different error messages, different connection-loss handling.

**Why?** Each of the 8+ flows independently implements the full AI interaction lifecycle
(loading, streaming, completion, error, cancel, connection loss) in its component or hook.

**Why? (Root Cause)**: There is no shared React-level primitive that encapsulates the
complete AI operation lifecycle. The canonical `connectSSE()` helper covers only the
SSE transport layer — it provides no lifecycle state machine, no error-to-i18n mapping,
no abort controller management, and no connection-loss detection.

The correct fix is not to patch each flow individually (symptom treatment), but to
extract a single, shared primitive that ALL AI flows use (root cause fix).

---

## Decision Drivers

1. **§16 Compliance**: All 8 §16 sub-rules must be enforced by the primitive, not
   by each component independently
2. **RULE-11 (No Silent Failures)**: Error mapping must never silently swallow errors
3. **RULE-16 (i18n)**: All user-facing error strings must use `studio.aiActions.*` keys
4. **RULE-20 (No Half-Implementations)**: The primitive must be complete — no
   "error mapping later" or "connection loss in phase 2"
5. **Composability**: Must work with all 7 existing SSE consumers without changing
   their interfaces
6. **Zero new runtime dependencies**: No new npm packages
7. **Testability**: The primitive must be unit-testable in isolation
8. **Machine-checkability**: Automated checks must verify §16 compliance

---

## Options Considered

### Option A — React Hook (`useAIOperation`)

A custom hook that encapsulates the full AI operation lifecycle: state machine,
AbortController management, error-to-i18n mapping, connection-loss detection with
partial output preservation, and retry logic.

**Architecture:**

```
Component
  └─ useAIOperation({ execute, ... })
       ├─ State machine: idle → loading → streaming → complete → error
       ├─ AbortController: create / expose / cleanup
       ├─ Error mapping: SSEStreamError → i18n user message
       ├─ Connection-loss: timeout detection + partial output + retry
       └─ Calls existing API function (streamRewrite, chatApi.streamChat, etc.)
```

The hook wraps existing API functions — it does NOT replace them. The transport
layer (`connectSSE`) stays in `lib/api/`. Domain-specific API wrappers
(`generation-streams.ts`, `chat.ts`, etc.) stay as-is. The hook provides the
React lifecycle management ON TOP of those functions.

**Pros:**
- Composable: works with any async function that accepts an `AbortSignal`
- Testable: pure hook with clear inputs/outputs, testable via `renderHook`
- Familiar: follows React conventions used throughout the codebase (30+ existing hooks)
- No new dependencies
- Zero coupling between features: each usage is independent
- Can be combined with any UI pattern (controlled components, Context, etc.)
- Existing API layer stays unchanged — no migration risk

**Cons:**
- Hook rules apply (cannot be called conditionally, must be at component top level)
- Requires consumers to call `notifyData()` for streaming state transition
- Does not enforce UI layout — components still render their own loading/error states

---

### Option B — Headless Component / Render-Prop Pattern

A `<AIOperation>` component that manages state and passes it via render prop:

```tsx
<AIOperation execute={(signal) => streamRewrite(...)}>
  {({ status, error, cancel, retry }) => (
    <div>...</div>
  )}
</AIOperation>
```

**Pros:**
- Explicit state passing via render prop
- Works with class components (not relevant — no class components exist)
- State is visible in JSX tree

**Cons:**
- Render props cause nesting (callback hell) when composed
- More verbose than hooks for the same functionality
- Modern React (and this codebase) strongly prefers hooks
- Cannot use other hooks inside render prop without wrapper component
- Does not compose with TanStack Query hooks already in use

---

### Option C — Context Provider Pattern

A global `<AIOperationProvider>` that manages all AI operations via Context.

**Pros:**
- Shared state across components
- Could coordinate between multiple concurrent AI operations

**Cons:**
- **Over-engineering**: AI operations are independent — they don't share state
- Context re-renders affect all consumers, even unrelated ones
- Requires provider wrapping at route/layout level
- Adds coupling between features that should be independent
- Does not solve the lifecycle problem — still needs per-operation state
- Breaks the "no global state for independent operations" principle

---

### Option D — State Machine Library (XState / Zustand middleware)

Use XState or Zustand with a formal state machine for AI operation lifecycle.

**Pros:**
- Formal state machine with visual debugging
- Impossible to reach invalid states

**Cons:**
- **New dependency**: Requires ADR with 3+ alternative evaluation (RULE-08)
- Learning curve for developers unfamiliar with XState
- Overkill for a 6-state lifecycle that React `useState` handles cleanly
- Adds bundle size (~15KB for XState minimal)
- Does not align with existing patterns (no state machine library in use)

---

## Decision

**We choose Option A — React Hook (`useAIOperation`).**

It is the simplest correct solution that works with the existing architecture:
- Wraps existing API functions without changing them
- Follows established React patterns in the codebase
- Zero new dependencies
- Testable and composable
- Directly enforces §16 compliance at the hook level

---

## Rationale

### Why Option A over Option B (Render Props)

Render props are an older React pattern that the codebase does not use. All 30+
existing hooks follow the custom hook pattern. Introducing render props would
create inconsistency. Hooks are more composable (can be combined with other hooks
like `useConnectionLost`, `useTranslations`) and avoid nesting.

### Why Option A over Option C (Context Provider)

AI operations are fundamentally independent. A chapter rewrite has no relationship
to a KB field suggestion. A global provider adds coupling without adding value.
If coordination between operations is needed in the future, it can be added at
the component level without changing the hook.

### Why Option A over Option D (State Machine Library)

The lifecycle has 6 states with straightforward transitions. React's `useState`
handles this naturally. Adding XState would introduce a new dependency (RULE-08
requires ADR), add bundle size, and create a learning curve for no measurable
benefit. The hook's internal implementation can use a simple reducer if the
state machine becomes more complex.

### Trade-offs Accepted

1. **`notifyData()` call required**: Components must call `notifyData()` when they
   receive the first SSE chunk to transition from `loading` to `streaming`. This
   is a small burden compared to the alternative (hook wrapping all SSE internals)
   and keeps the hook transport-agnostic.

2. **No enforced UI layout**: The hook provides state but does not dictate UI.
   This is intentional — features have different layouts (panels, inline, modals).
   §16 compliance is enforced at the state level, not the visual level.

3. **Existing `useConnectionLost` continues**: The new hook absorbs the
   `useConnectionLost` functionality. The existing hook can be deprecated after
   migration (it has only 3 consumers).

---

## Interface Contract (RULE-03)

### File: `packages/web/lib/hooks/use-ai-operation.ts`

```typescript
"use client";

/**
 * Shared AI interaction lifecycle hook.
 *
 * Encapsulates: state machine, AbortController management, error-to-i18n
 * mapping, connection-loss detection with partial output preservation, and
 * retry logic. Enforces §16 AI-Interaction Standards at the hook level.
 *
 * All AI operations MUST use this hook — no manual AbortController patterns.
 * See ADR-043.
 */

import { useCallback, useRef, useState } from "react";
import type { SSEStreamError } from "@/lib/api/streaming";

// ---------------------------------------------------------------------------
// Public Types
// ---------------------------------------------------------------------------

/** Lifecycle states for an AI operation (§16.3). */
export type AIOperationStatus =
  | "idle"
  | "loading"     // execute() called, waiting for first data
  | "streaming"   // first data received, accumulating
  | "complete"    // successfully finished
  | "error"       // failed with mapped, actionable error
  | "connection_lost"; // partial output preserved, retry available

/** Categorised error kinds for AI operations. */
export type AIErrorKind =
  | "abort"
  | "http"
  | "network"
  | "parse"
  | "stream"
  | "timeout"
  | "connection_lost";

/** Structured, i18n-ready error response (§16.5). */
export interface AIErrorResponse {
  /** Error category for programmatic handling. */
  kind: AIErrorKind;
  /** HTTP status code (for kind="http"). */
  status?: number;
  /** i18n key from studio.aiActions.* namespace. */
  i18nKey: string;
  /** Resolved user-facing message (locale-dependent). */
  userMessage: string;
  /** Whether retry is available. */
  retryable: boolean;
  /** Original error for logging. */
  cause: Error;
}

/** Immutable state snapshot for an AI operation. */
export interface AIOperationState<T> {
  /** Current lifecycle status. */
  status: AIOperationStatus;
  /** Result on successful completion. */
  result: T | null;
  /** Structured error on failure. */
  error: AIErrorResponse | null;
  /** Number of attempts (including retries). */
  attemptCount: number;
}

/** Configuration for useAIOperation. */
export interface UseAIOperationOptions<T> {
  /**
   * The async operation to execute. Receives an AbortSignal.
   *
   * Must return a Promise that resolves with the final result.
   * For streaming operations, chunk handling happens inside this function
   * via the domain-specific API (e.g., streamRewrite's onChunk callback).
   *
   * The hook does NOT wrap the SSE transport — it wraps the async operation.
   */
  execute: (signal: AbortSignal) => Promise<T>;

  /**
   * Connection-loss detection timeout in milliseconds.
   * If no notifyData() call within this window during loading/streaming,
   * transitions to "connection_lost" state. Default: 15000. Set to 0 to disable.
   */
  connectionLossTimeout?: number;

  /**
   * Maximum automatic retry attempts on connection loss.
   * Default: 0 (no auto-retry; user must click retry).
   */
  maxConnectionRetries?: number;

  /**
   * Custom error mapper. Receives the raw error and returns a structured
   * AIErrorResponse. If not provided, uses the default mapper which maps
   * SSEStreamError kinds and HTTP status codes to studio.aiActions.* i18n keys.
   */
  errorMapper?: (error: unknown) => AIErrorResponse;

  /** Called on successful completion. */
  onSuccess?: (result: T) => void;

  /** Called on failure (after all retries exhausted). */
  onError?: (error: AIErrorResponse) => void;
}

/** Return value of useAIOperation. */
export interface UseAIOperationReturn<T> {
  /** Current immutable state snapshot. */
  state: AIOperationState<T>;

  // -- Lifecycle actions --

  /**
   * Start the operation. Creates a new AbortController.
   * No-op if already in progress (loading/streaming).
   */
  start: () => void;

  /**
   * Cancel the in-progress operation. Transitions to idle.
   * No-op if not in progress.
   */
  cancel: () => void;

  /**
   * Retry the last operation. Re-invokes execute with a fresh AbortController.
   * Only valid in "error" or "connection_lost" state.
   */
  retry: () => void;

  /**
   * Reset to idle state. Clears result and error.
   * Also cancels any in-progress operation.
   */
  reset: () => void;

  /**
   * Notify the hook that streaming data has arrived.
   * Transitions "loading" → "streaming". Resets the connection-loss timer.
   *
   * MUST be called from inside the execute() callback when the first SSE
   * chunk arrives. Subsequent calls reset the connection-loss timer.
   */
  notifyData: () => void;

  // -- Convenience flags --

  /** `state.status === "idle"` */
  isIdle: boolean;
  /** `state.status === "loading"` */
  isLoading: boolean;
  /** `state.status === "streaming"` */
  isStreaming: boolean;
  /** `state.status === "complete"` */
  isComplete: boolean;
  /** `state.status === "error"` */
  isError: boolean;
  /** `state.status === "connection_lost"` */
  isConnectionLost: boolean;
}

// ---------------------------------------------------------------------------
// Hook Signature
// ---------------------------------------------------------------------------

export function useAIOperation<T>(
  options: UseAIOperationOptions<T>,
): UseAIOperationReturn<T> {
  // Implementation deferred to Frontend Specialist.
  // This interface IS the contract (RULE-03).
  throw new Error("Not implemented — contract only (ADR-043)");
}
```

### File: `packages/web/lib/api/ai-error-mapping.ts`

```typescript
/**
 * Default error mapper for AI operations.
 *
 * Maps SSEStreamError and HTTP status codes to structured, i18n-ready
 * AIErrorResponse objects using studio.aiActions.* keys (§16.5, §16.8).
 *
 * Machine-checkable: all error messages use i18n keys, never raw strings.
 */

import type { SSEStreamError } from "./streaming";
import type { AIErrorResponse, AIErrorKind } from "@/lib/hooks/use-ai-operation";

/** i18n key → default DE message (for documentation; actual text comes from i18n). */
export const AI_ERROR_MESSAGE_MAP: Record<string, { de: string; retryable: boolean }> = {
  "aiActions.errorApiKey": {
    de: "Dein API-Schlüssel ist ungültig. Überprüfe deine KI-Einstellungen.",
    retryable: false,
  },
  "aiActions.errorTextTooLong": {
    de: "Der Text ist zu lang für die KI. Kürze die Auswahl und versuche es erneut.",
    retryable: false,
  },
  "aiActions.errorRateLimit": {
    de: "Du hast zu viele Anfragen gesendet. Warte einen Moment.",
    retryable: true,
  },
  "aiActions.errorTimeout": {
    de: "Die KI braucht zu lange. Versuche es mit weniger Kontext erneut.",
    retryable: true,
  },
  "aiActions.errorConnection": {
    de: "Verbindung verloren. Prüfe deine Internetverbindung.",
    retryable: true,
  },
  "aiActions.errorParse": {
    de: "Die KI-Antwort war fehlerhaft. Versuche es erneut.",
    retryable: true,
  },
  "aiActions.errorDefault": {
    de: "Ein unerwarteter Fehler ist aufgetreten. Versuche es erneut.",
    retryable: true,
  },
};

/**
 * Map an SSEStreamError (or any error) to a structured AIErrorResponse.
 *
 * Mapping rules (§16.5):
 *   - kind="abort"       → swallowed (no error shown, returns to idle)
 *   - kind="http" + 401  → api key invalid
 *   - kind="http" + 413  → text too long
 *   - kind="http" + 429  → rate limit
 *   - kind="http" + 408  → timeout
 *   - kind="http" + 5xx  → connection/server error
 *   - kind="network"     → connection lost
 *   - kind="parse"       → parse error
 *   - kind="stream"      → stream error
 *   - kind="timeout"     → timeout (if detected by connection-loss timer)
 */
export function mapSSEError(error: unknown): AIErrorResponse | null {
  // Abort errors are swallowed — not an error state
  if (
    error instanceof DOMException && error.name === "AbortError" ||
    error instanceof Error && error.name === "AbortError"
  ) {
    return null;
  }

  if (error instanceof Error && "kind" in error) {
    const sse = error as SSEStreamError;
    return mapSSEStreamError(sse);
  }

  if (error instanceof Error) {
    return {
      kind: "network",
      i18nKey: "aiActions.errorConnection",
      userMessage: AI_ERROR_MESSAGE_MAP["aiActions.errorConnection"].de,
      retryable: true,
      cause: error,
    };
  }

  return {
    kind: "stream",
    i18nKey: "aiActions.errorDefault",
    userMessage: AI_ERROR_MESSAGE_MAP["aiActions.errorDefault"].de,
    retryable: true,
    cause: new Error(String(error)),
  };
}

function mapSSEStreamError(error: SSEStreamError): AIErrorResponse {
  if (error.kind === "abort") {
    // Should not reach here — abort is handled upstream
    return {
      kind: "abort",
      i18nKey: "aiActions.errorDefault",
      userMessage: "",
      retryable: false,
      cause: error,
    };
  }

  if (error.kind === "http") {
    return mapHTTPError(error);
  }

  if (error.kind === "network") {
    return {
      kind: "network",
      i18nKey: "aiActions.errorConnection",
      userMessage: AI_ERROR_MESSAGE_MAP["aiActions.errorConnection"].de,
      retryable: true,
      status: error.status,
      cause: error,
    };
  }

  if (error.kind === "parse") {
    return {
      kind: "parse",
      i18nKey: "aiActions.errorParse",
      userMessage: AI_ERROR_MESSAGE_MAP["aiActions.errorParse"].de,
      retryable: true,
      cause: error,
    };
  }

  // "stream" or unknown
  return {
    kind: "stream",
    i18nKey: "aiActions.errorDefault",
    userMessage: AI_ERROR_MESSAGE_MAP["aiActions.errorDefault"].de,
    retryable: true,
    cause: error,
  };
}

function mapHTTPError(error: SSEStreamError): AIErrorResponse {
  const status = error.status ?? 0;

  if (status === 401) {
    return {
      kind: "http",
      status: 401,
      i18nKey: "aiActions.errorApiKey",
      userMessage: AI_ERROR_MESSAGE_MAP["aiActions.errorApiKey"].de,
      retryable: false,
      cause: error,
    };
  }

  if (status === 413) {
    return {
      kind: "http",
      status: 413,
      i18nKey: "aiActions.errorTextTooLong",
      userMessage: AI_ERROR_MESSAGE_MAP["aiActions.errorTextTooLong"].de,
      retryable: false,
      cause: error,
    };
  }

  if (status === 429) {
    return {
      kind: "http",
      status: 429,
      i18nKey: "aiActions.errorRateLimit",
      userMessage: AI_ERROR_MESSAGE_MAP["aiActions.errorRateLimit"].de,
      retryable: true,
      cause: error,
    };
  }

  if (status === 408) {
    return {
      kind: "http",
      status: 408,
      i18nKey: "aiActions.errorTimeout",
      userMessage: AI_ERROR_MESSAGE_MAP["aiActions.errorTimeout"].de,
      retryable: true,
      cause: error,
    };
  }

  // 5xx or other
  return {
    kind: "http",
    status,
    i18nKey: "aiActions.errorConnection",
    userMessage: AI_ERROR_MESSAGE_MAP["aiActions.errorConnection"].de,
    retryable: true,
    cause: error,
  };
}
```

### Required i18n Additions

New keys for `studio.aiActions.*` namespace (§16.8, §16.5):

| i18n key | DE | EN | FR |
|----------|----|----|----|
| `aiActions.errorApiKey` | Dein API-Schlüssel ist ungültig. Überprüfe deine KI-Einstellungen. | Your API key is invalid. Check your AI settings. | Votre clé API est invalide. Vérifiez vos paramètres IA. |
| `aiActions.errorTextTooLong` | Der Text ist zu lang für die KI. Kürze die Auswahl und versuche es erneut. | The text is too long for the AI. Shorten your selection and try again. | Le texte est trop long pour l'IA. Raccourcissez votre sélection et réessayez. |
| `aiActions.errorRateLimit` | Du hast zu viele Anfragen gesendet. Warte einen Moment. | You've sent too many requests. Wait a moment. | Vous avez envoyé trop de requêtes. Attendez un moment. |
| `aiActions.errorTimeout` | Die KI braucht zu lange. Versuche es mit weniger Kontext erneut. | The AI is taking too long. Try again with less context. | L'IA prend trop de temps. Réessayez avec moins de contexte. |
| `aiActions.errorConnection` | Verbindung verloren. Prüfe deine Internetverbindung. | Connection lost. Check your internet connection. | Connexion perdue. Vérifiez votre connexion internet. |
| `aiActions.errorParse` | Die KI-Antwort war fehlerhaft. Versuche es erneut. | The AI response was malformed. Try again. | La réponse de l'IA était malformée. Réessayez. |
| `aiActions.errorDefault` | Ein unerwarteter Fehler ist aufgetreten. Versuche es erneut. | An unexpected error occurred. Try again. | Une erreur inattendue s'est produite. Réessayez. |

---

## Migration Plan

### Phase 1: Implement Primitives (Frontend Specialist)

| File | Action |
|------|--------|
| `packages/web/lib/hooks/use-ai-operation.ts` | **CREATE** — Hook implementation |
| `packages/web/lib/api/ai-error-mapping.ts` | **CREATE** — Default error mapper |
| `packages/web/messages/{en,de,fr}/studio.json` | **APPEND** — 7 new `aiActions.error*` keys |
| `packages/web/lib/hooks/__tests__/useAIOperation.test.ts` | **CREATE** — Unit tests (90%+ coverage) |
| `packages/web/lib/api/__tests__/ai-error-mapping.test.ts` | **CREATE** — Mapper unit tests |

### Phase 2: Migrate Existing Flows (Frontend Specialist, per feature)

Migration is incremental and non-breaking. Each flow is migrated independently.
Existing API functions (`streamRewrite`, `streamChat`, etc.) are NOT changed —
only the components/hooks that consume them.

**Migration pattern for callback-based SSE (generation-streams, coauthor, chat, timeline):**

```typescript
// BEFORE (manual lifecycle, inconsistent):
const abortRef = useRef<AbortController | null>(null);
const [status, setStatus] = useState<"idle" | "loading" | "streaming" | "error">("idle");
const [error, setError] = useState<string | null>(null);

const handleStart = async () => {
  const controller = new AbortController();
  abortRef.current = controller;
  setStatus("loading");
  setError(null);

  await streamRewrite(chapterId, novelId, request, {
    onChunk: (label, text) => { setStatus("streaming"); /* accumulate */ },
    onComplete: () => setStatus("complete"),
    onError: (err) => { setStatus("error"); setError(err.message); },
  }, controller.signal);
};

// AFTER (useAIOperation, §16-compliant):
const { state, start, cancel, notifyData, isStreaming, isError } = useAIOperation({
  execute: (signal) => streamRewrite(chapterId, novelId, request, {
    onChunk: (label, text) => { notifyData(); /* accumulate */ },
    onComplete: () => {},
    onError: (err) => { throw err; },
  }, signal),
});
```

**Migration pattern for Promise-based SSE (kb-sessions, suggest):**

```typescript
// BEFORE:
const abortRef = useRef<AbortController | null>(null);
const [loading, setLoading] = useState(false);

const handleSuggest = async () => {
  const controller = new AbortController();
  abortRef.current = controller;
  setLoading(true);
  try {
    const result = await suggestField(novelId, sessionId, fieldKey, controller.signal);
    // use result
  } catch (err) {
    // raw error shown
  } finally {
    setLoading(false);
  }
};

// AFTER:
const { state, start, notifyData, isError } = useAIOperation({
  execute: (signal) => suggestField(novelId, sessionId, fieldKey, signal),
});
```

### Migration Order (priority by user impact)

| # | Flow | File(s) | Type | Priority |
|---|------|---------|------|----------|
| 1 | Writing: Continue/Extend | `ContinueButton.tsx`, `useEditorGenerationActions.ts` | Callback SSE | P0 |
| 2 | Writing: Rewrite | Editor rewrite component | Callback SSE | P0 |
| 3 | Writing: Co-Author | `useCoAuthorPanel.ts`, `CoAuthorPanel.tsx` | Callback SSE | P0 |
| 4 | Writing: Generation | `GenerationPanel.tsx`, `SessionPanel.tsx` | Callback SSE | P0 |
| 5 | Chat | `useChat.ts`, `ChatPanel.tsx` | Callback SSE | P1 |
| 6 | KB: Sessions (Suggest/Interview/Enhance) | `useKBSessions.ts`, `KBInterviewView.tsx` | Promise SSE | P1 |
| 7 | Timeline: Extraction | `useTimelineExtraction.ts`, `ExtractionPanel.tsx` | Callback SSE | P1 |
| 8 | KB: Consistency Check | `useConsistency.ts`, `ConsistencyCheckPanel.tsx` | Callback SSE | P2 |
| 9 | GhostText: Inline Suggestions | `suggest.ts` (factory pattern) | Promise SSE | P2 |

### Out of Scope (separate ADRs needed)

| Flow | Reason |
|------|--------|
| Writing Session (WebSocket) | Not SSE — uses `WritingSessionSocket` class. Needs a `useAISession` hook for WebSocket lifecycle. Separate ADR. |
| Analysis (BetaReader, Worldbuilding, etc.) | Uses TanStack Query mutations, not raw SSE. May benefit from `useAIOperation` but requires investigation of mutation compatibility. |

### Phase 3: Deprecate `useConnectionLost`

After all flows are migrated:

| File | Action |
|------|--------|
| `packages/web/lib/hooks/use-connection-lost.ts` | **DEPRECATE** — Add `@deprecated See useAIOperation (ADR-043)` |
| All `useConnectionLost` consumers | **MIGRATE** to `useAIOperation` |

---

## RULE-XX Compliance

| Rule | Status | Evidence |
|------|--------|----------|
| RULE-03 | ✅ | Contract defined in this ADR before implementation. Interface signatures in `UseAIOperationOptions<T>`, `UseAIOperationReturn<T>`, `AIErrorResponse`. |
| RULE-04 | ✅ | Hook file ≤250 lines target. Error mapper in separate file. No single file exceeds limits. |
| RULE-05 | ✅ | Hook in `lib/hooks/`, error mapper in `lib/api/`. No cross-domain boundary violations. |
| RULE-06 | ✅ | `use-ai-operation.ts` = hook logic only. `ai-error-mapping.ts` = error mapping only. Single responsibility. |
| RULE-07 | ✅ | Components → hook → API functions → connectSSE. Dependencies flow one direction. |
| RULE-09 | ✅ | All public interfaces fully typed. No `any`. Generic `<T>` for result type. |
| RULE-10 | ✅ | Unit tests required for hook and mapper (90%+ coverage target). Test files specified in Phase 1. |
| RULE-11 | ✅ | Abort errors swallowed silently (by design — user cancelled). All other errors mapped to structured `AIErrorResponse` with `cause` preserved. No bare `catch: pass`. |
| RULE-16 | ✅ | All error messages use `studio.aiActions.*` i18n keys. 7 new keys registered in all 3 locales. Namespace validation passes. |
| RULE-17 | ✅ | Hook interface field names match what components expect. No field name mismatches between hook return and consumer code. |
| RULE-20 | ✅ | Complete implementation from day one: lifecycle state machine, error mapping, connection loss, retry, i18n. No "phase 2 later" — everything specified now. |

---

## Consequences

### Positive

1. **Single source of truth** for AI operation lifecycle — one hook replaces 8+ manual implementations
2. **§16 compliance by default** — any component using `useAIOperation` automatically satisfies
   §16.1–16.7 (streaming, cancel, loading, labels, errors, feedback, connection loss)
3. **Consistent error UX** — users see the same error message format across all AI features
4. **Reduced boilerplate** — 15–30 lines of AbortController + state management reduced to
   a single `useAIOperation()` call
5. **Testable in isolation** — hook and mapper both unit-testable without rendering components
6. **Machine-checkable** — automated checks can verify hook usage in AI components

### Negative / Trade-offs

1. **`notifyData()` discipline required** — Components must call `notifyData()` when first
   data arrives. Forgetting this call means the state stays in "loading" instead of
   transitioning to "streaming". **Mitigation**: The connection-loss timer still fires
   (transitioning to "connection_lost"), and the `isStreaming` flag is a convenience —
   visual loading indicators work with either state.

2. **Existing hook migration effort** — 8+ flows need migration. **Mitigation**: Each
   migration is independent and non-breaking. Can be done incrementally.

3. **`useConnectionLost` deprecation** — The existing hook has 3 consumers that need
   migration. **Mitigation**: Absorbed into Phase 3, after all flows are migrated.

4. **WebSocket flows excluded** — `WritingSessionSocket` and future WebSocket flows
   are out of scope. **Mitigation**: A separate `useAISession` hook can follow the same
   pattern in a future ADR.

---

## Machine-Checkability

The following checks CAN and SHOULD be automated:

### Check 1: `useAIOperation` usage in AI components

```bash
# Every TSX file that imports an SSE API function MUST also import useAIOperation
# (or be in the migration exclusion list)
rg "from.*streaming|from.*generation-streams|from.*coauthor|from.*chat|from.*kb-sessions|from.*timeline" --type tsx -l | \
  while read f; do
    rg "useAIOperation" "$f" || echo "MISSING: $f"
  done
```

### Check 2: No raw AbortController in AI components

```bash
# No manual AbortController patterns in AI components
# (after migration complete)
rg "new AbortController" packages/web/components/studio/ --type tsx -l
# Should return empty (or only excluded files)
```

### Check 3: Error message i18n keys exist

```bash
# All aiActions.error* keys must exist in all 3 locales
for locale in en de fr; do
  for key in errorApiKey errorTextTooLong errorRateLimit errorTimeout errorConnection errorParse errorDefault; do
    rg "aiActions\.$key" packages/web/messages/$locale/studio.json || echo "MISSING: $locale/$key"
  done
done
```

### Check 4: No hardcoded AI error messages

```bash
# No raw error.message in AI components — must use state.error.userMessage
rg "(err|error)\.message" packages/web/components/studio/ --type tsx -l
# Should return empty (or only excluded files)
```

### Check 5: Deprecated `useConnectionLost` not used (Phase 3)

```bash
rg "useConnectionLost" packages/web/ --type ts -l
# Should return empty after Phase 3 migration
```

---

## Implementation Notes

1. **The hook wraps async functions, not SSE directly.** This is a deliberate design choice.
   The hook is transport-agnostic — it works with SSE, REST, WebSocket (via adapter),
   or any async operation. The SSE specifics stay in the API layer.

2. **Connection-loss detection is timer-based.** The hook starts a timer when `start()`
   is called. Each `notifyData()` call resets the timer. If the timer fires, the state
   transitions to `connection_lost`. This works regardless of transport.

3. **Partial output preservation is the consumer's responsibility.** The hook does not
   manage accumulated text — that's domain-specific (some flows accumulate text, others
   accumulate structured objects). The hook provides `state.status` so the consumer knows
   whether to show a "partial output" banner. **The consumer must preserve partial output
   in its own state before retrying.**

4. **The `execute` function should throw to signal errors.** The hook catches thrown
   errors and maps them via `mapSSEError()`. If the API function uses callbacks for
   errors (like `streamRewrite`'s `onError`), the consumer should re-throw from the
   callback or use a wrapper that converts callbacks to Promise rejection.

5. **i18n resolution happens at render time, not in the hook.** The hook stores the
   `i18nKey` and a default `userMessage` (DE). Components should prefer using
   `useTranslations("studio")` to resolve `state.error.i18nKey` at render time for
   proper locale support. The default `userMessage` is a fallback for non-render contexts.

---

## Review Trigger

This decision should be revisited:

- [ ] When a WebSocket-based AI flow needs lifecycle management (→ new `useAISession` ADR)
- [ ] When TanStack Query integration is needed for AI operations that also need caching
- [ ] When more than 3 concurrent AI operations need coordination (→ Context/coordination layer)
- [ ] After 3 months — verify the hook has been adopted by all flows
