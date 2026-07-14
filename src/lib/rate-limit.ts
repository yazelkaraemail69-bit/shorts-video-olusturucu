import { AppError } from "@/lib/errors";

type Bucket = { count: number; resetAt: number };

const buckets = new Map<string, Bucket>();

export function assertRateLimit(params: {
  key: string;
  limit: number;
  windowMs: number;
}): void {
  const now = Date.now();
  const current = buckets.get(params.key);

  if (!current || now >= current.resetAt) {
    buckets.set(params.key, {
      count: 1,
      resetAt: now + params.windowMs,
    });
    return;
  }

  if (current.count >= params.limit) {
    throw new AppError(
      "Çok fazla istek. Birkaç saniye sonra tekrar deneyin.",
      429,
      "RATE_LIMIT",
    );
  }

  current.count += 1;
}
