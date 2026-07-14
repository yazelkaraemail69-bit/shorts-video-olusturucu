import type { Metadata } from "next";
import { Manrope, Syne } from "next/font/google";
import Link from "next/link";
import "./globals.css";

const syne = Syne({
  subsets: ["latin"],
  variable: "--font-syne",
  display: "swap",
});

const manrope = Manrope({
  subsets: ["latin"],
  variable: "--font-manrope",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Modüler AI Üretim Hattı",
  description:
    "İsteğini seç, uzman AI modelleri arka planda birleşsin — logo, görsel ve sosyal medya üretimi.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="tr">
      <body
        className={`${syne.variable} ${manrope.variable} antialiased`}
        style={
          {
            "--font-display": "var(--font-syne)",
            "--font-body": "var(--font-manrope)",
          } as React.CSSProperties
        }
      >
        <div className="min-h-screen">
          <header className="mx-auto flex w-full max-w-5xl items-center justify-between px-5 py-5 sm:px-8">
            <Link
              href="/"
              className="font-[family-name:var(--font-display)] text-sm font-semibold tracking-wide text-[var(--color-ink)] sm:text-base"
            >
              Modüler AI Üretim Hattı
            </Link>
            <nav className="flex items-center gap-4 text-sm text-[var(--color-ink-soft)]">
              <Link href="/gecmis" className="hover:text-[var(--color-accent)]">
                Geçmiş
              </Link>
              <Link href="/hesabim" className="hover:text-[var(--color-accent)]">
                Hesabım
              </Link>
              <Link
                href="/login"
                className="rounded-md bg-[var(--color-ink)] px-3 py-1.5 text-[var(--color-fog)] transition hover:bg-[var(--color-accent)]"
              >
                Giriş
              </Link>
            </nav>
          </header>
          <main>{children}</main>
        </div>
      </body>
    </html>
  );
}
