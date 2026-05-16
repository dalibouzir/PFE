import { Router } from "express";
import { z } from "zod";
import { prisma } from "../lib/prisma";
import { requireAuth } from "../middleware/auth";
import { validate } from "../middleware/validate";
import { ApiError, asyncHandler, ok } from "../utils/http";
import { mapEtape } from "../utils/mappers";
import { getCooperativeId } from "./helpers";

const router = Router();

const schema = z.object({
  batch_id: z.string().uuid(),
  type: z.string().min(2),
  date: z.string(),
  qty_in: z.number().min(0),
  qty_out: z.number().min(0),
  waste_qty: z.number().min(0).optional().nullable(),
  notes: z.string().optional().nullable(),
  status: z.string().optional(),
  duration_minutes: z.number().int().optional().nullable(),
});

const updateSchema = schema.partial();

router.use(requireAuth);

router.get(
  "/",
  asyncHandler(async (req, res) => {
    const cooperativeId = getCooperativeId(req);
    const rows = await prisma.etapeLot.findMany({
      where: { lot: { cooperativeId } },
      orderBy: [{ dateDebut: "desc" }, { ordre: "asc" }],
    });
    return ok(res, rows.map(mapEtape));
  }),
);

router.post(
  "/",
  validate(schema),
  asyncHandler(async (req, res) => {
    const payload = req.body as z.infer<typeof schema>;
    const lot = await prisma.lot.findUnique({ where: { id: payload.batch_id } });
    if (!lot) throw new ApiError(404, "Lot introuvable");

    const perte = payload.waste_qty ?? Math.max(payload.qty_in - payload.qty_out, 0);

    const count = await prisma.etapeLot.count({ where: { lotId: payload.batch_id } });
    const created = await prisma.etapeLot.create({
      data: {
        lotId: payload.batch_id,
        nomEtape: payload.type,
        type: payload.type,
        ordre: count + 1,
        quantiteEntreeKg: payload.qty_in,
        quantiteSortieKg: payload.qty_out,
        perteKg: perte,
        statut: payload.status?.toLowerCase().includes("complete") ? "TERMINE" : "EN_COURS",
        dateDebut: new Date(payload.date),
        dateFin: payload.status?.toLowerCase().includes("complete") ? new Date(payload.date) : null,
        notes: payload.notes,
      },
    });

    await prisma.lot.update({ where: { id: payload.batch_id }, data: { quantiteActuelleKg: payload.qty_out } });

    return ok(res, mapEtape(created), 201);
  }),
);

router.get(
  "/:id",
  asyncHandler(async (req, res) => {
    const row = await prisma.etapeLot.findUnique({ where: { id: String(req.params.id) } });
    if (!row) throw new ApiError(404, "Etape introuvable");
    return ok(res, mapEtape(row));
  }),
);

router.patch(
  "/:id",
  validate(updateSchema),
  asyncHandler(async (req, res) => {
    const payload = req.body as z.infer<typeof updateSchema>;
    const existing = await prisma.etapeLot.findUnique({ where: { id: String(req.params.id) } });
    if (!existing) throw new ApiError(404, "Etape introuvable");

    const qtyIn = payload.qty_in ?? existing.quantiteEntreeKg;
    const qtyOut = payload.qty_out ?? existing.quantiteSortieKg;
    const waste = payload.waste_qty ?? Math.max(qtyIn - qtyOut, 0);

    const updated = await prisma.etapeLot.update({
      where: { id: String(req.params.id) },
      data: {
        nomEtape: payload.type,
        type: payload.type,
        dateDebut: payload.date ? new Date(payload.date) : undefined,
        quantiteEntreeKg: qtyIn,
        quantiteSortieKg: qtyOut,
        perteKg: waste,
        notes: payload.notes,
        statut: payload.status ? (payload.status.toLowerCase().includes("complete") ? "TERMINE" : "EN_COURS") : undefined,
      },
    });

    await prisma.lot.update({ where: { id: updated.lotId }, data: { quantiteActuelleKg: qtyOut } });

    return ok(res, mapEtape(updated));
  }),
);

router.patch(
  "/:id/complete",
  asyncHandler(async (req, res) => {
    const updated = await prisma.etapeLot.update({
      where: { id: String(req.params.id) },
      data: { statut: "TERMINE", dateFin: new Date() },
    });

    return ok(res, mapEtape(updated));
  }),
);

router.delete(
  "/:id",
  asyncHandler(async (req, res) => {
    const deleted = await prisma.etapeLot.delete({ where: { id: String(req.params.id) } });
    return ok(res, mapEtape(deleted));
  }),
);

export default router;
