import { appConfig, isSupabaseConfigured } from "@/lib/config";
import { AppError, toErrorResponse } from "@/lib/errors";
import { getProfileCredits } from "@/lib/credits";
import { getDailyUsage } from "@/lib/quota";
import { createClient } from "@/lib/supabase/server";
import type { MeResponse } from "@/lib/types";

export async function GET() {
  try {
    if (!isSupabaseConfigured()) {
      throw new AppError("Supabase yapılandırılmamış.", 503, "NO_SUPABASE");
    }

    const supabase = await createClient();
    const {
      data: { user },
    } = await supabase.auth.getUser();

    if (!user) {
      throw new AppError("Giriş yapmalısınız.", 401, "UNAUTHORIZED");
    }

    const [profile, usage] = await Promise.all([
      getProfileCredits(user.id),
      getDailyUsage(user.id),
    ]);

    const body: MeResponse = {
      email: profile.email ?? user.email ?? null,
      credits: profile.credits,
      dailyLimit: usage.limit,
      usedToday: usage.used,
      remainingToday: usage.remaining,
      unlockCost: appConfig.unlockCost,
    };

    return Response.json(body);
  } catch (error) {
    return toErrorResponse(error);
  }
}
