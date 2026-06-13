import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "FX Strategy Lab",
  description: "Safety-first personal FX strategy validation workspace"
};

export default function RootLayout({
  children
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="ja">
      <body>{children}</body>
    </html>
  );
}
