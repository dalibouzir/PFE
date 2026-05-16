import { EtapeStatut, LotStatut } from "@prisma/client";
import { Router } from "express";
import { prisma } from "../lib/prisma";
import { getCache, setCache } from "../lib/redis";
import { requireAuth } from "../middleware/auth";
import { asyncHandler, ok } from "../utils/http";
import { mapCollecte, mapEtape, mapRecommendation } from "../utils/mappers";
import { getCooperativeId } from "./helpers";

const router = Router();

function stageLabel(type: string) {
  const normalized = type.toLowerCase();
  if (normalized.includes("tri") || normalized.includes("sort")) return "Tri";
  if (normalized.includes("sech") || normalized.includes("dry")) return "Sechage";
  if (normalized.includes("nettoyage") || normalized.includes("clean") || normalized.includes("lavage")) return "Nettoyage";
  if (normalized.includes("condition") || normalized.includes("pack")) return "Conditionnement";
  return "Autre";
}

async function buildDashboard(cooperativeId: string) {
  const cacheKey = `dashboard:${cooperativeId}:overview`;
  const cached = await getCache<unknown>(cacheKey);
  if (cached) return cached;

  const [collectes, steps, lots, stocks, recommendations] = await Promise.all([
    prisma.collecte.findMany({ where: { cooperativeId }, orderBy: { date: "desc" }, take: 100 }),
    prisma.etapeLot.findMany({ where: { lot: { cooperativeId } }, orderBy: { dateDebut: "desc" }, take: 100 }),
    prisma.lot.findMany({ where: { cooperativeId } }),
    prisma.stock.findMany({ where: { cooperativeId } }),
    prisma.recommandationIA.findMany({ where: { cooperativeId }, orderBy: { generatedAt: "desc" }, take: 8 }),
  ]);

  const totalCollecte = collectes.reduce((sum, row) => sum + row.quantiteKg, 0);
  const totalIn = steps.reduce((sum, row) => sum + row.quantiteEntreeKg, 0);
  const totalOut = steps.reduce((sum, row) => sum + row.quantiteSortieKg, 0);
  const totalLoss = steps.reduce((sum, row) => sum + row.perteKg, 0);
  const lossRate = totalIn > 0 ? (totalLoss / totalIn) * 100 : 0;
  const efficiencyRate = totalIn > 0 ? (totalOut / totalIn) * 100 : 0;

  const stockAlerts = stocks
    .filter((row) => row.quantiteActuelleKg <= row.seuilCritiqueKg)
    .map((row) => ({
      stock_id: row.id,
      product_id: row.produitId,
      quantity: row.quantiteActuelleKg,
      threshold: row.seuilCritiqueKg,
      unit: row.unit,
      deficit: Math.max(0, row.seuilCritiqueKg - row.quantiteActuelleKg),
      produit: row.produit,
    }));

  const payload = {
    total_production: Number(totalCollecte.toFixed(2)),
    loss_rate: Number(lossRate.toFixed(2)),
    efficiency_rate: Number(efficiencyRate.toFixed(2)),
    number_of_active_batches: lots.filter((row) => row.statut === LotStatut.ACTIF).length,
    stock_alerts: stockAlerts,
    recent_inputs: collectes.slice(0, 6).map(mapCollecte),
    recent_process_steps: steps.slice(0, 8).map(mapEtape),
    recent_recommendations: recommendations.map(mapRecommendation),
  };

  await setCache(cacheKey, payload, 30);
  return payload;
}

router.use(requireAuth);

router.get(
  "/overview",
  asyncHandler(async (req, res) => {
    const cooperativeId = getCooperativeId(req);
    const payload = await buildDashboard(cooperativeId);
    return ok(res, payload);
  }),
);

router.get(
  "/kpis",
  asyncHandler(async (req, res) => {
    const cooperativeId = getCooperativeId(req);
    const data = (await buildDashboard(cooperativeId)) as {
      total_production: number;
      loss_rate: number;
      efficiency_rate: number;
      number_of_active_batches: number;
      stock_alerts: unknown[];
    };

    return ok(res, {
      total_collecte_kg: data.total_production,
      taux_perte_global: data.loss_rate,
      efficacite_moyenne: data.efficiency_rate,
      lots_actifs: data.number_of_active_batches,
      stocks_critiques: data.stock_alerts.length,
    });
  }),
);

router.get(
  "/activite",
  asyncHandler(async (req, res) => {
    const cooperativeId = getCooperativeId(req);
    const data = (await buildDashboard(cooperativeId)) as {
      recent_inputs: ReturnType<typeof mapCollecte>[];
      recent_process_steps: ReturnType<typeof mapEtape>[];
    };

    const rows = [
      ...data.recent_inputs.map((row) => ({
        id: row.id,
        date: row.date,
        source: `Collecte ${row.produit}`,
        quantity: `${row.quantity.toFixed(1)} kg`,
        status: row.status,
      })),
      ...data.recent_process_steps.map((row) => ({
        id: row.id,
        date: row.date,
        source: `Etape ${stageLabel(row.type)}`,
        quantity: `${row.qty_out.toFixed(1)} kg`,
        status: row.warning ? "ATTENTION" : "OK",
      })),
    ]
      .sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime())
      .slice(0, 6);

    return ok(res, rows);
  }),
);

router.get(
  "/repartition-pertes",
  asyncHandler(async (req, res) => {
    const cooperativeId = getCooperativeId(req);

    const rows = await prisma.etapeLot.findMany({
      where: { lot: { cooperativeId } },
      select: { type: true, perteKg: true },
    });

    const grouped = new Map<string, number>();
    for (const row of rows) {
      const key = stageLabel(row.type);
      grouped.set(key, (grouped.get(key) ?? 0) + row.perteKg);
    }

    const payload = Array.from(grouped.entries()).map(([etape, perte_kg]) => ({ etape, perte_kg }));
    return ok(res, payload);
  }),
);

router.get(
  "/flux-matiere",
  asyncHandler(async (req, res) => {
    const cooperativeId = getCooperativeId(req);
    const lots = await prisma.lot.findMany({
      where: { cooperativeId, statut: LotStatut.ACTIF },
      include: { etapes: { orderBy: { ordre: "asc" } } },
    });

    const payload = lots.map((lot) => {
      const totalIn = lot.etapes.reduce((sum, row) => sum + row.quantiteEntreeKg, 0);
      const totalOut = lot.etapes.reduce((sum, row) => sum + row.quantiteSortieKg, 0);
      const totalLoss = lot.etapes.reduce((sum, row) => sum + row.perteKg, 0);
      const progress = totalIn > 0 ? (totalOut / totalIn) * 100 : 0;
      const lossPct = totalIn > 0 ? (totalLoss / totalIn) * 100 : 0;

      return {
        lot_id: lot.id,
        code: lot.code,
        produit: lot.produit,
        progression_pct: Number(Math.max(0, Math.min(100, progress)).toFixed(2)),
        perte_pct: Number(lossPct.toFixed(2)),
        etapes_total: lot.etapes.length,
        etapes_terminees: lot.etapes.filter((item) => item.statut === EtapeStatut.TERMINE).length,
      };
    });

    return ok(res, payload);
  }),
);

router.get(
  "/recommandation-ia",
  asyncHandler(async (req, res) => {
    const cooperativeId = getCooperativeId(req);
    const rec = await prisma.recommandationIA.findFirst({ where: { cooperativeId }, orderBy: { generatedAt: "desc" } });
    return ok(res, rec ? mapRecommendation(rec) : null);
  }),
);

router.get(
  "/stocks-critiques",
  asyncHandler(async (req, res) => {
    const cooperativeId = getCooperativeId(req);
    const rows = await prisma.stock.findMany({ where: { cooperativeId } });
    const payload = rows
      .filter((row) => row.quantiteActuelleKg <= row.seuilCritiqueKg)
      .map((row) => ({
        id: row.id,
        produit: row.produit,
        quantite_actuelle_kg: row.quantiteActuelleKg,
        seuil_critique_kg: row.seuilCritiqueKg,
      }));

    return ok(res, payload);
  }),
);

export default router;
