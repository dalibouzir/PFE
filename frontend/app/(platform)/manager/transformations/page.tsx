import { PageIntro } from "@/components/ui/PageIntro";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { transformationRecords, transformationsFlow } from "@/lib/mock-data";

export default function TransformationsPage() {
  return (
    <main>
      <PageIntro title="Transformations" subtitle="Nettoyage, sechage, tri et emballage des lots." />

      <section className="premium-card reveal rounded-2xl p-5" style={{ ["--delay" as string]: "40ms" }}>
        <h3 className="text-base font-semibold text-[var(--green-900)]">Flux post-recolte</h3>
        <div className="mt-3 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          {transformationsFlow.map((step) => (
            <article key={step.etape} className="rounded-xl border border-[var(--line)] bg-[var(--surface-soft)] p-3">
              <p className="text-xs uppercase tracking-wide text-[var(--muted)]">{step.etape}</p>
              <p className="mt-1 text-sm font-semibold text-[var(--text)]">{step.lotsActifs} lots actifs</p>
              <p className="mt-1 text-xs text-[var(--muted)]">Efficacite {step.efficacite.toFixed(1)}%</p>
              <p className="text-xs text-[#9a5e3d]">Perte moyenne {step.perteMoyenne.toFixed(1)}%</p>
            </article>
          ))}
        </div>
      </section>

      <section className="mt-4 grid gap-4 xl:grid-cols-3">
        {transformationRecords.map((record, index) => (
          <article key={record.lotCode} className="premium-card reveal rounded-2xl p-5" style={{ ["--delay" as string]: `${90 + index * 50}ms` }}>
            <div className="mb-2 flex items-center justify-between">
              <h3 className="text-base font-semibold text-[var(--green-900)]">{record.lotCode}</h3>
              <StatusBadge
                label={record.statut}
                tone={record.statut === "Bloque" ? "danger" : record.statut === "En transformation" ? "warning" : "success"}
              />
            </div>

            <p className="text-sm text-[var(--muted)]">{record.produit} · {record.quantiteKg.toLocaleString("fr-FR")} kg</p>
            <p className="text-xs text-[var(--muted)]">Equipe: {record.operateur}</p>

            <div className="mt-3 rounded-xl bg-[var(--surface-soft)] px-3 py-2 text-sm">
              Etape actuelle: <span className="font-semibold text-[var(--green-900)]">{record.stageActuelle}</span>
            </div>

            <div className="mt-3 space-y-2">
              {record.historique.map((step) => (
                <div key={step.stage} className="rounded-xl border border-[var(--line)] px-3 py-2">
                  <div className="flex items-center justify-between text-sm">
                    <p className="font-medium text-[var(--text)]">{step.stage}</p>
                    <StatusBadge
                      label={step.state === "termine" ? "Termine" : step.state === "en cours" ? "En cours" : "A venir"}
                      tone={step.state === "termine" ? "success" : step.state === "en cours" ? "warning" : "info"}
                    />
                  </div>
                  <p className="mt-1 text-xs text-[var(--muted)]">
                    {step.startedAt} {step.endedAt ? `-> ${step.endedAt}` : "-> en cours"}
                  </p>
                </div>
              ))}
            </div>
          </article>
        ))}
      </section>
    </main>
  );
}
