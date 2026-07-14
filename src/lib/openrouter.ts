import { appConfig } from "@/lib/config";
import { AppError } from "@/lib/errors";

const OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions";

function headers() {
  const key = process.env.OPENROUTER_API_KEY;
  if (!key) {
    throw new AppError(
      "OpenRouter API anahtarı tanımlı değil.",
      500,
      "MISSING_OPENROUTER_KEY",
    );
  }

  return {
    Authorization: `Bearer ${key}`,
    "Content-Type": "application/json",
    "HTTP-Referer":
      process.env.OPENROUTER_SITE_URL ?? "http://localhost:3000",
    "X-Title": process.env.OPENROUTER_APP_NAME ?? "Moduler AI Uretim Hatti",
  };
}

export async function chatCompletion(params: {
  model: string;
  system: string;
  user: string;
  temperature?: number;
}): Promise<string> {
  if (appConfig.mockAi) {
    return mockChat(params.system, params.user);
  }

  const res = await fetch(OPENROUTER_URL, {
    method: "POST",
    headers: headers(),
    body: JSON.stringify({
      model: params.model,
      temperature: params.temperature ?? 0.4,
      messages: [
        { role: "system", content: params.system },
        { role: "user", content: params.user },
      ],
    }),
  });

  if (!res.ok) {
    const body = await res.text();
    console.error("OpenRouter chat error:", body);
    throw new AppError(
      "Prompt mühendisliği başarısız oldu. Lütfen tekrar deneyin.",
      502,
      "OPENROUTER_CHAT_FAILED",
    );
  }

  const data = (await res.json()) as {
    choices?: Array<{ message?: { content?: string } }>;
  };

  const content = data.choices?.[0]?.message?.content?.trim();
  if (!content) {
    throw new AppError("Model boş yanıt döndü.", 502, "EMPTY_CHAT");
  }

  return content;
}

export async function generateImage(params: {
  model: string;
  prompt: string;
}): Promise<{ base64: string; mimeType: string }> {
  if (appConfig.mockAi) {
    return mockImage(params.prompt);
  }

  const res = await fetch(OPENROUTER_URL, {
    method: "POST",
    headers: headers(),
    body: JSON.stringify({
      model: params.model,
      messages: [
        {
          role: "user",
          content: params.prompt,
        },
      ],
      modalities: ["image", "text"],
    }),
  });

  if (!res.ok) {
    const body = await res.text();
    console.error("OpenRouter image error:", body);
    throw new AppError(
      "Görsel üretimi başarısız oldu. Lütfen tekrar deneyin.",
      502,
      "OPENROUTER_IMAGE_FAILED",
    );
  }

  const data = (await res.json()) as {
    choices?: Array<{
      message?: {
        images?: Array<{
          image_url?: { url?: string };
          imageUrl?: { url?: string };
        }>;
        content?: string | Array<{ type?: string; image_url?: { url?: string } }>;
      };
    }>;
  };

  const message = data.choices?.[0]?.message;
  const fromImages =
    message?.images?.[0]?.image_url?.url ??
    message?.images?.[0]?.imageUrl?.url;

  let dataUrl = fromImages;

  if (!dataUrl && Array.isArray(message?.content)) {
    const part = message.content.find(
      (p) => p.type === "image_url" || p.image_url,
    );
    dataUrl = part?.image_url?.url;
  }

  if (!dataUrl) {
    throw new AppError(
      "Görsel modeli çıktı üretmedi. Model ID'lerini kontrol edin.",
      502,
      "NO_IMAGE_IN_RESPONSE",
    );
  }

  return await resolveImagePayload(dataUrl);
}

async function resolveImagePayload(
  url: string,
): Promise<{ base64: string; mimeType: string }> {
  if (url.startsWith("data:")) {
    const match = /^data:([^;]+);base64,(.+)$/.exec(url);
    if (!match) {
      throw new AppError("Geçersiz görsel veri formatı.", 502);
    }
    return { mimeType: match[1], base64: match[2] };
  }

  if (url.startsWith("http://") || url.startsWith("https://")) {
    const imgRes = await fetch(url);
    if (!imgRes.ok) {
      throw new AppError("Görsel indirilemedi.", 502);
    }
    const mimeType = imgRes.headers.get("content-type") ?? "image/png";
    const buf = Buffer.from(await imgRes.arrayBuffer());
    return { base64: buf.toString("base64"), mimeType };
  }

  throw new AppError(
    "Beklenen base64 görsel alınamadı.",
    502,
    "UNEXPECTED_IMAGE_URL",
  );
}

function mockChat(system: string, user: string): string {
  if (system.includes("caption") || system.includes("Instagram")) {
    return JSON.stringify({
      caption:
        "Yeni sezon, yeni enerji. Markanı öne çıkaran sade ve güçlü bir görsel dil. #tasarım #marka",
      imagePrompt: `Professional Instagram post visual for: ${user}. Clean composition, high contrast, modern brand aesthetic, square 1:1, no watermarks.`,
    });
  }

  if (system.includes("logo")) {
    return `Minimal vector-style logo design for: ${user}. Flat shapes, clean negative space, 2-3 colors max, centered mark, white background, no photorealism, no mockups, no text clutter.`;
  }

  return `Photorealistic high-quality image of: ${user}. Natural lighting, sharp detail, cinematic composition, no watermark, no text overlay.`;
}

async function mockImage(prompt: string): Promise<{
  base64: string;
  mimeType: string;
}> {
  // 1x1 teal PNG as tiny placeholder; Sharp will still process it.
  // Prefer a readable SVG rendered via a simple PNG from placehold text encoded.
  const label = encodeURIComponent(prompt.slice(0, 40) || "Mock AI");
  const res = await fetch(
    `https://placehold.co/1024x1024/1a3a32/e8f0ec/png?text=${label}`,
  );

  if (!res.ok) {
    // Fallback tiny PNG
    const tiny =
      "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==";
    return { base64: tiny, mimeType: "image/png" };
  }

  const buf = Buffer.from(await res.arrayBuffer());
  return { base64: buf.toString("base64"), mimeType: "image/png" };
}
