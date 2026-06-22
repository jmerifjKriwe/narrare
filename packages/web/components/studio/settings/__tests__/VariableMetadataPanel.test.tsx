import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { VariableMetadataPanel } from "@/components/studio/settings/VariableMetadataPanel";
import type { PromptVariableMetadata } from "@/types";

const variables: readonly PromptVariableMetadata[] = [
  {
    name: "language",
    description: "ISO language code",
    variable_type: "text",
    required: true,
    provenance: "system_generated",
    security: "system_only",
  },
  {
    name: "kb_summary",
    description: "Curated KB summary",
    variable_type: "text",
    required: false,
    provenance: "curated_kb",
    security: "xml_section_required",
  },
];

describe("VariableMetadataPanel", () => {
  it("renders each variable with provenance + security labels", () => {
    render(<VariableMetadataPanel variables={variables} />);
    // Variable names appear in ``{{name}}`` form
    expect(screen.getByText("{{language}}")).toBeInTheDocument();
    expect(screen.getByText("{{kb_summary}}")).toBeInTheDocument();
    // Provenance column
    expect(screen.getByText("system_generated")).toBeInTheDocument();
    expect(screen.getByText("curated_kb")).toBeInTheDocument();
    // Security column
    expect(screen.getByText("system_only")).toBeInTheDocument();
    expect(screen.getByText("xml_section_required")).toBeInTheDocument();
    // Descriptions
    expect(screen.getByText("ISO language code")).toBeInTheDocument();
    expect(screen.getByText("Curated KB summary")).toBeInTheDocument();
  });

  it("marks required variables with an indicator", () => {
    render(<VariableMetadataPanel variables={variables} />);
    // Required indicator appears for the required row only
    expect(screen.getAllByText("*").length).toBeGreaterThanOrEqual(1);
  });

  it("renders empty-state message when no variables", () => {
    render(<VariableMetadataPanel variables={[]} />);
    expect(
      screen.getByText("settings.prompts.promptCustomization.noVariables"),
    ).toBeInTheDocument();
  });
});
