import { appConfig } from "@/lib/config";
import { chatCompletion, generateImage } from "@/lib/openrouter";
import type { PipelineResult } from "@/lib/types";

const SOCIAL_SYSTEM = `You are a social media creative director for Instagram.
Given the user's brief, return STRICT JSON with keys:
- "caption": Turkish Instagram caption (1-3 short sentences, optional hashtags)
- "imagePrompt": English image-generation prompt for a square Instagram post visual
No markdown, no extra keys.`;

export async function runSocialPipeline(
  userPrompt: string,
): Promise<PipelineResult> {
  const raw = await chatCompletion({
    model: appConfig.models.prompt,
    system: SOCIAL_SYSTEM,
    user: userPrompt,
  });

  const parsed = parseSocialJson(raw, userPrompt);

  const image = await generateImage({
    model: appConfig.models.socialImage,
    prompt: parsed.imagePrompt,
  });

  return {
    engineeredPrompt: parsed.imagePrompt,
    caption: parsed.caption,
    imageBase64: image.base64,
    mimeType: image.mimeType,
    modelUsed: `${appConfig.models.prompt} + ${appConfig.models.socialImage}`,
  };
}

function parseSocialJson(
  raw: string,
  fallbackUser: string,
): { caption: string; imagePrompt: string } {
  try {
    const cleaned = raw.replace(/^```json\s*|\s*```$/g, "").trim();
    const data = JSON.parse(cleaned) as {
      caption?: string;
      imagePrompt?: string;
    };
    if (data.caption && data.imagePrompt) {
      return { caption: data.caption, imagePrompt: data.imagePrompt };
    }
  } catch {
    // fall through
  }

  return {
    caption: fallbackUser,
    imagePrompt: `Instagram post visual for: ${fallbackUser}. Square 1:1, modern brand aesthetic.`,
  };
}
