// Name Generation types & Save status

// Save status for editor
export type SaveStatus = "idle" | "saving" | "saved" | "error";

// ---------------------------------------------------------------------------
// Name Generation types
// ---------------------------------------------------------------------------

export type NameType = "character" | "place" | "organization" | "item";
export type Gender = "male" | "female" | "neutral" | "any";

export interface NameGenerateRequest {
  project_id: string;
  name_type: NameType;
  name_style: string;
  count: number;
  gender: Gender;
  explanation_language: string;
}

export interface GeneratedName {
  name: string;
  pronunciation: string | null;
  meaning: string | null;
  type: string;
  name_style: string;
  is_duplicate: boolean;
  confidence: number;
}

export interface NameGenerateResponse {
  names: GeneratedName[];
  count: number;
  name_style: string;
  name_type: string;
}
