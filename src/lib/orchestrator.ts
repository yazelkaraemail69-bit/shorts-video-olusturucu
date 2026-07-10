import { AppError } from "@/lib/errors";
import { runImagePipeline } from "@/lib/pipelines/image";
import { runLogoPipeline } from "@/lib/pipelines/logo";
import { runSocialPipeline } from "@/lib/pipelines/social";
import type { GenerationType, PipelineResult } from "@/lib/types";

export async function runOrchestrator(
  type: GenerationType,
  userPrompt: string,
): Promise<PipelineResult> {
  const trimmed = userPrompt.trim();
  if (trimmed.length < 3) {
    throw new AppError("Lütfen en az birkaç kelimelik bir istek yazın.", 400);
  }
  if (trimmed.length > 2000) {
    throw new AppError("İstek metni çok uzun (maks. 2000 karakter).", 400);
  }

  switch (type) {
    case "logo":
      return runLogoPipeline(trimmed);
    case "image":
      return runImagePipeline(trimmed);
    case "social":
      return runSocialPipeline(trimmed);
    default:
      throw new AppError("Geçersiz üretim tipi.", 400);
  }
}
