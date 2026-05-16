import { Router } from "express";
import { z } from "zod";
import { prisma } from "../lib/prisma";
import { requireAuth } from "../middleware/auth";
import { validate } from "../middleware/validate";
import { asyncHandler, ok } from "../utils/http";
import { mapProduct } from "../utils/mappers";
import { getCooperativeId } from "./helpers";

const router = Router();

const schema = z.object({
  name: z.string().min(2),
  category: z.string().min(2),
  unit: z.string().min(1),
  quality_grade: z.string().optional().nullable(),
  cooperative_id: z.string().uuid().optional(),
});

const updateSchema = schema.partial();

router.use(requireAuth);

router.get(
  "/",
  asyncHandler(async (req, res) => {
    const cooperativeId = getCooperativeId(req);
    const rows = await prisma.produit.findMany({ where: { cooperativeId }, orderBy: { name: "asc" } });
    return ok(res, rows.map(mapProduct));
  }),
);

router.post(
  "/",
  validate(schema),
  asyncHandler(async (req, res) => {
    const payload = req.body as z.infer<typeof schema>;
    const cooperativeId = payload.cooperative_id ?? getCooperativeId(req);

    const row = await prisma.produit.create({
      data: {
        cooperativeId,
        name: payload.name,
        category: payload.category,
        unit: payload.unit,
        qualityGrade: payload.quality_grade,
      },
    });

    return ok(res, mapProduct(row), 201);
  }),
);

router.get(
  "/:id",
  asyncHandler(async (req, res) => {
    const row = await prisma.produit.findUnique({ where: { id: String(req.params.id) } });
    return ok(res, row ? mapProduct(row) : null);
  }),
);

router.patch(
  "/:id",
  validate(updateSchema),
  asyncHandler(async (req, res) => {
    const payload = req.body as z.infer<typeof updateSchema>;
    const row = await prisma.produit.update({
      where: { id: String(req.params.id) },
      data: {
        name: payload.name,
        category: payload.category,
        unit: payload.unit,
        qualityGrade: payload.quality_grade,
      },
    });

    return ok(res, mapProduct(row));
  }),
);

router.delete(
  "/:id",
  asyncHandler(async (req, res) => {
    const row = await prisma.produit.delete({ where: { id: String(req.params.id) } });
    return ok(res, mapProduct(row));
  }),
);

export default router;
