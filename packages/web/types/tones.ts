// Custom Tone types

export interface CustomTone {
  id: string;
  name: string;
  instructions: string;
}

export interface CreateCustomToneRequest {
  name: string;
  instructions: string;
}

export interface UpdateCustomToneRequest {
  name?: string;
  instructions?: string;
}
