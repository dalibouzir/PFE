import "./globals.css";
import type { Metadata } from "next";
import { Manrope, Sora } from "next/font/google";
import { Providers } from "@/app/providers";

const manrope = Manrope({
  subsets: ["latin"],
  variable: "--font-manrope",
});

const sora = Sora({
  subsets: ["latin"],
  variable: "--font-sora",
});

export const metadata: Metadata = {
  title: "WeeFarm",
  description: "Plateforme de gestion des cooperatives agricoles",
  icons: {
    icon: "/logo.png",
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fr" data-scroll-behavior="smooth">
      <body className={`${manrope.variable} ${sora.variable}`}>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
