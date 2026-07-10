import { appConfig } from "@/lib/config";
import { chatCompletion, generateImage } from "@/lib/openrouter";
import type { PipelineResult } from "@/lib/types";

const LOGO_SYSTEM = `You are an expert logo prompt engineer. Rewrite the user's request into a single English image-generation prompt optimized for vector-like / flat logo output.
Rules: minimal shapes, clean negative space, 2-3 colors, centered mark, white or solid background, no photorealism, no 3D mockups, no watermarks, no extra text unless the brand name is essential.
Return ONLY the prompt text.`;

export async function runLogoPipeline(
  userPrompt: string,
): Promise<PipelineResult> {
  const engineeredPrompt = await chatCompletion({
    model: appConfig.models.prompt,
    system: LOGO_SYSTEM,
    user: userPrompt,
  });

  const image = await generateImage({
    model: appConfig.models.logo,
    prompt: engineeredPrompt,
  });

  return {
    engineeredPrompt,
    caption: null,
    imageBase64: image.base64,
    mimeType: image.mimeType,
    modelUsed: `${appConfig.models.prompt} + ${appConfig.models.logo}`,
  };
}
