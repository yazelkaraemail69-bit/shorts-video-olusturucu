"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { createClient } from "@/lib/supabase/client";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [mode, setMode] = useState<"login" | "signup">("login");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setMessage(null);
    setLoading(true);

    try {
      const supabase = createClient();

      if (mode === "signup") {
        const { error: signError } = await supabase.auth.signUp({
          email,
          password,
          options: {
            emailRedirectTo: `${window.location.origin}/auth/callback`,
          },
        });
        if (signError) throw signError;
        setMessage(
          "Hesap oluşturuldu. E-posta onayını açtıysanız gelen kutunu kontrol edin; aksi halde giriş yapabilirsiniz.",
        );
      } else {
        const { error: loginError } = await supabase.auth.signInWithPassword({
          email,
          password,
        });
        if (loginError) throw loginError;
        window.location.href = "/";
      }
    } catch (err) {
      const msg =
        err instanceof Error ? err.message : "Kimlik doğrulama başarısız.";
      if (msg.includes("Supabase")) {
        setError(
          "Supabase yapılandırılmamış. .env.local içine URL ve anon key ekleyin.",
        );
      } else {
        setError(msg);
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto max-w-md px-5 py-16 sm:px-8">
      <h1 className="font-[family-name:var(--font-display)] text-3xl font-semibold">
        {mode === "login" ? "Giriş yap" : "Hesap oluştur"}
      </h1>
      <p className="mt-2 text-sm text-[var(--color-ink-soft)]">
        Üretim hattını kullanmak için oturum açın.
      </p>

      <form onSubmit={onSubmit} className="mt-8 space-y-4">
        <label className="block text-sm">
          E-posta
          <input
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="mt-1 w-full border border-[var(--color-line)] bg-white/70 px-3 py-2 outline-none focus:ring-2 focus:ring-[var(--color-accent)]"
          />
        </label>
        <label className="block text-sm">
          Şifre
          <input
            type="password"
            required
            minLength={6}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="mt-1 w-full border border-[var(--color-line)] bg-white/70 px-3 py-2 outline-none focus:ring-2 focus:ring-[var(--color-accent)]"
          />
        </label>

        <button
          type="submit"
          disabled={loading}
          className="w-full bg-[var(--color-ink)] py-3 text-[var(--color-fog)] hover:bg-[var(--color-accent)] disabled:opacity-60"
        >
          {loading ? "Bekleyin…" : mode === "login" ? "Giriş" : "Kayıt ol"}
        </button>
      </form>

      <button
        type="button"
        className="mt-4 text-sm text-[var(--color-accent)] underline-offset-4 hover:underline"
        onClick={() => setMode((m) => (m === "login" ? "signup" : "login"))}
      >
        {mode === "login"
          ? "Hesabın yok mu? Kayıt ol"
          : "Zaten hesabın var mı? Giriş yap"}
      </button>

      {error && (
        <p className="mt-4 text-sm text-[var(--color-warm)]" role="alert">
          {error}
        </p>
      )}
      {message && (
        <p className="mt-4 text-sm text-[var(--color-accent)]">{message}</p>
      )}

      <Link href="/" className="mt-8 inline-block text-sm text-[var(--color-ink-soft)]">
        ← Stüdyoya dön
      </Link>
    </div>
  );
}
