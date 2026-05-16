import { Router } from "express";
import { prisma } from "../lib/prisma";
import { requireAuth } from "../middleware/auth";
import { asyncHandler, ok } from "../utils/http";

const router = Router();

router.use(requireAuth);

router.get(
  "/metrics",
  asyncHandler(async (req, res) => {
    const q = typeof req.query.q === "string" ? req.query.q.trim() : "";
    const limit = Math.min(Number(req.query.limit ?? 20) || 20, 50);

    const where = q
      ? {
          OR: [
            { crop: { contains: q, mode: "insensitive" as const } },
            { region: { contains: q, mode: "insensitive" as const } },
            { metric: { contains: q, mode: "insensitive" as const } },
            { notes: { contains: q, mode: "insensitive" as const } },
          ],
        }
      : {};

    const [items, total] = await Promise.all([
      prisma.referenceMetric.findMany({ where, orderBy: { createdAt: "desc" }, take: limit }),
      prisma.referenceMetric.count({ where }),
    ]);

    return ok(res, {
      total,
      items: items.map((item) => ({
        id: item.id,
        source_id: item.sourceId,
        country: item.country,
        region: item.region,
        crop: item.crop,
        metric: item.metric,
        period: item.period,
        value: item.value,
        unit: item.unit,
        notes: item.notes,
      })),
    });
  }),
);

router.get(
  "/knowledge",
  asyncHandler(async (req, res) => {
    const q = typeof req.query.q === "string" ? req.query.q.trim() : "";
    const limit = Math.min(Number(req.query.limit ?? 20) || 20, 50);

    const where = q
      ? {
          OR: [
            { crop: { contains: q, mode: "insensitive" as const } },
            { region: { contains: q, mode: "insensitive" as const } },
            { topic: { contains: q, mode: "insensitive" as const } },
            { content: { contains: q, mode: "insensitive" as const } },
          ],
        }
      : {};

    const [items, total] = await Promise.all([
      prisma.knowledgeChunk.findMany({ where, orderBy: { createdAt: "desc" }, take: limit }),
      prisma.knowledgeChunk.count({ where }),
    ]);

    return ok(res, {
      total,
      items: items.map((item) => ({
        id: item.id,
        source_id: item.sourceId,
        source_url: item.sourceUrl,
        country: item.country,
        region: item.region,
        crop: item.crop,
        topic: item.topic,
        content: item.content,
      })),
    });
  }),
);

export default router;
