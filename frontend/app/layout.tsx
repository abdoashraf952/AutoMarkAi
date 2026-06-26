import type { ReactNode } from "react";
import type { Metadata, Viewport } from "next";
import "./globals.css";
import AuroraBackground from "@/components/AuroraBackground";

export const metadata: Metadata = {
  title: "AutoMark AI — Your friendly ad helper",
  description:
    "Answer a few simple questions and AutoMark turns your idea into a ready-to-publish ad — no marketing experience needed.",
};

export const viewport: Viewport = {
  themeColor: "#070b1a",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>
        <AuroraBackground />
        {children}
      </body>
    </html>
  );
}
