/**
 * KBEntryDetail graceful-render tests — audit B04 regression.
 *
 * `GET /novels/{id}/kb/templates/{type}` returns `TemplateDetailResponse`
 * (no `field_groups`); the detail view read `template.field_groups.length`
 * and crashed into the error boundary on EVERY entity. After the fix the
 * view renders metadata + flat body editor for the real contract shape.
 *
 * @module KBEntryDetail.graceful.test
 */

import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { KBEntry, KBRelationship } from "@/lib/api/kb";
import { KBEntryDetail } from "../KBEntryDetail";

vi.mock("next-intl", () => ({
  useTranslations: () => (key: string) => key,
}));

vi.mock("@/lib/hooks/useKB", () => ({
  useKBTemplate: () => ({
    // Real TemplateDetailResponse shape — NO field_groups/fields/sections/meta.
    data: {
      entity_type: "character",
      scope: "user",
      content: "---\nprompt_type: kb\n---\n\nbody",
      base_content: null,
      schema_version: "2.0.0",
      based_on_version: null,
      is_overridden: false,
    },
    isLoading: false,
  }),
  useUpdateKBEntry: () => ({ mutate: vi.fn(), isPending: false, isError: false }),
  useDeleteKBEntry: () => ({ mutate: vi.fn(), isPending: false, isError: false }),
}));

vi.mock("../KBEntryHeader", () => ({ KBEntryHeader: () => <div data-testid="kb-entry-header" /> }));
vi.mock("../KBMetadataBar", () => ({ KBMetadataBar: () => <div data-testid="kb-metadata-bar" /> }));
vi.mock("../KBRelationshipSection", () => ({
  KBRelationshipSection: () => <div data-testid="kb-relationships" />,
}));
vi.mock("../KBEntryAISections", () => ({
  KBEntryAISections: () => <div data-testid="kb-ai-sections" />,
}));
vi.mock("@/components/kb/ScopeToggle", () => ({ ScopeToggle: () => null }));
vi.mock("@/components/ui/confirm-dialog", () => ({ ConfirmDialog: () => null }));

const entry = {
  id: "entry-1",
  entity_type: "character",
  name: "Alice",
  status: "draft",
  tags: ["hero"],
  metadata: { origin: "Chapter 1" },
  body: "A brave hero who fears rivers.",
} as unknown as KBEntry;

describe("KBEntryDetail with the real template contract", () => {
  it("renders without crashing and shows the flat body editor", () => {
    render(
      <KBEntryDetail
        novelId="novel-1"
        entry={entry}
        relationships={[] as unknown as KBRelationship[]}
        onDeleted={vi.fn()}
      />,
    );

    expect(screen.getByTestId("kb-entry-header")).toBeInTheDocument();
    expect(screen.getByLabelText("kb.body")).toBeInTheDocument();
    expect(screen.getByDisplayValue("A brave hero who fears rivers.")).toBeInTheDocument();
    expect(screen.getByText("Origin:")).toBeInTheDocument(); // metadata fallback display
  });
});
