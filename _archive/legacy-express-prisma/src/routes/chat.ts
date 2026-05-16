import { Router } from "express";
import { z } from "zod";
import { prisma } from "../lib/prisma";
import { requireAuth } from "../middleware/auth";
import { validate } from "../middleware/validate";
import { asyncHandler, ok } from "../utils/http";
import { getCooperativeId } from "./helpers";

const router = Router();

const schema = z.object({
  message: z.string().min(3),
  top_k: z.number().int().min(1).max(10).optional(),
});

async function buildDashboardSnapshot(cooperativeId: string) {
  const [collectes, steps, lots, stocks, coop] = await Promise.all([
    prisma.collecte.findMany({ where: { cooperativeId }, take: 60 }),
    prisma.etapeLot.findMany({ where: { lot: { cooperativeId } }, take: 60 }),
    prisma.lot.findMany({ where: { cooperativeId, statut: "ACTIF" } }),
    prisma.stock.findMany({ where: { cooperativeId } }),
    prisma.cooperative.findUnique({ where: { id: cooperativeId } }),
  ]);

  const totalCollecte = collectes.reduce((sum, row) => sum + row.quantiteKg, 0);
  const totalIn = steps.reduce((sum, row) => sum + row.quantiteEntreeKg, 0);
  const totalOut = steps.reduce((sum, row) => sum + row.quantiteSortieKg, 0);
  const totalLoss = steps.reduce((sum, row) => sum + row.perteKg, 0);

  return {
    cooperative_name: coop?.name ?? null,
    region: coop?.region ?? null,
    total_production: Number(totalCollecte.toFixed(2)),
    loss_rate: totalIn > 0 ? Number(((totalLoss / totalIn) * 100).toFixed(2)) : 0,
    efficiency_rate: totalIn > 0 ? Number(((totalOut / totalIn) * 100).toFixed(2)) : 0,
    number_of_active_batches: lots.length,
    stock_alerts: stocks.filter((item) => item.quantiteActuelleKg <= item.seuilCritiqueKg).length,
  };
}

async function callClaude(prompt: string) {
  const key = process.env.CLAUDE_API_KEY;
  if (!key) return null;

  const model = process.env.CLAUDE_MODEL || "claude-3-5-sonnet-20241022";

  const response = await fetch("https://api.anthropic.com/v1/messages", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "x-api-key": key,
      "anthropic-version": "2023-06-01",
    },
    body: JSON.stringify({
      model,
      max_tokens: 500,
      temperature: 0.2,
      messages: [{ role: "user", content: prompt }],
    }),
  });

  if (!response.ok) return null;
  const data = (await response.json()) as { content?: Array<{ type: string; text?: string }> };
  const text = data.content?.find((item) => item.type === "text")?.text?.trim();
  return text || null;
}

router.use(requireAuth);

router.post(
  "/",
  validate(schema),
  asyncHandler(async (req, res) => {
    const { message, top_k } = req.body as z.infer<typeof schema>;
    const cooperativeId = getCooperativeId(req);

    const limit = top_k ?? 4;

    const [metrics, chunks, dashboard] = await Promise.all([
      prisma.referenceMetric.findMany({ orderBy: { createdAt: "desc" }, take: limit }),
      prisma.knowledgeChunk.findMany({ orderBy: { createdAt: "desc" }, take: limit }),
      buildDashboardSnapshot(cooperativeId),
    ]);

    const grounded = chunks.length > 0 || metrics.length > 0;

    const fallbackMessage = [
      `Analyse operationnelle pour: \"${message}\".`,
      `Perte globale: ${dashboard.loss_rate.toFixed(1)}%, efficacite: ${dashboard.efficiency_rate.toFixed(1)}%.`,
      dashboard.stock_alerts > 0
        ? `Priorite: ${dashboard.stock_alerts} stock(s) critique(s) a traiter.`
        : "Aucune alerte critique stock detectee.",
      "Action recommandee: maintenir le suivi quotidien des etapes a plus forte perte et controler l'humidite.",
    ].join(" ");

    const prompt = `Tu es assistant agricole WeeFarm. Reponds en francais, style operationnel court.\nQuestion: ${message}\nDashboard: ${JSON.stringify(
      dashboard,
    )}\nMetriques: ${JSON.stringify(metrics)}\nKnowledge: ${JSON.stringify(chunks.map((c) => c.content))}`;

    const llmText = await callClaude(prompt);

    return ok(res, {
      success: true,
      message: llmText ?? fallbackMessage,
      grounded,
      mode: llmText ? "llm" : "fallback",
      citations: chunks.map((item) => ({
        source_id: item.sourceId,
        source_url: item.sourceUrl,
        region: item.region,
        crop: item.crop,
        topic: item.topic,
        excerpt: item.content.slice(0, 200),
      })),
      context_metrics: metrics.map((item) => ({
        source_id: item.sourceId,
        region: item.region,
        crop: item.crop,
        metric: item.metric,
        period: item.period,
        value: item.value,
        unit: item.unit,
        notes: item.notes,
      })),
      dashboard,
    });
  }),
);

export default router;
