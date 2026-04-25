import { Router } from "express";
import { z } from "zod";
import { prisma } from "../lib/prisma";
import { requireAuth } from "../middleware/auth";
import { validate } from "../middleware/validate";
import { ApiError, asyncHandler, ok } from "../utils/http";
import { mapLot } from "../utils/mappers";
import { getCooperativeId } from "./helpers";

const router = Router();

const schema = z.object({
  product_id: z.string().uuid().optional().nullable(),
  code: z.string().min(3),
  creation_date: z.string(),
  initial_qty: z.number().positive(),
  produit: z.string().optional(),
  cooperative_id: z.string().uuid().optional(),
});

const updateSchema = schema.partial();

router.use(requireAuth);

router.get(
  "/",
  asyncHandler(async (req, res) => {
    const cooperativeId = getCooperativeId(req);
    const rows = await prisma.lot.findMany({ where: { cooperativeId }, orderBy: { creationDate: "desc" } });
    return ok(res, rows.map(mapLot));
  }),
);

router.post(
  "/",
  validate(schema),
  asyncHandler(async (req, res) => {
    const payload = req.body as z.infer<typeof schema>;
    const cooperativeId = payload.cooperative_id ?? getCooperativeId(req);

    let produit = payload.produit;
    if (!produit && payload.product_id) {
      const product = await prisma.produit.findUnique({ where: { id: payload.product_id } });
      produit = product?.name;
    }
    if (!produit) throw new ApiError(400, "produit requis");

    const created = await prisma.lot.create({
      data: {
        cooperativeId,
        productId: payload.product_id,
        code: payload.code,
        produit,
        quantiteInitialeKg: payload.initial_qty,
        quantiteActuelleKg: payload.initial_qty,
        creationDate: new Date(payload.creation_date),
        createdByUserId: req.auth?.userId,
      },
    });

    return ok(res, mapLot(created), 201);
  }),
);

router.get(
  "/:id",
  asyncHandler(async (req, res) => {
    const row = await prisma.lot.findUnique({ where: { id: String(req.params.id) } });
    if (!row) throw new ApiError(404, "Lot introuvable");
    return ok(res, mapLot(row));
  }),
);

router.patch(
  "/:id",
  validate(updateSchema),
  asyncHandler(async (req, res) => {
    const payload = req.body as z.infer<typeof updateSchema>;
    const row = await prisma.lot.update({
      where: { id: String(req.params.id) },
      data: {
        code: payload.code,
        productId: payload.product_id,
        produit: payload.produit,
        quantiteInitialeKg: payload.initial_qty,
        creationDate: payload.creation_date ? new Date(payload.creation_date) : undefined,
      },
    });
    return ok(res, mapLot(row));
  }),
);

router.patch(
  "/:id/status",
  validate(z.object({ status: z.string() })),
  asyncHandler(async (req, res) => {
    const status = String(req.body.status || "").toLowerCase();
    const row = await prisma.lot.update({
      where: { id: String(req.params.id) },
      data: {
        statut: status === "completed" || status === "termine" ? "TERMINE" : "ACTIF",
      },
    });
    return ok(res, mapLot(row));
  }),
);

router.delete(
  "/:id",
  asyncHandler(async (req, res) => {
    const deleted = await prisma.lot.delete({ where: { id: String(req.params.id) } });
    return ok(res, mapLot(deleted));
  }),
);

export default router;
