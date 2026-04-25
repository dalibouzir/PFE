import { RecommandationStatut } from "@prisma/client";
import { Router } from "express";
import { z } from "zod";
import { prisma } from "../lib/prisma";
import { requireAuth } from "../middleware/auth";
import { asyncHandler, ok } from "../utils/http";
import { mapRecommendation } from "../utils/mappers";
import { getCooperativeId } from "./helpers";

const router = Router();

const generateSchema = z.object({
  cooperative_id: z.string().uuid().optional(),
});

router.use(requireAuth);

router.get(
  "/recommandation",
  asyncHandler(async (req, res) => {
    const cooperativeId = getCooperativeId(req);
    const row = await prisma.recommandationIA.findFirst({ where: { cooperativeId }, orderBy: { generatedAt: "desc" } });
    return ok(res, row ? mapRecommendation(row) : null);
  }),
);

router.post(
  "/generate",
  asyncHandler(async (req, res) => {
    const parsed = generateSchema.parse(req.body ?? {});
    const cooperativeId = parsed.cooperative_id ?? getCooperativeId(req);

    const [stocks, stages, collectes] = await Promise.all([
      prisma.stock.findMany({ where: { cooperativeId } }),
      prisma.etapeLot.findMany({ where: { lot: { cooperativeId } }, orderBy: { dateDebut: "desc" }, take: 30 }),
      prisma.collecte.findMany({ where: { cooperativeId }, orderBy: { date: "desc" }, take: 30 }),
    ]);

    const criticalStocks = stocks.filter((item) => item.quantiteActuelleKg <= item.seuilCritiqueKg).length;
    const avgLoss =
      stages.length > 0
        ? stages.reduce((sum, stage) => {
            if (stage.quantiteEntreeKg <= 0) return sum;
            return sum + (stage.perteKg / stage.quantiteEntreeKg) * 100;
          }, 0) / stages.length
        : 0;
    const recentCollecte = collectes.reduce((sum, item) => sum + item.quantiteKg, 0);

    let statut: RecommandationStatut = RecommandationStatut.STABLE;
    let texte = "Aucune action critique. Maintenir le process actuel.";
    let rationale = "Les indicateurs production/pertes sont stables.";

    if (criticalStocks > 1 || avgLoss > 12) {
      statut = RecommandationStatut.CRITIQUE;
      texte = "Action rapide conseillee: reduire pertes sur etapes critiques et reapprovisionner les stocks sensibles.";
      rationale = `Stocks critiques=${criticalStocks}, perte moyenne=${avgLoss.toFixed(1)}%.`;
    } else if (criticalStocks > 0 || avgLoss > 7) {
      statut = RecommandationStatut.ATTENTION;
      texte = "Ajuster le suivi qualite et renforcer la supervision sur les etapes de transformation.";
      rationale = `Signal modere: stocks critiques=${criticalStocks}, perte moyenne=${avgLoss.toFixed(1)}%.`;
    } else if (recentCollecte > 0) {
      texte = "Aucune action critique. Maintenir le process actuel.";
      rationale = `Collecte recente ${recentCollecte.toFixed(0)} kg avec pertes controlees.`;
    }

    const created = await prisma.recommandationIA.create({
      data: {
        cooperativeId,
        texte,
        statut,
        rationale,
        expectedImpact: statut === RecommandationStatut.STABLE ? "+0.5 pt efficacite" : "Reduction des pertes attendue",
        generatedAt: new Date(),
      },
    });

    return ok(res, mapRecommendation(created), 201);
  }),
);

export default router;
