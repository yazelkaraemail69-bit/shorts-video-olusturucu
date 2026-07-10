export type GenerationType = "logo" | "image" | "social";

export type GenerationStatus = "preview" | "unlocked" | "failed";

export interface PipelineResult {
  engineeredPrompt: string;
  caption: string | null;
  imageBase64: string;
  mimeType: string;
  modelUsed: string;
}

export interface GenerationRow {
  id: string;
  user_id: string;
  type: GenerationType;
  user_prompt: string;
  engineered_prompt: string;
  caption: string | null;
  preview_url: string | null;
  full_url: string | null;
  model_used: string | null;
  status: GenerationStatus;
  credits_spent: number;
  created_at: string;
}

export interface MeResponse {
  email: string | null;
  credits: number;
  dailyLimit: number;
  usedToday: number;
  remainingToday: number;
  unlockCost: number;
}
