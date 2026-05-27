/**
 * useKB hook tests — TanStack Query hooks for KB templates.
 *
 * Tests useKBTemplate and useKBTemplates query hooks:
 * 1. useKBTemplate fetches template for entity type
 * 2. useKBTemplate is disabled when entityType is null
 * 3. useKBTemplates fetches all templates
 * 4. useKBTemplates is disabled when novelId is empty
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// Mock the API client module
vi.mock("@/lib/api/kb", () => ({
  kbApi: {
    getTemplate: vi.fn(),
    listTemplates: vi.fn(),
    listEntries: vi.fn(),
    getEntry: vi.fn(),
    createEntry: vi.fn(),
    updateEntry: vi.fn(),
    deleteEntry: vi.fn(),
    searchEntries: vi.fn(),
    listRelationships: vi.fn(),
    createRelationship: vi.fn(),
    deleteRelationship: vi.fn(),
    getInverseSuggestion: vi.fn(),
    resolveReferences: vi.fn(),
    autocompleteEntries: vi.fn(),
  },
}));

import { kbApi } from "@/lib/api/kb";
import { useKBTemplate, useKBTemplates } from "@/lib/hooks/useKB";

// ---------------------------------------------------------------------------
// Mock helpers
// ---------------------------------------------------------------------------

const mockGetTemplate = kbApi.getTemplate as ReturnType<typeof vi.fn>;
const mockListTemplates = kbApi.listTemplates as ReturnType<typeof vi.fn>;

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const mockTemplate = {
  meta: { template_type: "character", template_version: "1.0", schema_version: "1.0" },
  fields: [{ name: "name", field_type: "text", required: true, description: "Character name" }],
  field_groups: [],
  sections: [],
  body: "# Character",
};

const mockTemplateInfoList = [
  {
    entity_type: "character",
    scope: "global",
    schema_version: "1.0",
    has_override: false,
    has_update: false,
  },
  {
    entity_type: "location",
    scope: "global",
    schema_version: "1.0",
    has_override: false,
    has_update: false,
  },
];

// ---------------------------------------------------------------------------
// Test wrapper
// ---------------------------------------------------------------------------

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
      mutations: { retry: false },
    },
  });
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("useKBTemplate", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it("fetches template for given entity type", async () => {
    mockGetTemplate.mockResolvedValueOnce(mockTemplate);

    const { result } = renderHook(() => useKBTemplate("novel-1", "character"), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(mockGetTemplate).toHaveBeenCalledWith("novel-1", "character");
    expect(result.current.data?.meta.template_type).toBe("character");
    expect(result.current.data?.fields).toHaveLength(1);
  });

  it("is disabled when entityType is null", () => {
    const { result } = renderHook(() => useKBTemplate("novel-1", null), {
      wrapper: createWrapper(),
    });

    expect(result.current.fetchStatus).toBe("idle");
    expect(mockGetTemplate).not.toHaveBeenCalled();
  });

  it("handles API errors", async () => {
    mockGetTemplate.mockRejectedValueOnce(new Error("Template not found"));

    const { result } = renderHook(() => useKBTemplate("novel-1", "missing"), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });

    expect(result.current.error?.message).toBe("Template not found");
  });
});

describe("useKBTemplates", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it("fetches all templates for a novel", async () => {
    mockListTemplates.mockResolvedValueOnce(mockTemplateInfoList);

    const { result } = renderHook(() => useKBTemplates("novel-1"), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(mockListTemplates).toHaveBeenCalledWith("novel-1");
    expect(result.current.data).toHaveLength(2);
    expect(result.current.data?.[0].entity_type).toBe("character");
    expect(result.current.data?.[1].entity_type).toBe("location");
  });

  it("is disabled when novelId is empty", () => {
    const { result } = renderHook(() => useKBTemplates(""), {
      wrapper: createWrapper(),
    });

    expect(result.current.fetchStatus).toBe("idle");
    expect(mockListTemplates).not.toHaveBeenCalled();
  });

  it("handles API errors", async () => {
    mockListTemplates.mockRejectedValueOnce(new Error("Server error"));

    const { result } = renderHook(() => useKBTemplates("novel-1"), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });

    expect(result.current.error?.message).toBe("Server error");
  });
});
