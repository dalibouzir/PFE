import "./globals.css";
import type { Metadata } from "next";
import { Manrope, Sora } from "next/font/google";

const manrope = Manrope({
  subsets: ["latin"],
  variable: "--font-manrope",
});

const sora = Sora({
  subsets: ["latin"],
  variable: "--font-sora",
});

export const metadata: Metadata = {
  title: "WeeFarm | VERDANOVA",
  description: "Plateforme de gestion des cooperatives agricoles",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fr">
      <body className={`${manrope.variable} ${sora.variable}`}>{children}</body>
    </html>
  );
}
