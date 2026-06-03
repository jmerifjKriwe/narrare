// Knowledge Base Template types

export interface KBTemplateField {
  name: string;
  field_type: string;
  required: boolean;
  description: string;
}

export interface KBTemplateSection {
  name: string;
  label_key: string;
  description_key: string;
  order: number;
}

export interface KBTemplateFieldGroup {
  name: string;
  label_key: string;
  description_key: string;
  fields: KBTemplateField[];
  order: number;
}

export interface KBTemplateMeta {
  template_type: string;
  template_version: string;
  schema_version: string;
}

export interface KBTemplate {
  meta: KBTemplateMeta;
  fields: KBTemplateField[];
  field_groups: KBTemplateFieldGroup[];
  sections: KBTemplateSection[];
  body: string;
}

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
