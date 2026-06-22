"use client";

/**
 * usePromptLiveTest — SSE-backed live-test AI operation.
 *
 * Wraps :func:`streamPromptLiveTest` with :func:`useAIOperation` so the
 * dialog gets the §16 lifecycle for free (cancel/retry/connection-lost,
 * structured error mapping via :func:`mapSSEError`).
 *
 * Extracted from ``usePromptEditorState`` for RULE-04 (each hook ≤150 lines).
 *
 * The hook owns:
 *   - ``acknowledged`` flag (warning-gate confirmation).
 *   - ``output`` accumulator (streamed text).
 *   - ``streaming`` / ``error`` flags from :func:`useAIOperation`.
 *   - ``handleConfirm`` / ``handleCancel`` handlers.
 *   - Reset of transient state when the host dialog closes.
 */

import { useCallback, useState } from "react";
import { streamPromptLiveTest } from "@/lib/api/client";
import { useAIOperation } from "@/lib/hooks/use-ai-operation";
import { buildSystemVariables } from "./promptVariables";

interface UsePromptLiveTestParams {
  readonly promptId: string;
  readonly language: "en" | "de" | "fr";
  /** Optional edited prompt body to override the stored template. */
  readonly editedOverride: string | null;
}

export interface UsePromptLiveTestReturn {
  readonly acknowledged: boolean;
  readonly output: string;
  readonly streaming: boolean;
  readonly error: string | null;
  readonly handleConfirm: () => void;
  readonly handleCancel: () => void;
  /** Reset transient state — call when the host dialog closes. */
  readonly reset: () => void;
}

export function usePromptLiveTest({
  promptId,
  language,
  editedOverride,
}: UsePromptLiveTestParams): UsePromptLiveTestReturn {
  const [acknowledged, setAcknowledged] = useState(false);
  const [output, setOutput] = useState("");
  const [errorKey, setErrorKey] = useState<string | null>(null);

  const liveTestOp = useAIOperation<void>({
    execute: async (signal) => {
      setOutput("");
      setErrorKey(null);
      await streamPromptLiveTest(
        promptId,
        {
          variables: buildSystemVariables(promptId, language),
          language,
          edited_override: editedOverride ?? undefined,
          user_prompt: "",
          acknowledge_token_cost: true,
        },
        {
          onChunk: (chunk) => {
            liveTestOp.notifyData();
            setOutput((prev) => prev + chunk);
          },
          onError: (e) => {
            setErrorKey(
              e.kind === "http" && e.status === 403 ? "no_active_provider" : "live_test_failed",
            );
            throw e;
          },
        },
        signal,
      );
    },
    connectionLossTimeout: 15_000,
  });

  const handleConfirm = useCallback(() => {
    setAcknowledged(true);
    liveTestOp.start();
  }, [liveTestOp]);

  const handleCancel = useCallback(() => {
    liveTestOp.cancel();
  }, [liveTestOp]);

  const reset = useCallback(() => {
    liveTestOp.cancel();
    setAcknowledged(false);
    setOutput("");
    setErrorKey(null);
  }, [liveTestOp]);

  return {
    acknowledged,
    output,
    streaming: liveTestOp.isStreaming || liveTestOp.isLoading,
    error: errorKey,
    handleConfirm,
    handleCancel,
    reset,
  };
}
