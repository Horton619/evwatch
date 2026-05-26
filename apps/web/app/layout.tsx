import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import Link from "next/link";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "evwatch",
  description: "Used EV market monitor — Pacific Northwest",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">
        <header className="sticky top-0 z-10 bg-[#070910]/90 backdrop-blur border-b border-neutral-900">
          <div className="max-w-7xl mx-auto px-4 md:px-6 py-3 flex items-baseline justify-between">
            <Link href="/" className="flex items-baseline gap-2">
              <span className="text-[10px] tracking-[0.3em] uppercase text-neutral-500">
                Visual Entropy Productions
              </span>
              <span className="text-lg font-semibold text-neutral-100">
                evwatch
              </span>
            </Link>
            <span className="text-xs text-neutral-500 hidden md:block">
              Pacific Northwest · 100mi from Port Orchard
            </span>
          </div>
        </header>
        <main className="flex-1">{children}</main>
        <footer className="border-t border-neutral-900 py-4 mt-8">
          <div className="max-w-7xl mx-auto px-4 md:px-6 text-[11px] text-neutral-600 flex justify-between">
            <span>© {new Date().getFullYear()} Visual Entropy Productions</span>
            <a
              href="https://veproductions.net"
              target="_blank"
              rel="noopener noreferrer"
              className="hover:text-neutral-400"
            >
              veproductions.net
            </a>
          </div>
        </footer>
      </body>
    </html>
  );
}
