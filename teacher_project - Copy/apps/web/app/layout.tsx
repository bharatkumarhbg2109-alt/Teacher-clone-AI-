import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "TeachClone — Adaptive AI Teacher",
  description:
    "Learn any subject at exactly your level, in text or audio. Upload a video, PDF or link — or learn from a popular teacher.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-bg text-slate-100 antialiased">{children}</body>
    </html>
  );
}
