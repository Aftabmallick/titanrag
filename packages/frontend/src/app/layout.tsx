import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "TitanRAG — Enterprise RAG Platform",
  description: "Multi-tenant, multimodal enterprise retrieval-augmented generation engine",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="antialiased bg-slate-950 text-slate-100">{children}</body>
    </html>
  );
}
