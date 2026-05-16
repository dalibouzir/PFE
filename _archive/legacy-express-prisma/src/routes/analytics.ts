import { Router } from "express";
import { prisma } from "../lib/prisma";
import { requireAuth } from "../middleware/auth";
import { asyncHandler, ok } from "../utils/http";
import { mapEtape, mapRecommendation } from "../utils/mappers";
import { getCooperativeId } from "./helpers";

const router = Router();

router.use(requireAuth);

router.get(
  "/dashboard",
  asyncHandler(async (req, res) => {
    const cooperativeId = getCooperativeId(req);

    const [collectes, steps, lots, stocks, recommendations] = await Promise.all([
      prisma.collecte.findMany({ where: { cooperativeId }, orderBy: { date: "desc" }, take: 50 }),
      prisma.etapeLot.findMany({ where: { lot: { cooperativeId } }, orderBy: { dateDebut: "desc" }, take: 50 }),
      prisma.lot.findMany({ where: { cooperativeId } }),
      prisma.stock.findMany({ where: { cooperativeId } }),
      prisma.recommandationIA.findMany({ where: { cooperativeId }, orderBy: { generatedAt: "desc" }, take: 6 }),
    ]);

    const totalProduction = collectes.reduce((sum, item) => sum + item.quantiteKg, 0);
    const totalIn = steps.reduce((sum, item) => sum + item.quantiteEntreeKg, 0);
    const totalOut = steps.reduce((sum, item) => sum + item.quantiteSortieKg, 0);
    const totalLoss = steps.reduce((sum, item) => sum + item.perteKg, 0);

    return ok(res, {
      total_production: Number(totalProduction.toFixed(2)),
      loss_rate: totalIn > 0 ? Number(((totalLoss / totalIn) * 100).toFixed(2)) : 0,
      efficiency_rate: totalIn > 0 ? Number(((totalOut / totalIn) * 100).toFixed(2)) : 0,
      number_of_active_batches: lots.filter((item) => item.statut === "ACTIF").length,
      stock_alerts: stocks
        .filter((item) => item.quantiteActuelleKg <= item.seuilCritiqueKg)
        .map((item) => ({
          stock_id: item.id,
          product_id: item.produitId,
          quantity: item.quantiteActuelleKg,
          threshold: item.seuilCritiqueKg,
          unit: item.unit,
          deficit: Math.max(0, item.seuilCritiqueKg - item.quantiteActuelleKg),
        })),
      recent_inputs: collectes.slice(0, 8).map((item) => ({
        id: item.id,
        cooperative_id: item.cooperativeId,
        member_id: item.membreId,
        product_id: item.produitId,
        date: item.date.toISOString().slice(0, 10),
        quantity: item.quantiteKg,
        grade: item.grade,
        estimated_value: item.estimatedValueFcfa,
        status: item.statut,
        created_at: item.createdAt.toISOString(),
        updated_at: item.updatedAt.toISOString(),
      })),
      recent_process_steps: steps.slice(0, 10).map(mapEtape),
      recent_recommendations: recommendations.map(mapRecommendation),
    });
  }),
);

router.get(
  "/batches/:id/metrics",
  asyncHandler(async (req, res) => {
    const batch = await prisma.lot.findUnique({ where: { id: String(req.params.id) }, include: { etapes: true } });
    if (!batch) return ok(res, null);

    const totalIn = batch.etapes.reduce((sum, item) => sum + item.quantiteEntreeKg, 0);
    const totalOut = batch.etapes.reduce((sum, item) => sum + item.quantiteSortieKg, 0);
    const totalLoss = batch.etapes.reduce((sum, item) => sum + item.perteKg, 0);

    return ok(res, {
      batch_id: batch.id,
      total_in: totalIn,
      total_out: totalOut,
      total_loss: totalLoss,
      loss_rate: totalIn > 0 ? (totalLoss / totalIn) * 100 : 0,
      efficiency_rate: totalIn > 0 ? (totalOut / totalIn) * 100 : 0,
      stages: batch.etapes.map(mapEtape),
    });
  }),
);

router.get(
  "/batches/:id/anomaly",
  asyncHandler(async (req, res) => {
    const steps = await prisma.etapeLot.findMany({ where: { lotId: String(req.params.id) } });
    if (steps.length === 0) return ok(res, { anomaly_detected: false, anomaly_score: 0 });

    const avgLoss =
      steps.reduce((sum, step) => {
        if (step.quantiteEntreeKg <= 0) return sum;
        return sum + (step.perteKg / step.quantiteEntreeKg) * 100;
      }, 0) / steps.length;

    const anomalyScore = Math.min(100, Math.round(avgLoss * 7));
    return ok(res, {
      anomaly_detected: anomalyScore >= 45,
      anomaly_score: anomalyScore,
      risk_level: anomalyScore >= 70 ? "high" : anomalyScore >= 45 ? "medium" : "low",
    });
  }),
);

router.get(
  "/batches/:id/recommendation",
  asyncHandler(async (req, res) => {
    const rec = await prisma.recommandationIA.findFirst({
      where: { lotId: String(req.params.id) },
      orderBy: { generatedAt: "desc" },
    });

    return ok(res, rec ? mapRecommendation(rec) : null);
  }),
);

export default router;
