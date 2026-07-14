import { z } from "zod";
import { appConfig, isSupabaseConfigured } from "@/lib/config";
import { AppError, toErrorResponse } from "@/lib/errors";
import { makePreviewAndFull } from "@/lib/image/preview";
import { runOrchestrator } from "@/lib/orchestrator";
import { assertAndIncrementDailyQuota } from "@/lib/quota";
import { createAdminClient } from "@/lib/supabase/admin";
import { createClient } from "@/lib/supabase/server";
import { assertRateLimit } from "@/lib/rate-limit";
import { uploadGenerationAssets } from "@/lib/storage";

export const maxDuration = 60;

const bodySchema = z.object({
  type: z.enum(["logo", "image", "social"]),
  prompt: z.string().min(3).max(2000),
});

export async function POST(request: Request) {
  try {
    if (!isSupabaseConfigured()) {
      throw new AppError(
        "Supabase yapılandırılmamış. .env.local dosyasını doldurun.",
        503,
        "NO_SUPABASE",
      );
    }

    const supabase = await createClient();
    const {
      data: { user },
    } = await supabase.auth.getUser();

    if (!user) {
      throw new AppError(
        "Üretim için giriş yapmalısınız.",
        401,
        "UNAUTHORIZED",
      );
    }

    const ip =
      request.headers.get("x-forwarded-for")?.split(",")[0]?.trim() ??
      "unknown";
    assertRateLimit({
      key: `generate:${user.id}:${ip}`,
      limit: 10,
      windowMs: 60_000,
    });

    const json = await request.json();
    const parsed = bodySchema.safeParse(json);
    if (!parsed.success) {
      throw new AppError("Geçersiz istek. Tip ve metin kontrol edin.", 400);
    }

    const { type, prompt } = parsed.data;

    await assertAndIncrementDailyQuota(user.id);

    const result = await runOrchestrator(type, prompt);
    const assets = await makePreviewAndFull({
      base64: result.imageBase64,
      mimeType: result.mimeType,
    });

    const admin = createAdminClient();
    const generationId = crypto.randomUUID();

    const uploaded = await uploadGenerationAssets({
      userId: user.id,
      generationId,
      preview: assets.preview,
      full: assets.full,
      previewContentType: assets.previewContentType,
      fullContentType: assets.fullContentType,
    });

    const { data: row, error } = await admin
      .from("generations")
      .insert({
        id: generationId,
        user_id: user.id,
        type,
        user_prompt: prompt,
        engineered_prompt: result.engineeredPrompt,
        caption: result.caption,
        preview_url: uploaded.previewUrl,
        full_url: uploaded.fullPath,
        model_used: result.modelUsed,
        status: "preview",
        credits_spent: 0,
      })
      .select("*")
      .single();

    if (error || !row) {
      console.error(error);
      throw new AppError("Üretim kaydı oluşturulamadı.", 500);
    }

    return Response.json({
      id: row.id,
      type: row.type,
      status: row.status,
      previewUrl: row.preview_url,
      caption: row.caption,
      engineeredPrompt: row.engineered_prompt,
      modelUsed: row.model_used,
      unlockCost: appConfig.unlockCost,
      mock: appConfig.mockAi,
    });
  } catch (error) {
    return toErrorResponse(error);
  }
}
