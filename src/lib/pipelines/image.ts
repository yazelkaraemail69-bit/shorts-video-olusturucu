import { appConfig } from "@/lib/config";
import { chatCompletion, generateImage } from "@/lib/openrouter";
import type { PipelineResult } from "@/lib/types";

const IMAGE_SYSTEM = `You are an expert image prompt engineer. Rewrite the user's request into a single English prompt optimized for photorealistic image generation.
Rules: natural lighting, sharp detail, cinematic composition, no watermark, no UI chrome, no text overlay unless explicitly requested.
Return ONLY the prompt text.`;

export async function runImagePipeline(
  userPrompt: string,
): Promise<PipelineResult> {
  const engineeredPrompt = await chatCompletion({
    model: appConfig.models.prompt,
    system: IMAGE_SYSTEM,
    user: userPrompt,
  });

  let image;
  let modelUsed = appConfig.models.image;

  try {
    image = await generateImage({
      model: appConfig.models.image,
      prompt: engineeredPrompt,
    });
  } catch {
    modelUsed = appConfig.models.logo;
    image = await generateImage({
      model: appConfig.models.logo,
      prompt: engineeredPrompt,
    });
  }

  return {
    engineeredPrompt,
    caption: null,
    imageBase64: image.base64,
    mimeType: image.mimeType,
    modelUsed: `${appConfig.models.prompt} + ${modelUsed}`,
  };
}
