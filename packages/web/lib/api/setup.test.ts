/**
 * Setup Wizard API client tests — covers setupApi validation & completion.
 *
 * Focuses on endpoint/method correctness and the getProviderModels default
 * parameters and listDemos result transform.
 */

import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api/core", () => ({ fetchApi: vi.fn() }));

import { fetchApi } from "@/lib/api/core";
import { setupApi } from "@/lib/api/setup";

const f = vi.mocked(fetchApi);

beforeEach(() => vi.clearAllMocks());

describe("setupApi — validation steps", () => {
  it("validateStep1 → POST with body", async () => {
    f.mockResolvedValueOnce({ valid: true } as never);
    const data = { project_name: "P", writing_language: "en", autosave_interval: 5 };
    await setupApi.validateStep1(data);
    expect(f).toHaveBeenCalledWith("/setup/validate/step-1", {
      method: "POST",
      body: JSON.stringify(data),
    });
  });

  it("validateStep2 → POST with body", async () => {
    f.mockResolvedValueOnce({ valid: true } as never);
    const data = { title: "T" };
    await setupApi.validateStep2(data);
    expect(f).toHaveBeenCalledWith(
      "/setup/validate/step-2",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("validateStep3 → POST with body", async () => {
    f.mockResolvedValueOnce({ valid: true, starter: "blank", demo_info: null } as never);
    const data = { starter: "blank", import_path: null };
    await setupApi.validateStep3(data);
    expect(f).toHaveBeenCalledWith(
      "/setup/validate/step-3",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("validateStep4 → POST with body", async () => {
    f.mockResolvedValueOnce({ valid: true } as never);
    const data = { provider: "openai" as const, api_key: "k", model: "gpt-4" };
    await setupApi.validateStep4(data);
    expect(f).toHaveBeenCalledWith(
      "/setup/validate/step-4",
      expect.objectContaining({ method: "POST" }),
    );
  });
});

describe("setupApi — getProviderModels default parameters", () => {
  it("uses empty api_key and default ollama_url when omitted", async () => {
    f.mockResolvedValueOnce({} as never);
    await setupApi.getProviderModels("openai");
    expect(f).toHaveBeenCalledWith(
      "/setup/providers/openai/models?api_key=&ollama_url=http%3A%2F%2Flocalhost%3A11434",
    );
  });

  it("passes through custom api_key and ollama_url", async () => {
    f.mockResolvedValueOnce({} as never);
    await setupApi.getProviderModels("ollama", "secret", "http://host:1234");
    expect(f).toHaveBeenCalledWith(
      "/setup/providers/ollama/models?api_key=secret&ollama_url=http%3A%2F%2Fhost%3A1234",
    );
  });
});

describe("setupApi — complete & listDemos", () => {
  it("complete → POST state", async () => {
    f.mockResolvedValueOnce({ novel_id: "n1", redirect_to: "/x", message: "ok" } as never);
    const state = { project_name: "P" } as never;
    await setupApi.complete(state);
    expect(f).toHaveBeenCalledWith("/setup/complete", {
      method: "POST",
      body: JSON.stringify({ state }),
    });
  });

  it("listDemos unwraps the demos array", async () => {
    const demos = [{ id: "d1", title: "Demo" }] as never;
    f.mockResolvedValueOnce({ demos } as never);
    const result = await setupApi.listDemos();
    expect(f).toHaveBeenCalledWith("/setup/demos");
    expect(result).toBe(demos);
  });
});
