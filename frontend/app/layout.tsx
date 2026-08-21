import type { ReactNode } from "react";
import type { Metadata, Viewport } from "next";
import "./globals.css";
import AuroraBackground from "@/components/AuroraBackground";

export const metadata: Metadata = {
  title: "Mark · Real Estate Campaign AI",
  description:
    "Your AI campaign partner for real estate. Upload unit photos, answer a few questions, and Mark launches a professional Meta ad campaign — in under 2 minutes.",
};

export const viewport: Viewport = {
  themeColor: "#0A0805",
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
          href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Playfair+Display:ital,wght@0,700;0,800;1,700&display=swap"
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
