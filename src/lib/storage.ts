import { createAdminClient } from "@/lib/supabase/admin";
import { AppError } from "@/lib/errors";

export async function uploadGenerationAssets(params: {
  userId: string;
  generationId: string;
  preview: Buffer;
  full: Buffer;
  previewContentType: string;
  fullContentType: string;
}): Promise<{ previewUrl: string; fullPath: string }> {
  const admin = createAdminClient();
  const previewPath = `${params.userId}/${params.generationId}/preview.jpg`;
  const fullPath = `${params.userId}/${params.generationId}/full.png`;

  const { error: previewError } = await admin.storage
    .from("generations")
    .upload(previewPath, params.preview, {
      contentType: params.previewContentType,
      upsert: true,
    });

  if (previewError) {
    console.error(previewError);
    throw new AppError("Önizleme yüklenemedi.", 500);
  }

  const { error: fullError } = await admin.storage
    .from("generations")
    .upload(fullPath, params.full, {
      contentType: params.fullContentType,
      upsert: true,
    });

  if (fullError) {
    console.error(fullError);
    throw new AppError("Tam görsel yüklenemedi.", 500);
  }

  const { data: publicData } = admin.storage
    .from("generations")
    .getPublicUrl(previewPath);

  // Store private full path; signed URL created on unlock
  return {
    previewUrl: publicData.publicUrl,
    fullPath,
  };
}

export async function createSignedFullUrl(fullPath: string) {
  const admin = createAdminClient();
  const { data, error } = await admin.storage
    .from("generations")
    .createSignedUrl(fullPath, 60 * 60);

  if (error || !data?.signedUrl) {
    console.error(error);
    throw new AppError("Tam görsel bağlantısı oluşturulamadı.", 500);
  }

  return data.signedUrl;
}
