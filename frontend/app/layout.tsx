import type { ReactNode } from "react";
import type { Metadata, Viewport } from "next";
import "./globals.css";
import AuroraBackground from "@/components/AuroraBackground";

export const metadata: Metadata = {
  title: "AutoMark AI — Conversational Campaign Studio",
  description:
    "Chat your way from a single product photo to a published Meta ad campaign.",
};

export const viewport: Viewport = {
  themeColor: "#05060f",
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
