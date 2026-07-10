import { appConfig, isSupabaseConfigured } from "@/lib/config";
import { AppError, toErrorResponse } from "@/lib/errors";
import { unlockGeneration } from "@/lib/credits";
import { createClient } from "@/lib/supabase/server";
import { createSignedFullUrl } from "@/lib/storage";

export async function POST(
  _request: Request,
  context: { params: Promise<{ id: string }> },
) {
  try {
    if (!isSupabaseConfigured()) {
      throw new AppError("Supabase yapılandırılmamış.", 503, "NO_SUPABASE");
    }

    const { id } = await context.params;
    const supabase = await createClient();
    const {
      data: { user },
    } = await supabase.auth.getUser();

    if (!user) {
      throw new AppError("Giriş yapmalısınız.", 401, "UNAUTHORIZED");
    }

    const updated = await unlockGeneration({
      userId: user.id,
      generationId: id,
    });

    const signedUrl = await createSignedFullUrl(updated.full_url as string);

    return Response.json({
      id: updated.id,
      status: updated.status,
      fullUrl: signedUrl,
      creditsSpent: updated.credits_spent,
      unlockCost: appConfig.unlockCost,
    });
  } catch (error) {
    return toErrorResponse(error);
  }
}
