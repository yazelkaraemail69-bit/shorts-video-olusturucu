export const appConfig = {
  dailyLimit: Number(process.env.DAILY_GENERATION_LIMIT ?? 5),
  unlockCost: Number(process.env.UNLOCK_CREDIT_COST ?? 1),
  initialCredits: Number(process.env.INITIAL_CREDITS ?? 10),
  mockAi: process.env.MOCK_AI === "true",
  models: {
    prompt: process.env.MODEL_PROMPT ?? "anthropic/claude-3.5-sonnet",
    logo: process.env.MODEL_LOGO ?? "black-forest-labs/flux-1.1-pro",
    image: process.env.MODEL_IMAGE ?? "openai/dall-e-3",
    socialImage:
      process.env.MODEL_SOCIAL_IMAGE ?? "black-forest-labs/flux-1.1-pro",
  },
};

export function isSupabaseConfigured(): boolean {
  return Boolean(
    process.env.NEXT_PUBLIC_SUPABASE_URL &&
      process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY,
  );
}
