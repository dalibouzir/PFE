import { Router } from "express";
import { z } from "zod";
import { prisma } from "../lib/prisma";
import { requireAuth } from "../middleware/auth";
import { validate } from "../middleware/validate";
import { asyncHandler, ok } from "../utils/http";
import { getCooperativeId } from "./helpers";

const router = Router();

const schema = z.object({
  titre: z.string().min(2),
  date: z.string(),
  type: z.string().min(2),
  description: z.string().optional().nullable(),
  cooperative_id: z.string().uuid().optional(),
});

router.use(requireAuth);

router.get(
  "/",
  asyncHandler(async (req, res) => {
    const cooperativeId = getCooperativeId(req);
    const rows = await prisma.evenementCalendrier.findMany({
      where: {
        cooperativeId,
        date: { gte: new Date() },
      },
      orderBy: { date: "asc" },
      take: 50,
    });
    return ok(res, rows);
  }),
);

router.post(
  "/",
  validate(schema),
  asyncHandler(async (req, res) => {
    const payload = req.body as z.infer<typeof schema>;
    const cooperativeId = payload.cooperative_id ?? getCooperativeId(req);

    const row = await prisma.evenementCalendrier.create({
      data: {
        cooperativeId,
        titre: payload.titre,
        date: new Date(payload.date),
        type: payload.type,
        description: payload.description,
      },
    });

    return ok(res, row, 201);
  }),
);

export default router;
