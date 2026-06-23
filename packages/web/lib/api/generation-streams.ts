/**
 * Shared SSE-backed generation stream wrappers.
 *
 * The transport/parser lives in streaming.ts; this module keeps only
 * writing-feature-specific accumulation and callback semantics.
 */

import type { TokenUsage } from "@/types";
import { connectSSE, type SSEStreamError } from "./streaming";

export interface GenerationChunk {
  text: string;
  is_final?: boolean;
  usage?: TokenUsage;
}

/** Context metadata sent as first SSE event (CR-07 Context Inspector). */
export interface ContextMeta {
  type: "context_meta";
  kb_characters_count: number;
  kb_locations_count: number;
  kb_factions_count: number;
  kb_suggested_count: number;
  kb_pinned_count: number;
  recent_chapter_count: number;
  character_names: string[];
  location_names: string[];
  faction_names: string[];
  is_first_chapter: boolean;
  has_user_preferences: boolean;
  tone: string;
  total_budget_tokens: number;
}

export type RewriteMode = "tone" | "style" | "voice" | "fix" | "custom";

export interface RewriteRequest {
  selection_text: string;
  context_before?: string;
  context_after?: string;
  mode: RewriteMode;
  options?: Record<string, string>;
  character_id?: string;
  custom_instructions?: string;
  count?: number;
  tone?: string;
  language?: string;
}

export interface RewriteAlternative {
  label: string;
  text: string;
}

export interface RewriteConfig {
  mode: RewriteMode;
  option: string;
  count: number;
  customInstructions?: string;
}

// ---------------------------------------------------------------------------
// Style variants (CR-AUFG-07-22)
// ---------------------------------------------------------------------------

export type StyleVariant =
  | "leaner"
  | "more_lyrical"
  | "more_tense"
  | "more_intimate"
  | "more_dialogue"
  | "more_sensory";

export interface StyleVariantRegenerateRequest {
  // RULE-17 contract parity: mirrors the Python `StyleVariantRegenerateRequest`
  // in apps/api/narrare/writing/schemas_style_variants.py exactly (field names,
  // optionality). Backend is the SSOT.
  source_text: string;
  context_before?: string;
  context_after?: string;
  style_variant: StyleVariant;
  tone?: string;
  language?: string;
}

export type ExtendLength = "short" | "medium" | "long";

export interface ExtendRequest {
  text_before: string;
  text_after?: string | null;
  length?: ExtendLength;
  tone?: string;
  language?: string;
}

export interface ExtendStreamEvent {
  type?: "request_info" | "text" | "done";
  request_id?: string;
  text?: string;
  is_final?: boolean;
  usage?: TokenUsage;
}

/**
 * Client-side state machine parser for `<alternative label="...">` tags.
 */
export function parseAlternatives(fullText: string): RewriteAlternative[] {
  const alternatives: RewriteAlternative[] = [];
  const openTagRegex = /^<alternative\s+label="([^"]*)">/;
  const closeTag = "</alternative>";

  let i = 0;
  let inAlternative = false;
  let currentLabel = "";
  let currentTextStart = 0;

  while (i < fullText.length) {
    if (!inAlternative) {
      const remaining = fullText.slice(i);
      const match = openTagRegex.exec(remaining);

      if (
        match &&
        (i === 0 || fullText[i - 1] === "\n" || fullText.slice(i - closeTag.length, i) === closeTag)
      ) {
        currentLabel = match[1];
        i += match[0].length;
        currentTextStart = i;
        inAlternative = true;
        continue;
      }
      i++;
      continue;
    }

    const closeIdx = fullText.indexOf(closeTag, i);
    if (closeIdx === -1) break;

    alternatives.push({ label: currentLabel, text: fullText.slice(currentTextStart, closeIdx) });
    i = closeIdx + closeTag.length;
    inAlternative = false;
  }

  if (alternatives.length === 0 && fullText.trim().length > 0) {
    alternatives.push({ label: "Rewritten text", text: fullText.trim() });
  }

  return alternatives;
}

interface StreamCallbacks {
  onError?: (error: Error) => void;
}

function reportStreamError(callbacks: StreamCallbacks, error: SSEStreamError): void {
  callbacks.onError?.(error);
}

export async function streamRewrite(
  chapterId: string,
  novelId: string,
  request: RewriteRequest,
  callbacks: {
    onRequestInfo?: (requestId: string) => void;
    onAlternative: (label: string, text: string) => void;
    onAlternativeFinal?: (count: number) => void;
    onError?: (error: Error) => void;
  },
  signal?: AbortSignal,
): Promise<void> {
  let pendingText = "";
  let emittedCount = 0;
  let isComplete = false;
  const closeTag = "</alternative>";

  function emitCompleteAlternatives(): void {
    while (pendingText.includes(closeTag)) {
      const closeIdx = pendingText.indexOf(closeTag);
      const completeText = pendingText.slice(0, closeIdx + closeTag.length);
      for (const alternative of parseAlternatives(completeText)) {
        callbacks.onAlternative(alternative.label, alternative.text);
        emittedCount++;
      }
      pendingText = pendingText.slice(closeIdx + closeTag.length);
    }
  }

  function complete(): void {
    if (isComplete) return;
    isComplete = true;
    for (const alternative of parseAlternatives(pendingText)) {
      callbacks.onAlternative(alternative.label, alternative.text);
      emittedCount++;
    }
    pendingText = "";
    callbacks.onAlternativeFinal?.(emittedCount);
  }

  await connectSSE<ExtendStreamEvent>({
    url: `/writing/chapters/${chapterId}/rewrite?novel_id=${novelId}`,
    method: "POST",
    body: request,
    signal,
    onChunk: (event) => {
      if (event.type === "request_info" && event.request_id) {
        callbacks.onRequestInfo?.(event.request_id);
        return;
      }
      if (event.text) {
        pendingText += event.text;
        emitCompleteAlternatives();
      }
      if (event.is_final) complete();
    },
    onComplete: complete,
    onError: (error) => reportStreamError(callbacks, error),
  });
}

/**
 * Stream a style-variant regeneration of an existing AI output (CR-AUFG-07-22).
 *
 * POSTs to the dedicated SSE endpoint and parses `<alternative>` tags,
 * mirroring {@link streamRewrite}. The `source_text` is the existing output;
 * `style_variant` is the creative direction. Model/provider settings resolve
 * through the existing cascade — this never changes providers.
 */
export async function streamStyleVariantRegeneration(
  chapterId: string,
  novelId: string,
  request: StyleVariantRegenerateRequest,
  callbacks: {
    onRequestInfo?: (requestId: string) => void;
    onAlternative: (label: string, text: string) => void;
    onAlternativeFinal?: (count: number) => void;
    onError?: (error: Error) => void;
  },
  signal?: AbortSignal,
): Promise<void> {
  let pendingText = "";
  let emittedCount = 0;
  let isComplete = false;
  const closeTag = "</alternative>";

  function emitCompleteAlternatives(): void {
    while (pendingText.includes(closeTag)) {
      const closeIdx = pendingText.indexOf(closeTag);
      const completeText = pendingText.slice(0, closeIdx + closeTag.length);
      for (const alternative of parseAlternatives(completeText)) {
        callbacks.onAlternative(alternative.label, alternative.text);
        emittedCount++;
      }
      pendingText = pendingText.slice(closeIdx + closeTag.length);
    }
  }

  function complete(): void {
    if (isComplete) return;
    isComplete = true;
    for (const alternative of parseAlternatives(pendingText)) {
      callbacks.onAlternative(alternative.label, alternative.text);
      emittedCount++;
    }
    pendingText = "";
    callbacks.onAlternativeFinal?.(emittedCount);
  }

  await connectSSE<ExtendStreamEvent>({
    url: `/writing/chapters/${chapterId}/style-variants/regenerate?novel_id=${novelId}`,
    method: "POST",
    body: request,
    signal,
    onChunk: (event) => {
      if (event.type === "request_info" && event.request_id) {
        callbacks.onRequestInfo?.(event.request_id);
        return;
      }
      if (event.text) {
        pendingText += event.text;
        emitCompleteAlternatives();
      }
      if (event.is_final) complete();
    },
    onComplete: complete,
    onError: (error) => reportStreamError(callbacks, error),
  });
}

export async function streamExtend(
  chapterId: string,
  novelId: string,
  request: ExtendRequest,
  callbacks: {
    onRequestInfo?: (requestId: string) => void;
    onChunk: (text: string) => void;
    onComplete?: () => void;
    onError?: (error: Error) => void;
  },
  signal?: AbortSignal,
): Promise<void> {
  let isComplete = false;

  function complete(): void {
    if (isComplete) return;
    isComplete = true;
    callbacks.onComplete?.();
  }

  await connectSSE<ExtendStreamEvent>({
    url: `/writing/chapters/${chapterId}/extend?novel_id=${novelId}`,
    method: "POST",
    body: request,
    signal,
    onChunk: (event) => {
      if (event.type === "request_info" && event.request_id) {
        callbacks.onRequestInfo?.(event.request_id);
        return;
      }
      if (event.text) callbacks.onChunk(event.text);
      if (event.is_final) complete();
    },
    onComplete: complete,
    onError: (error) => reportStreamError(callbacks, error),
  });
}

/** Type guard: narrows a stream event to ContextMeta. */
function isContextMeta(event: GenerationChunk | ContextMeta): event is ContextMeta {
  return "type" in event && event.type === "context_meta";
}

export async function streamGeneration(
  requestId: string,
  onChunk: (chunk: GenerationChunk) => void,
  onComplete?: () => void,
  onError?: (error: Error) => void,
  signal?: AbortSignal,
  onUsage?: (usage: TokenUsage) => void,
  onContextMeta?: (meta: ContextMeta) => void,
): Promise<void> {
  await connectSSE<GenerationChunk | ContextMeta>({
    url: `/writing/generation/${requestId}/stream`,
    method: "GET",
    signal,
    onChunk: (event) => {
      if (isContextMeta(event)) {
        onContextMeta?.(event);
        return;
      }
      if (event.is_final && event.usage) onUsage?.(event.usage);
      onChunk(event);
    },
    onComplete: () => onComplete?.(),
    onError: (error) => onError?.(error),
  });
}
