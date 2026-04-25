import { Router } from "express";
import { z } from "zod";
import { prisma } from "../lib/prisma";
import { requireAuth } from "../middleware/auth";
import { validate } from "../middleware/validate";
import { asyncHandler, ok } from "../utils/http";
import { getCooperativeId } from "./helpers";

const router = Router();

const schema = z.object({
  member_id: z.string().uuid(),
  location: z.string().min(2),
  area: z.number().min(0),
  soil_type: z.string().optional().nullable(),
  irrigation_type: z.string().optional().nullable(),
  cooperative_id: z.string().uuid().optional(),
});

const updateSchema = schema.partial();

function mapField(field: {
  id: string;
  memberId: string;
  cooperativeId: string;
  location: string;
  area: number;
  soilType: string | null;
  irrigationType: string | null;
  createdAt: Date;
  updatedAt: Date;
}) {
  return {
    id: field.id,
    member_id: field.memberId,
    cooperative_id: field.cooperativeId,
    location: field.location,
    area: field.area,
    soil_type: field.soilType,
    irrigation_type: field.irrigationType,
    created_at: field.createdAt.toISOString(),
    updated_at: field.updatedAt.toISOString(),
  };
}

router.use(requireAuth);

router.get(
  "/",
  asyncHandler(async (req, res) => {
    const cooperativeId = getCooperativeId(req);
    const items = await prisma.parcelle.findMany({ where: { cooperativeId }, orderBy: { createdAt: "desc" } });
    return ok(res, items.map(mapField));
  }),
);

router.post(
  "/",
  validate(schema),
  asyncHandler(async (req, res) => {
    const payload = req.body as z.infer<typeof schema>;
    const cooperativeId = payload.cooperative_id ?? getCooperativeId(req);

    const created = await prisma.parcelle.create({
      data: {
        memberId: payload.member_id,
        cooperativeId,
        location: payload.location,
        area: payload.area,
        soilType: payload.soil_type,
        irrigationType: payload.irrigation_type,
      },
    });

    return ok(res, mapField(created), 201);
  }),
);

router.get(
  "/:id",
  asyncHandler(async (req, res) => {
    const item = await prisma.parcelle.findUnique({ where: { id: String(req.params.id) } });
    return ok(res, item ? mapField(item) : null);
  }),
);

router.patch(
  "/:id",
  validate(updateSchema),
  asyncHandler(async (req, res) => {
    const payload = req.body as z.infer<typeof updateSchema>;
    const updated = await prisma.parcelle.update({
      where: { id: String(req.params.id) },
      data: {
        memberId: payload.member_id,
        location: payload.location,
        area: payload.area,
        soilType: payload.soil_type,
        irrigationType: payload.irrigation_type,
      },
    });

    return ok(res, mapField(updated));
  }),
);

router.delete(
  "/:id",
  asyncHandler(async (req, res) => {
    const deleted = await prisma.parcelle.delete({ where: { id: String(req.params.id) } });
    return ok(res, mapField(deleted));
  }),
);

export default router;
