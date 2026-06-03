/**
 * Custom Tones API.
 */

import type { CreateCustomToneRequest, CustomTone, UpdateCustomToneRequest } from "@/types";
import { fetchApi } from "./core";

export const tonesApi = {
  list: () => fetchApi<CustomTone[]>("/settings/user/tones"),

  create: (data: CreateCustomToneRequest) =>
    fetchApi<CustomTone>("/settings/user/tones", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  update: (id: string, data: UpdateCustomToneRequest) =>
    fetchApi<CustomTone>(`/settings/user/tones/${id}`, {
      method: "PUT",
      body: JSON.stringify(data),
    }),

  delete: (id: string) => fetchApi<void>(`/settings/user/tones/${id}`, { method: "DELETE" }),
};
