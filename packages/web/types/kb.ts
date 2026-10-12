// Knowledge Base Template types
//
// NOTE (audit B04): the fantasy field-schema shapes (`KBTemplate` with
// `meta`/`fields`/`field_groups`/`sections`, `KBTemplateMeta`,
// `KBTemplateField`, `KBTemplateFieldGroup`, `KBTemplateSection`) were
// deleted — the template endpoints return flat prompt-template payloads.
// The live contract types live in `lib/api/kb.ts` (`KBTemplate`) and here.

export interface KBTemplateInfo {
  entity_type: string;
  scope: string;
  schema_version: string;
  has_override: boolean;
  has_update: boolean;
}

export interface KBTemplateDetail {
  entity_type: string;
  scope: string;
  content: string;
  base_content: string | null;
  schema_version: string;
  based_on_version: string | null;
  is_overridden: boolean;
}

export interface KBTemplateUpdateInfo {
  entity_type: string;
  override_version: string | null;
  current_bundled_version: string | null;
}

export interface KBTemplateDiff {
  entity_type: string;
  override_content: string;
  bundled_content: string;
}
