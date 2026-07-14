import { appConfig } from "@/lib/config";
import { AppError } from "@/lib/errors";
import { createAdminClient } from "@/lib/supabase/admin";

function todayUtc(): string {
  return new Date().toISOString().slice(0, 10);
}

export async function assertAndIncrementDailyQuota(userId: string) {
  const admin = createAdminClient();
  const day = todayUtc();
  const limit = appConfig.dailyLimit;

  const { data: existing, error: readError } = await admin
    .from("usage_daily")
    .select("generations_count")
    .eq("user_id", userId)
    .eq("day", day)
    .maybeSingle();

  if (readError) {
    console.error(readError);
    throw new AppError("Kota kontrolü başarısız.", 500);
  }

  const used = existing?.generations_count ?? 0;
  if (used >= limit) {
    throw new AppError(
      `Günlük üretim limitine ulaştınız (${limit}/gün). Yarın tekrar deneyin.`,
      429,
      "DAILY_LIMIT",
    );
  }

  if (existing) {
    const { error } = await admin
      .from("usage_daily")
      .update({ generations_count: used + 1 })
      .eq("user_id", userId)
      .eq("day", day);

    if (error) {
      console.error(error);
      throw new AppError("Kota güncellenemedi.", 500);
    }
  } else {
    const { error } = await admin.from("usage_daily").insert({
      user_id: userId,
      day,
      generations_count: 1,
    });

    if (error) {
      console.error(error);
      throw new AppError("Kota kaydı oluşturulamadı.", 500);
    }
  }

  return { used: used + 1, remaining: limit - used - 1, limit };
}

export async function getDailyUsage(userId: string) {
  const admin = createAdminClient();
  const day = todayUtc();

  const { data } = await admin
    .from("usage_daily")
    .select("generations_count")
    .eq("user_id", userId)
    .eq("day", day)
    .maybeSingle();

  const used = data?.generations_count ?? 0;
  return {
    used,
    remaining: Math.max(0, appConfig.dailyLimit - used),
    limit: appConfig.dailyLimit,
  };
}
