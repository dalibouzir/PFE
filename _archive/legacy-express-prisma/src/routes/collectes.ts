import { Router } from "express";
import { CollecteStatut } from "@prisma/client";
import { z } from "zod";
import { prisma } from "../lib/prisma";
import { invalidateByPrefix } from "../lib/redis";
import { requireAuth } from "../middleware/auth";
import { validate } from "../middleware/validate";
import { emitDashboardUpdate } from "../socket/io";
import { ApiError, asyncHandler, ok } from "../utils/http";
import { mapCollecte } from "../utils/mappers";
import { getCooperativeId, parsePagination } from "./helpers";

const router = Router();

const schema = z.object({
  membre_id: z.string().uuid().optional(),
  member_id: z.string().uuid().optional(),
  product_id: z.string().uuid().optional().nullable(),
  produit: z.string().optional(),
  date: z.string(),
  quantity: z.number().positive(),
  grade: z.string().optional(),
  estimated_value: z.number().optional().nullable(),
  status: z.enum(["VALIDE", "EN_ATTENTE"]).optional(),
  cooperative_id: z.string().uuid().optional(),
  agent_id: z.string().uuid().optional().nullable(),
});

const updateSchema = z.object({
  date: z.string().optional(),
  quantity: z.number().positive().optional(),
  grade: z.string().optional(),
  estimated_value: z.number().optional().nullable(),
  status: z.enum(["VALIDE", "EN_ATTENTE"]).optional(),
  produit: z.string().optional(),
});

router.use(requireAuth);

router.get(
  "/",
  asyncHandler(async (req, res) => {
    const cooperativeId = getCooperativeId(req);
    const { skip, take, page, pageSize } = parsePagination(req);
    const produit = typeof req.query.produit === "string" ? req.query.produit : undefined;
    const statut = typeof req.query.statut === "string" ? req.query.statut : undefined;
    const dateFrom = typeof req.query.date_from === "string" ? new Date(req.query.date_from) : undefined;
    const dateTo = typeof req.query.date_to === "string" ? new Date(req.query.date_to) : undefined;

    const where = {
      cooperativeId,
      ...(produit ? { produit: { contains: produit, mode: "insensitive" as const } } : {}),
      ...(statut ? { statut: statut === "VALIDE" ? CollecteStatut.VALIDE : CollecteStatut.EN_ATTENTE } : {}),
      ...(dateFrom || dateTo
        ? {
            date: {
              ...(dateFrom ? { gte: dateFrom } : {}),
              ...(dateTo ? { lte: dateTo } : {}),
            },
          }
        : {}),
    };

    const [rows, total] = await Promise.all([
      prisma.collecte.findMany({ where, orderBy: { date: "desc" }, skip, take }),
      prisma.collecte.count({ where }),
    ]);

    return ok(res, {
      items: rows.map(mapCollecte),
      total,
      page,
      page_size: pageSize,
    });
  }),
);

router.post(
  "/",
  validate(schema),
  asyncHandler(async (req, res) => {
    const payload = req.body as z.infer<typeof schema>;
    const cooperativeId = payload.cooperative_id ?? getCooperativeId(req);
    const memberId = payload.member_id ?? payload.membre_id;
    if (!memberId) {
      throw new ApiError(400, "member_id requis");
    }

    let produit = payload.produit;
    if (!produit && payload.product_id) {
      const product = await prisma.produit.findUnique({ where: { id: payload.product_id } });
      produit = product?.name;
    }

    if (!produit) {
      throw new ApiError(400, "produit requis");
    }

    const row = await prisma.collecte.create({
      data: {
        cooperativeId,
        membreId: memberId,
        produitId: payload.product_id,
        produit,
        date: new Date(payload.date),
        quantiteKg: payload.quantity,
        grade: payload.grade ?? "A",
        estimatedValueFcfa: payload.estimated_value ?? null,
        statut: payload.status === "VALIDE" ? CollecteStatut.VALIDE : CollecteStatut.EN_ATTENTE,
        agentId: payload.agent_id ?? req.auth?.userId ?? null,
      },
    });

    await invalidateByPrefix(`dashboard:${cooperativeId}`);
    emitDashboardUpdate("collecte:new", { cooperativeId, collecteId: row.id });

    return ok(res, mapCollecte(row), 201);
  }),
);

router.get(
  "/:id",
  asyncHandler(async (req, res) => {
    const row = await prisma.collecte.findUnique({ where: { id: String(req.params.id) } });
    if (!row) throw new ApiError(404, "Collecte introuvable");
    return ok(res, mapCollecte(row));
  }),
);

router.put(
  "/:id",
  validate(updateSchema),
  asyncHandler(async (req, res) => {
    const payload = req.body as z.infer<typeof updateSchema>;
    const existing = await prisma.collecte.findUnique({ where: { id: String(req.params.id) } });
    if (!existing) throw new ApiError(404, "Collecte introuvable");

    const row = await prisma.collecte.update({
      where: { id: String(req.params.id) },
      data: {
        date: payload.date ? new Date(payload.date) : undefined,
        quantiteKg: payload.quantity,
        grade: payload.grade,
        estimatedValueFcfa: payload.estimated_value,
        statut:
          payload.status === undefined
            ? undefined
            : payload.status === "VALIDE"
              ? CollecteStatut.VALIDE
              : CollecteStatut.EN_ATTENTE,
        produit: payload.produit,
      },
    });

    await invalidateByPrefix(`dashboard:${existing.cooperativeId}`);
    emitDashboardUpdate("collecte:updated", { cooperativeId: existing.cooperativeId, collecteId: row.id });

    return ok(res, mapCollecte(row));
  }),
);

router.patch(
  "/:id",
  validate(updateSchema),
  asyncHandler(async (req, res) => {
    const payload = req.body as z.infer<typeof updateSchema>;
    const existing = await prisma.collecte.findUnique({ where: { id: String(req.params.id) } });
    if (!existing) throw new ApiError(404, "Collecte introuvable");

    const row = await prisma.collecte.update({
      where: { id: String(req.params.id) },
      data: {
        date: payload.date ? new Date(payload.date) : undefined,
        quantiteKg: payload.quantity,
        grade: payload.grade,
        estimatedValueFcfa: payload.estimated_value,
        statut:
          payload.status === undefined
            ? undefined
            : payload.status === "VALIDE"
              ? CollecteStatut.VALIDE
              : CollecteStatut.EN_ATTENTE,
        produit: payload.produit,
      },
    });

    await invalidateByPrefix(`dashboard:${existing.cooperativeId}`);
    emitDashboardUpdate("collecte:updated", { cooperativeId: existing.cooperativeId, collecteId: row.id });

    return ok(res, mapCollecte(row));
  }),
);

router.delete(
  "/:id",
  asyncHandler(async (req, res) => {
    const existing = await prisma.collecte.findUnique({ where: { id: String(req.params.id) } });
    if (!existing) throw new ApiError(404, "Collecte introuvable");

    const deleted = await prisma.collecte.delete({ where: { id: String(req.params.id) } });
    await invalidateByPrefix(`dashboard:${existing.cooperativeId}`);
    emitDashboardUpdate("collecte:updated", { cooperativeId: existing.cooperativeId, collecteId: deleted.id });
    return ok(res, mapCollecte(deleted));
  }),
);

export default router;
