/**
 * Shared fixtures and helpers for KBSessionFieldList tests.
 */

import { vi } from "vitest";
import type { KBCreationField, KBCreationSession } from "@/lib/api/kb-sessions";

export const emptyFields: KBCreationField[] = [
  {
    field_key: "name",
    label: "Name",
    field_type: "text",
    required: true,
    source: "user",
    user_value: undefined,
    ai_suggested_value: undefined,
    ai_reasoning: undefined,
    final_value: undefined,
  },
  {
    field_key: "description",
    label: "Description",
    field_type: "text",
    required: false,
    source: "user",
    user_value: undefined,
    ai_suggested_value: undefined,
    ai_reasoning: undefined,
    final_value: undefined,
  },
];

export const mixedFields: KBCreationField[] = [
  {
    field_key: "name",
    label: "Name",
    field_type: "text",
    required: true,
    source: "user",
    user_value: "Anna Schmidt",
    ai_suggested_value: undefined,
    ai_reasoning: undefined,
    final_value: "Anna Schmidt",
  },
  {
    field_key: "description",
    label: "Description",
    field_type: "text",
    required: false,
    source: "user",
    user_value: undefined,
    ai_suggested_value: undefined,
    ai_reasoning: undefined,
    final_value: undefined,
  },
  {
    field_key: "background",
    label: "Background",
    field_type: "text",
    required: false,
    source: "ai",
    user_value: undefined,
    ai_suggested_value: "A historian from a small town.",
    ai_reasoning: "Common background archetype.",
    final_value: undefined,
  },
  {
    field_key: "affiliation",
    label: "Affiliation",
    field_type: "text",
    required: false,
    source: "world_derived",
    user_value: "University of Berlin",
    ai_suggested_value: undefined,
    ai_reasoning: undefined,
    final_value: "University of Berlin",
  },
];

export const mockSession: KBCreationSession = {
  id: "session-1",
  novel_id: "novel-1",
  user_id: "user-1",
  entity_type: "character",
  status: "active",
  fields: mixedFields,
  context_entries: [],
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

export const emptySession: KBCreationSession = {
  ...mockSession,
  fields: emptyFields,
};

export const defaultProps = {
  session: mockSession,
  onSuggest: vi.fn(),
  onAnswer: vi.fn(),
  onAcceptSuggestion: vi.fn(),
  onRejectSuggestion: vi.fn(),
  onStartInterview: vi.fn(),
  onEnhance: vi.fn(),
};
