"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

type Item = {
  id: string;
  type: string;
  user_prompt: string;
  caption: string | null;
  preview_url: string | null;
  status: string;
  created_at: string;
  model_used: string | null;
};

const TYPE_LABEL: Record<string, string> = {
  logo: "Logo",
  image: "Görsel",
  social: "Sosyal Medya",
};

export default function GecmisPage() {
  const [items, setItems] = useState<Item[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/api/generations")
      .then(async (res) => {
        const data = await res.json();
        if (!res.ok) throw new Error(data.error ?? "Geçmiş yüklenemedi.");
        setItems(data.items ?? []);
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="mx-auto max-w-5xl px-5 py-12 sm:px-8">
      <h1 className="font-[family-name:var(--font-display)] text-3xl font-semibold">
        Geçmiş
      </h1>
      <p className="mt-2 text-sm text-[var(--color-ink-soft)]">
        Son üretimlerin. Tam çıktı için ana sayfadan kredi harcayabilirsin.
      </p>

      {loading && <p className="mt-8 text-sm">Yükleniyor…</p>}

      {error && (
        <div className="mt-8 border border-[var(--color-warm)]/30 bg-[var(--color-warm)]/10 p-4 text-sm text-[var(--color-warm)]">
          {error}
          <div className="mt-3">
            <Link href="/login" className="underline">
              Giriş yap
            </Link>
          </div>
        </div>
      )}

      {!loading && !error && items.length === 0 && (
        <p className="mt-10 text-[var(--color-ink-soft)]">
          Henüz üretim yok.{" "}
          <Link href="/" className="text-[var(--color-accent)] underline">
            Stüdyoya git
          </Link>
        </p>
      )}

      <ul className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {items.map((item) => (
          <li
            key={item.id}
            className="border border-[var(--color-line)] bg-white/60"
          >
            {item.preview_url ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={item.preview_url}
                alt=""
                className="aspect-square w-full object-cover"
              />
            ) : (
              <div className="flex aspect-square items-center justify-center bg-[var(--color-mist)] text-sm text-[var(--color-ink-soft)]">
                Görsel yok
              </div>
            )}
            <div className="space-y-1 p-3">
              <p className="text-xs uppercase tracking-wider text-[var(--color-accent)]">
                {TYPE_LABEL[item.type] ?? item.type} · {item.status}
              </p>
              <p className="line-clamp-2 text-sm">{item.user_prompt}</p>
              <p className="text-xs text-[var(--color-ink-soft)]">
                {new Date(item.created_at).toLocaleString("tr-TR")}
              </p>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
