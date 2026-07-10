import { appConfig } from "@/lib/config";
import { AppError } from "@/lib/errors";
import { createAdminClient } from "@/lib/supabase/admin";

export async function getProfileCredits(userId: string) {
  const admin = createAdminClient();
  const { data, error } = await admin
    .from("profiles")
    .select("credits, email")
    .eq("id", userId)
    .maybeSingle();

  if (error) {
    console.error(error);
    throw new AppError("Profil okunamadı.", 500);
  }

  if (!data) {
    throw new AppError("Profil bulunamadı.", 404, "NO_PROFILE");
  }

  return data as { credits: number; email: string | null };
}

export async function unlockGeneration(params: {
  userId: string;
  generationId: string;
}) {
  const admin = createAdminClient();
  const cost = appConfig.unlockCost;

  const { data: generation, error: genError } = await admin
    .from("generations")
    .select("*")
    .eq("id", params.generationId)
    .eq("user_id", params.userId)
    .maybeSingle();

  if (genError) {
    console.error(genError);
    throw new AppError("Üretim kaydı okunamadı.", 500);
  }

  if (!generation) {
    throw new AppError("Üretim bulunamadı.", 404);
  }

  if (generation.status === "unlocked" && generation.full_url) {
    return generation;
  }

  if (!generation.full_url) {
    throw new AppError("Tam çözünürlük dosyası hazır değil.", 409);
  }

  const profile = await getProfileCredits(params.userId);
  if (profile.credits < cost) {
    throw new AppError(
      `Yetersiz kredi. Tam çıktı için ${cost} kredi gerekli.`,
      402,
      "INSUFFICIENT_CREDITS",
    );
  }

  const { error: creditError } = await admin
    .from("profiles")
    .update({ credits: profile.credits - cost })
    .eq("id", params.userId)
    .gte("credits", cost);

  if (creditError) {
    console.error(creditError);
    throw new AppError("Kredi düşülemedi.", 500);
  }

  const { data: updated, error: updateError } = await admin
    .from("generations")
    .update({
      status: "unlocked",
      credits_spent: cost,
    })
    .eq("id", params.generationId)
    .eq("user_id", params.userId)
    .select("*")
    .single();

  if (updateError || !updated) {
    console.error(updateError);
    // best-effort rollback
    await admin
      .from("profiles")
      .update({ credits: profile.credits })
      .eq("id", params.userId);
    throw new AppError("Kilidi açma başarısız.", 500);
  }

  return updated;
}
