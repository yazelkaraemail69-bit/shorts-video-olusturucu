"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { createClient } from "@/lib/supabase/client";
import type { MeResponse } from "@/lib/types";

export default function HesabimPage() {
  const [me, setMe] = useState<MeResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/api/me")
      .then(async (res) => {
        const data = await res.json();
        if (!res.ok) throw new Error(data.error ?? "Profil yüklenemedi.");
        setMe(data);
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  async function logout() {
    try {
      const supabase = createClient();
      await supabase.auth.signOut();
      window.location.href = "/login";
    } catch {
      setError("Çıkış yapılamadı. Supabase yapılandırmasını kontrol edin.");
    }
  }

  return (
    <div className="mx-auto max-w-lg px-5 py-12 sm:px-8">
      <h1 className="font-[family-name:var(--font-display)] text-3xl font-semibold">
        Hesabım
      </h1>
      <p className="mt-2 text-sm text-[var(--color-ink-soft)]">
        Kredi bakiyesi ve günlük üretim hakkın.
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

      {me && (
        <div className="mt-8 space-y-4 border border-[var(--color-line)] bg-white/60 p-5">
          <p className="text-sm text-[var(--color-ink-soft)]">{me.email}</p>
          <dl className="grid grid-cols-2 gap-4">
            <div>
              <dt className="text-xs uppercase tracking-wider text-[var(--color-accent)]">
                Kredi
              </dt>
              <dd className="font-[family-name:var(--font-display)] text-3xl font-semibold">
                {me.credits}
              </dd>
            </div>
            <div>
              <dt className="text-xs uppercase tracking-wider text-[var(--color-accent)]">
                Bugün kalan
              </dt>
              <dd className="font-[family-name:var(--font-display)] text-3xl font-semibold">
                {me.remainingToday}
                <span className="text-base font-normal text-[var(--color-ink-soft)]">
                  /{me.dailyLimit}
                </span>
              </dd>
            </div>
          </dl>
          <p className="text-sm text-[var(--color-ink-soft)]">
            Tam çıktı kilidi açmak {me.unlockCost} kredi tutar. Önizleme günlük
            limitten düşer, krediden düşmez.
          </p>
          <button
            type="button"
            onClick={logout}
            className="border border-[var(--color-line)] px-4 py-2 text-sm hover:border-[var(--color-accent)]"
          >
            Çıkış yap
          </button>
        </div>
      )}
    </div>
  );
}
