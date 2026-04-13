import Image from "next/image";

export function AgriBrandLoader({
  title = "WeeFarm",
  subtitle = "Synchronisation des parcelles, stocks et collectes...",
  mode = "screen",
}: {
  title?: string;
  subtitle?: string;
  mode?: "screen" | "panel";
}) {
  const isScreen = mode === "screen";

  return (
    <main className={isScreen ? "agri-loader-screen" : "agri-loader-panel"} role="status" aria-live="polite" aria-label="Chargement en cours">
      {isScreen && <div className="agri-loader-noise" />}
      {isScreen && <div className="agri-loader-halo agri-loader-halo-one" />}
      {isScreen && <div className="agri-loader-halo agri-loader-halo-two" />}

      <section className={isScreen ? "agri-loader-core" : "agri-loader-core agri-loader-core-compact"}>
        <div className="agri-loader-orbit">
          <span className="agri-loader-seed agri-loader-seed-a" />
          <span className="agri-loader-seed agri-loader-seed-b" />
          <span className="agri-loader-seed agri-loader-seed-c" />

          <div className="agri-loader-logo-shell">
            <Image
              src="/logo.png"
              alt="Logo WeeFarm"
              width={88}
              height={88}
              className="agri-loader-logo"
              priority
            />
          </div>
        </div>

        <div className="agri-loader-growline">
          <span className="agri-loader-soil" />
          <span className="agri-loader-stem" />
          <span className="agri-loader-leaf agri-loader-leaf-left" />
          <span className="agri-loader-leaf agri-loader-leaf-right" />
        </div>

        <h2 className="agri-loader-title">{title}</h2>
        <p className="agri-loader-subtitle">{subtitle}</p>

        <div className="agri-loader-dots" aria-hidden="true">
          <span />
          <span />
          <span />
        </div>
      </section>
    </main>
  );
}
