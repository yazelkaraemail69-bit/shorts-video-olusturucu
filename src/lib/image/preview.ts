import sharp from "sharp";

export async function makePreviewAndFull(params: {
  base64: string;
  mimeType: string;
}): Promise<{
  preview: Buffer;
  full: Buffer;
  previewContentType: string;
  fullContentType: string;
}> {
  const input = Buffer.from(params.base64, "base64");

  const full = await sharp(input)
    .png({ quality: 90, compressionLevel: 8 })
    .toBuffer();

  const preview = await sharp(input)
    .resize({
      width: 512,
      height: 512,
      fit: "inside",
      withoutEnlargement: true,
    })
    .jpeg({ quality: 55, mozjpeg: true })
    .toBuffer();

  return {
    preview,
    full,
    previewContentType: "image/jpeg",
    fullContentType: "image/png",
  };
}
