import { Router } from "express";
import { z } from "zod";
import { prisma } from "../lib/prisma";
import { invalidateByPrefix } from "../lib/redis";
import { requireAuth } from "../middleware/auth";
import { validate } from "../middleware/validate";
import { emitDashboardUpdate } from "../socket/io";
import { ApiError, asyncHandler, ok } from "../utils/http";
import { mapStock } from "../utils/mappers";
import { getCooperativeId } from "./helpers";

const router = Router();

const createSchema = z.object({
  product_id: z.string().uuid().optional().nullable(),
  produit: z.string().optional(),
  quantity: z.number().min(0),
  threshold: z.number().min(0),
  quantity_max: z.number().min(0).optional(),
  unit: z.string().optional(),
  cooperative_id: z.string().uuid().optional(),
});

const updateSchema = z.object({
  quantity: z.number().min(0).optional(),
  threshold: z.number().min(0).optional(),
  quantity_max: z.number().min(0).optional(),
  unit: z.string().optional(),
  produit: z.string().optional(),
});

const adjustSchema = z.object({ amount: z.number().positive() });

router.use(requireAuth);

router.get(
  "/",
  asyncHandler(async (req, res) => {
    const cooperativeId = getCooperativeId(req);
    const rows = await prisma.stock.findMany({ where: { cooperativeId }, orderBy: { updatedAt: "desc" } });

    const payload = rows.map((row) => {
      const fillPercent = row.quantiteMaxKg > 0 ? (row.quantiteActuelleKg / row.quantiteMaxKg) * 100 : 0;
      const critical = row.quantiteActuelleKg <= row.seuilCritiqueKg;
      return {
        ...mapStock(row),
        fill_percent: Number(Math.max(0, Math.min(fillPercent, 100)).toFixed(2)),
        alert_status: critical ? "CRITIQUE" : "NORMAL",
      };
    });

    return ok(res, payload);
  }),
);

router.post(
  "/",
  validate(createSchema),
  asyncHandler(async (req, res) => {
    const payload = req.body as z.infer<typeof createSchema>;
    const cooperativeId = payload.cooperative_id ?? getCooperativeId(req);

    let produit = payload.produit;
    if (!produit && payload.product_id) {
      const product = await prisma.produit.findUnique({ where: { id: payload.product_id } });
      produit = product?.name;
    }

    if (!produit) throw new ApiError(400, "produit requis");

    const created = await prisma.stock.create({
      data: {
        cooperativeId,
        produitId: payload.product_id,
        produit,
        quantiteActuelleKg: payload.quantity,
        seuilCritiqueKg: payload.threshold,
        quantiteMaxKg: payload.quantity_max ?? Math.max(payload.quantity, payload.threshold) * 2,
        unit: payload.unit ?? "kg",
      },
    });

    await invalidateByPrefix(`dashboard:${cooperativeId}`);
    emitDashboardUpdate("stocks:updated", { cooperativeId, stockId: created.id });

    return ok(res, mapStock(created), 201);
  }),
);

router.put(
  "/:id",
  validate(updateSchema),
  asyncHandler(async (req, res) => {
    const payload = req.body as z.infer<typeof updateSchema>;
    const existing = await prisma.stock.findUnique({ where: { id: String(req.params.id) } });
    if (!existing) throw new ApiError(404, "Stock introuvable");

    const updated = await prisma.stock.update({
      where: { id: String(req.params.id) },
      data: {
        quantiteActuelleKg: payload.quantity,
        seuilCritiqueKg: payload.threshold,
        quantiteMaxKg: payload.quantity_max,
        unit: payload.unit,
        produit: payload.produit,
        lastUpdated: new Date(),
      },
    });

    await invalidateByPrefix(`dashboard:${existing.cooperativeId}`);
    emitDashboardUpdate("stocks:updated", { cooperativeId: existing.cooperativeId, stockId: updated.id });

    return ok(res, mapStock(updated));
  }),
);

router.patch(
  "/:id",
  validate(updateSchema),
  asyncHandler(async (req, res) => {
    const payload = req.body as z.infer<typeof updateSchema>;
    const existing = await prisma.stock.findUnique({ where: { id: String(req.params.id) } });
    if (!existing) throw new ApiError(404, "Stock introuvable");

    const updated = await prisma.stock.update({
      where: { id: String(req.params.id) },
      data: {
        quantiteActuelleKg: payload.quantity,
        seuilCritiqueKg: payload.threshold,
        quantiteMaxKg: payload.quantity_max,
        unit: payload.unit,
        produit: payload.produit,
        lastUpdated: new Date(),
      },
    });

    await invalidateByPrefix(`dashboard:${existing.cooperativeId}`);
    emitDashboardUpdate("stocks:updated", { cooperativeId: existing.cooperativeId, stockId: updated.id });

    return ok(res, mapStock(updated));
  }),
);

router.post(
  "/:id/increase",
  validate(adjustSchema),
  asyncHandler(async (req, res) => {
    const { amount } = req.body as z.infer<typeof adjustSchema>;
    const existing = await prisma.stock.findUnique({ where: { id: String(req.params.id) } });
    if (!existing) throw new ApiError(404, "Stock introuvable");

    const updated = await prisma.stock.update({
      where: { id: String(req.params.id) },
      data: {
        quantiteActuelleKg: existing.quantiteActuelleKg + amount,
        lastUpdated: new Date(),
      },
    });

    await invalidateByPrefix(`dashboard:${existing.cooperativeId}`);
    emitDashboardUpdate("stocks:updated", { cooperativeId: existing.cooperativeId, stockId: updated.id });
    return ok(res, mapStock(updated));
  }),
);

router.post(
  "/:id/decrease",
  validate(adjustSchema),
  asyncHandler(async (req, res) => {
    const { amount } = req.body as z.infer<typeof adjustSchema>;
    const existing = await prisma.stock.findUnique({ where: { id: String(req.params.id) } });
    if (!existing) throw new ApiError(404, "Stock introuvable");

    const updated = await prisma.stock.update({
      where: { id: String(req.params.id) },
      data: {
        quantiteActuelleKg: Math.max(0, existing.quantiteActuelleKg - amount),
        lastUpdated: new Date(),
      },
    });

    await invalidateByPrefix(`dashboard:${existing.cooperativeId}`);
    emitDashboardUpdate("stocks:updated", { cooperativeId: existing.cooperativeId, stockId: updated.id });
    return ok(res, mapStock(updated));
  }),
);

router.delete(
  "/:id",
  asyncHandler(async (req, res) => {
    const deleted = await prisma.stock.delete({ where: { id: String(req.params.id) } });
    await invalidateByPrefix(`dashboard:${deleted.cooperativeId}`);
    emitDashboardUpdate("stocks:updated", { cooperativeId: deleted.cooperativeId, stockId: deleted.id });
    return ok(res, mapStock(deleted));
  }),
);

export default router;
