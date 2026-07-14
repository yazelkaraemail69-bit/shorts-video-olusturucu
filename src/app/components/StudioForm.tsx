"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import type { GenerationType } from "@/lib/types";

type ResultState = {
  id: string;
  type: GenerationType;
  status: string;
  previewUrl: string;
  caption: string | null;
  engineeredPrompt: string;
  modelUsed: string;
  unlockCost: number;
  fullUrl?: string;
  mock?: boolean;
};

const TYPES: Array<{ id: GenerationType; label: string; hint: string }> = [
  {
    id: "logo",
    label: "Logo",
    hint: "Minimal, marka odaklı işaret",
  },
  {
    id: "image",
    label: "Görsel",
    hint: "Fotoğraf gerçekçiliğinde sahne",
  },
  {
    id: "social",
    label: "Sosyal Medya",
    hint: "Caption + Instagram görseli",
  },
];

const PLACEHOLDERS: Record<GenerationType, string> = {
  logo: "Restoranım için modern bir logo istiyorum",
  image: "Ahşap masada buharlı kahve, sabah ışığı",
  social: "Yeni ürünüm için Instagram postu tasarla",
};

export function StudioForm() {
  const [type, setType] = useState<GenerationType>("logo");
  const [prompt, setPrompt] = useState("");
  const [loading, setLoading] = useState(false);
  const [unlocking, setUnlocking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ResultState | null>(null);
  const [showPrompt, setShowPrompt] = useState(false);
  const [me, setMe] = useState<{
    credits: number;
    remainingToday: number;
    dailyLimit: number;
  } | null>(null);

  useEffect(() => {
    fetch("/api/me")
      .then(async (res) => {
        if (!res.ok) return null;
        return res.json();
      })
      .then((data) => {
        if (data) {
          setMe({
            credits: data.credits,
            remainingToday: data.remainingToday,
            dailyLimit: data.dailyLimit,
          });
        }
      })
      .catch(() => null);
  }, [result]);

  const placeholder = useMemo(() => PLACEHOLDERS[type], [type]);

  async function onGenerate(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setResult(null);
    setLoading(true);

    try {
      const res = await fetch("/api/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ type, prompt }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.error ?? "Üretim başarısız.");
      }
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Bir hata oluştu.");
    } finally {
      setLoading(false);
    }
  }

  async function onUnlock() {
    if (!result) return;
    setUnlocking(true);
    setError(null);
    try {
      const res = await fetch(`/api/generations/${result.id}/unlock`, {
        method: "POST",
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.error ?? "Kilit açılamadı.");
      }
      setResult((prev) =>
        prev
          ? {
              ...prev,
              status: data.status,
              fullUrl: data.fullUrl,
            }
          : prev,
      );
      setMe((prev) =>
        prev
          ? { ...prev, credits: Math.max(0, prev.credits - (result.unlockCost || 1)) }
          : prev,
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Bir hata oluştu.");
    } finally {
      setUnlocking(false);
    }
  }

  return (
    <div className="mx-auto w-full max-w-5xl px-5 pb-20 sm:px-8">
      <section className="relative overflow-hidden rounded-none pt-6 sm:pt-10">
        <div
          className="pointer-events-none absolute inset-0 -z-10 opacity-70"
          style={{
            backgroundImage:
              "linear-gradient(135deg, rgba(15,107,92,0.08), transparent 40%), repeating-linear-gradient(-12deg, transparent, transparent 18px, rgba(20,40,34,0.04) 18px, rgba(20,40,34,0.04) 19px)",
          }}
        />

        <p className="mb-3 text-xs font-medium uppercase tracking-[0.22em] text-[var(--color-accent)]">
          AI Design Studio
        </p>
        <h1 className="max-w-3xl font-[family-name:var(--font-display)] text-4xl leading-[1.05] font-semibold tracking-tight text-[var(--color-ink)] sm:text-6xl">
          Modüler AI Üretim Hattı
        </h1>
        <p className="mt-4 max-w-xl text-base leading-relaxed text-[var(--color-ink-soft)] sm:text-lg">
          Ne istediğini söyle. Sistem, işin uzmanı modelleri arka planda
          birleştirip sonucu getirir.
        </p>

        {me && (
          <p className="mt-4 text-sm text-[var(--color-ink-soft)]">
            Bugün {me.remainingToday}/{me.dailyLimit} üretim · {me.credits} kredi
          </p>
        )}
      </section>

      <form onSubmit={onGenerate} className="mt-10 space-y-6">
        <fieldset>
          <legend className="mb-3 text-sm font-medium text-[var(--color-ink)]">
            Üretim tipi
          </legend>
          <div className="grid gap-3 sm:grid-cols-3">
            {TYPES.map((item) => {
              const active = type === item.id;
              return (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => setType(item.id)}
                  className={`border px-4 py-4 text-left transition ${
                    active
                      ? "border-[var(--color-accent)] bg-[var(--color-accent)] text-[var(--color-fog)]"
                      : "border-[var(--color-line)] bg-white/50 text-[var(--color-ink)] hover:border-[var(--color-accent)]"
                  }`}
                >
                  <span className="block font-[family-name:var(--font-display)] text-lg font-semibold">
                    {item.label}
                  </span>
                  <span
                    className={`mt-1 block text-sm ${active ? "text-white/80" : "text-[var(--color-ink-soft)]"}`}
                  >
                    {item.hint}
                  </span>
                </button>
              );
            })}
          </div>
        </fieldset>

        <label className="block">
          <span className="mb-2 block text-sm font-medium">İsteğin</span>
          <textarea
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder={placeholder}
            rows={4}
            required
            className="w-full resize-y border border-[var(--color-line)] bg-white/70 px-4 py-3 text-[var(--color-ink)] outline-none ring-[var(--color-accent)] placeholder:text-[var(--color-line)] focus:ring-2"
          />
        </label>

        <div className="flex flex-wrap items-center gap-3">
          <button
            type="submit"
            disabled={loading}
            className="bg-[var(--color-ink)] px-6 py-3 font-medium text-[var(--color-fog)] transition hover:bg-[var(--color-accent)] disabled:opacity-60"
          >
            {loading ? "Üretiliyor…" : "Üret"}
          </button>
          <Link
            href="/login"
            className="text-sm text-[var(--color-ink-soft)] underline-offset-4 hover:text-[var(--color-accent)] hover:underline"
          >
            Giriş yapmadan üretim çalışmaz
          </Link>
        </div>
      </form>

      {error && (
        <div
          role="alert"
          className="mt-6 border border-[var(--color-warm)]/40 bg-[var(--color-warm)]/10 px-4 py-3 text-sm text-[var(--color-warm)]"
        >
          {error}
          {error.includes("giriş") && (
            <Link href="/login" className="ml-2 underline">
              Giriş sayfası
            </Link>
          )}
        </div>
      )}

      {result && (
        <section className="mt-10 grid gap-6 border-t border-[var(--color-line)] pt-10 lg:grid-cols-[1.1fr_0.9fr]">
          <div>
            <p className="mb-2 text-xs uppercase tracking-[0.18em] text-[var(--color-accent)]">
              Önizleme
              {result.mock ? " · mock" : ""}
            </p>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={result.fullUrl ?? result.previewUrl}
              alt="Üretilen görsel"
              className={`w-full border border-[var(--color-line)] bg-[var(--color-mist)] object-cover ${
                result.fullUrl ? "" : "blur-[1.5px] brightness-95"
              }`}
            />
            {!result.fullUrl && (
              <p className="mt-2 text-sm text-[var(--color-ink-soft)]">
                Düşük çözünürlüklü önizleme. Tam çıktı için kredi harcayın.
              </p>
            )}
          </div>

          <div className="space-y-4">
            {result.caption && (
              <div>
                <h2 className="font-[family-name:var(--font-display)] text-lg font-semibold">
                  Caption
                </h2>
                <p className="mt-2 whitespace-pre-wrap text-[var(--color-ink-soft)]">
                  {result.caption}
                </p>
              </div>
            )}

            <button
              type="button"
              onClick={() => setShowPrompt((v) => !v)}
              className="text-sm text-[var(--color-accent)] underline-offset-4 hover:underline"
            >
              {showPrompt ? "Geliştirilmiş promptu gizle" : "Geliştirilmiş promptu göster"}
            </button>
            {showPrompt && (
              <pre className="overflow-x-auto whitespace-pre-wrap border border-[var(--color-line)] bg-white/60 p-3 text-xs text-[var(--color-ink-soft)]">
                {result.engineeredPrompt}
              </pre>
            )}

            <p className="text-xs text-[var(--color-ink-soft)]">
              Model hattı: {result.modelUsed}
            </p>

            {result.fullUrl ? (
              <a
                href={result.fullUrl}
                target="_blank"
                rel="noreferrer"
                className="inline-block bg-[var(--color-accent)] px-5 py-3 font-medium text-white hover:bg-[var(--color-accent-deep)]"
              >
                Tam görseli aç
              </a>
            ) : (
              <button
                type="button"
                onClick={onUnlock}
                disabled={unlocking}
                className="bg-[var(--color-warm)] px-5 py-3 font-medium text-white transition hover:opacity-90 disabled:opacity-60"
              >
                {unlocking
                  ? "Açılıyor…"
                  : `Tamamı için ${result.unlockCost} kredi harca`}
              </button>
            )}
          </div>
        </section>
      )}
    </div>
  );
}
