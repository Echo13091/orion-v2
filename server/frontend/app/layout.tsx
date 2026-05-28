import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
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
  title: "Orion V2",
  description: "Distributed edge automation operations console",
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
        <a
          href="/vision-node"
          className="fixed right-3 top-3 z-50 rounded-full border border-neutral-700 bg-neutral-950/90 px-3 py-2 text-xs font-semibold uppercase tracking-[0.16em] text-neutral-200 shadow-lg backdrop-blur transition hover:border-blue-400/60 hover:bg-blue-500/10 hover:text-blue-100"
        >
          Vision Node
        </a>
        {children}
      </body>
    </html>
  );
}
