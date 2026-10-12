/**
 * KBTemplate contract tests — RULE-17 parity with TemplateDetailResponse.
 *
 * Audit B04: the interface previously claimed `meta` / `fields` /
 * `field_groups` / `sections`, none of which the backend route ever
 * returned. The @ts-expect-error lines are a compile-time ratchet: if any
 * of those keys reappear on the type, type-check FAILS with "unused
 * '@ts-expect-error' directive".
 *
 * @module kb-template-contract.test
 */

import { describe, expect, it } from "vitest";
import type { KBTemplate } from "@/lib/api/kb";

const realPayload = {
  entity_type: "character",
  scope: "user",
  content: "---\nprompt_type: kb\n---\n\nbody",
  base_content: null,
  schema_version: "2.0.0",
  based_on_version: null,
  is_overridden: false,
} as const satisfies KBTemplate;

describe("KBTemplate mirrors TemplateDetailResponse", () => {
  it("accepts a real payload", () => {
    expect(realPayload.entity_type).toBe("character");
    expect(realPayload.is_overridden).toBe(false);
  });

  it("no longer declares the fantasy keys (compile-time ratchet)", () => {
    const template = realPayload as KBTemplate;
    // @ts-expect-error — the backend contract has no field_groups (audit B04)
    expect(template.field_groups).toBeUndefined();
    // @ts-expect-error — the backend contract has no fields (audit B04)
    expect(template.fields).toBeUndefined();
    // @ts-expect-error — the backend contract has no sections (audit B04)
    expect(template.sections).toBeUndefined();
    // @ts-expect-error — the backend contract has no meta (audit B04)
    expect(template.meta).toBeUndefined();
  });
});
