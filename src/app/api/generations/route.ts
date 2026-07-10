import { isSupabaseConfigured } from "@/lib/config";
import { AppError, toErrorResponse } from "@/lib/errors";
import { createClient } from "@/lib/supabase/server";

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

    const { data, error } = await supabase
      .from("generations")
      .select(
        "id, type, user_prompt, engineered_prompt, caption, preview_url, status, credits_spent, model_used, created_at",
      )
      .eq("user_id", user.id)
      .order("created_at", { ascending: false })
      .limit(50);

    if (error) {
      console.error(error);
      throw new AppError("Geçmiş yüklenemedi.", 500);
    }

    return Response.json({ items: data ?? [] });
  } catch (error) {
    return toErrorResponse(error);
  }
}
