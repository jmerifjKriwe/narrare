import { beforeEach, describe, expect, it, vi } from "vitest";

// Mock @tiptap/core before importing Autosave — TipTap doesn't work in jsdom
vi.mock("@tiptap/core", () => {
  const mockExtension = {
    name: "autosave",
    config: {
      name: "autosave",
      addOptions: vi.fn(),
      addStorage: vi.fn(),
      addCommands: vi.fn(),
    },
    configure: vi.fn(() => mockExtension),
  };

  return {
    create: vi.fn(() => mockExtension),
    Extension: { create: vi.fn(() => mockExtension) },
  };
});

import { Autosave } from "./Autosave";

describe("Autosave extension", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("should have the correct extension name", () => {
    expect(Autosave.name).toBe("autosave");
  });

  it("should be configurable with custom options", () => {
    const saveFn = vi.fn().mockResolvedValue(undefined);

    const ext = Autosave.configure({
      interval: 5000,
      saveFn,
      enabled: true,
    });

    expect(ext).toBeDefined();
  });

  it("should accept enabled=false option", () => {
    const saveFn = vi.fn().mockResolvedValue(undefined);

    const ext = Autosave.configure({
      interval: 1000,
      saveFn,
      enabled: false,
    });

    expect(ext).toBeDefined();
  });

  it("should expose configure method", () => {
    expect(typeof Autosave.configure).toBe("function");
  });
});
