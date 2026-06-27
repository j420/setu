import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "SETU — Reunification Control Room",
  description:
    "Name-optional, PA-first, human-gated missing-person reunification for Kumbh Mela 2027.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
