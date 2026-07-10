/**
 * settings API client tests — covers settingsApi, aiSettingsApi, tokenLimitsApi.
 *
 * Focuses on URL/method/body correctness and the buildTokenLimitsPath branches.
 */

import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api/core", () => ({ fetchApi: vi.fn() }));

import { fetchApi } from "@/lib/api/core";
import { aiSettingsApi, settingsApi, tokenLimitsApi } from "@/lib/api/settings";

const f = vi.mocked(fetchApi);

beforeEach(() => vi.clearAllMocks());

describe("settingsApi", () => {
  it("getUser → GET /settings/user", async () => {
    f.mockResolvedValueOnce({} as never);
    await settingsApi.getUser();
    expect(f).toHaveBeenCalledWith("/settings/user");
  });

  it("updateUser → PATCH with body", async () => {
    f.mockResolvedValueOnce({} as never);
    const payload = { theme: "dark" } as never;
    await settingsApi.updateUser(payload);
    expect(f).toHaveBeenCalledWith("/settings/user", {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  });

  it("getProject → GET novel settings", async () => {
    f.mockResolvedValueOnce({} as never);
    await settingsApi.getProject("n1");
    expect(f).toHaveBeenCalledWith("/settings/novels/n1");
  });

  it("updateProject → PATCH novel settings", async () => {
    f.mockResolvedValueOnce({} as never);
    await settingsApi.updateProject("n1", { autosave_interval: 30 } as never);
    expect(f).toHaveBeenCalledWith(
      "/settings/novels/n1",
      expect.objectContaining({ method: "PATCH" }),
    );
  });
});

describe("aiSettingsApi", () => {
  it("CRUDs providers and AI settings with correct verbs", async () => {
    f.mockResolvedValue({} as never);

    await aiSettingsApi.listProviders();
    expect(f).toHaveBeenLastCalledWith("/settings/ai/providers");

    await aiSettingsApi.createProvider({} as never);
    expect(f).toHaveBeenLastCalledWith(
      "/settings/ai/providers",
      expect.objectContaining({ method: "POST" }),
    );

    await aiSettingsApi.updateProvider("p1", {} as never);
    expect(f).toHaveBeenLastCalledWith(
      "/settings/ai/providers/p1",
      expect.objectContaining({ method: "PATCH" }),
    );

    await aiSettingsApi.deleteProvider("p1");
    expect(f).toHaveBeenLastCalledWith(
      "/settings/ai/providers/p1",
      expect.objectContaining({ method: "DELETE" }),
    );

    await aiSettingsApi.getUserSettings();
    expect(f).toHaveBeenLastCalledWith("/settings/ai");

    await aiSettingsApi.refreshModels();
    expect(f).toHaveBeenLastCalledWith(
      "/settings/models/refresh",
      expect.objectContaining({ method: "POST" }),
    );

    await aiSettingsApi.getProviderModels("p1");
    expect(f).toHaveBeenLastCalledWith("/settings/ai/providers/p1/models");

    await aiSettingsApi.getProjectSettings("n1");
    expect(f).toHaveBeenLastCalledWith("/settings/ai/novels/n1");
  });
});

describe("tokenLimitsApi.getResolved — buildTokenLimitsPath branches", () => {
  it("uses the bare path when no query is given", async () => {
    f.mockResolvedValueOnce({} as never);
    await tokenLimitsApi.getResolved();
    expect(f).toHaveBeenCalledWith("/settings/token-limits/");
  });

  it("appends provider only", async () => {
    f.mockResolvedValueOnce({} as never);
    await tokenLimitsApi.getResolved({ provider: "openai" });
    expect(f).toHaveBeenCalledWith("/settings/token-limits/?provider=openai");
  });

  it("appends provider + model_id", async () => {
    f.mockResolvedValueOnce({} as never);
    await tokenLimitsApi.getResolved({ provider: "openai", modelId: "gpt-4" });
    expect(f).toHaveBeenCalledWith("/settings/token-limits/?provider=openai&model_id=gpt-4");
  });

  it("appends provider + model_id + intent", async () => {
    f.mockResolvedValueOnce({} as never);
    await tokenLimitsApi.getResolved({ provider: "openai", modelId: "gpt-4", intent: "default" });
    expect(f).toHaveBeenCalledWith(
      "/settings/token-limits/?provider=openai&model_id=gpt-4&intent=default",
    );
  });
});

describe("tokenLimitsApi mutations", () => {
  it("updateUser → PUT user limits", async () => {
    f.mockResolvedValueOnce(undefined as never);
    await tokenLimitsApi.updateUser({} as never);
    expect(f).toHaveBeenCalledWith(
      "/settings/token-limits/user",
      expect.objectContaining({ method: "PUT" }),
    );
  });

  it("updateProject → PUT project limits", async () => {
    f.mockResolvedValueOnce(undefined as never);
    await tokenLimitsApi.updateProject("p1", {} as never);
    expect(f).toHaveBeenCalledWith(
      "/settings/token-limits/project/p1",
      expect.objectContaining({ method: "PUT" }),
    );
  });
});
