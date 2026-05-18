"use client";

import { AgriBrandLoader } from "@/components/ui/AgriBrandLoader";

export function ContentAreaLoader({
  title = "Chargement de la page",
  subtitle = "Préparation des données...",
}: {
  title?: string;
  subtitle?: string;
}) {
  return (
    <div className="absolute inset-0 z-30 flex items-center justify-center bg-[linear-gradient(180deg,rgba(249,246,239,0.84)_0%,rgba(249,246,239,0.66)_32%,rgba(249,246,239,0.42)_72%,rgba(249,246,239,0.14)_100%)] backdrop-blur-[8px]">
      <AgriBrandLoader mode="panel" title={title} subtitle={subtitle} />
    </div>
  );
}

