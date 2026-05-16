import { TachePriorite, TacheStatut } from "@prisma/client";
import { Router } from "express";
import { z } from "zod";
import { prisma } from "../lib/prisma";
import { requireAuth } from "../middleware/auth";
import { validate } from "../middleware/validate";
import { asyncHandler, ok } from "../utils/http";
import { getCooperativeId } from "./helpers";

const router = Router();

const createSchema = z.object({
  titre: z.string().min(2),
  description: z.string().optional().nullable(),
  assignee_id: z.string().uuid().optional().nullable(),
  statut: z.enum(["A_FAIRE", "EN_COURS", "TERMINEE"]).optional(),
  due_date: z.string().optional().nullable(),
  priorite: z.enum(["BASSE", "MOYENNE", "HAUTE"]).optional(),
  cooperative_id: z.string().uuid().optional(),
});

const updateSchema = createSchema.partial();

router.use(requireAuth);

router.get(
  "/",
  asyncHandler(async (req, res) => {
    const cooperativeId = getCooperativeId(req);
    const rows = await prisma.tache.findMany({ where: { cooperativeId }, orderBy: { createdAt: "desc" } });
    return ok(res, rows);
  }),
);

router.post(
  "/",
  validate(createSchema),
  asyncHandler(async (req, res) => {
    const payload = req.body as z.infer<typeof createSchema>;
    const cooperativeId = payload.cooperative_id ?? getCooperativeId(req);

    const row = await prisma.tache.create({
      data: {
        cooperativeId,
        titre: payload.titre,
        description: payload.description,
        assigneeId: payload.assignee_id,
        statut: (payload.statut ?? "A_FAIRE") as TacheStatut,
        dueDate: payload.due_date ? new Date(payload.due_date) : null,
        priorite: (payload.priorite ?? "MOYENNE") as TachePriorite,
      },
    });

    return ok(res, row, 201);
  }),
);

router.put(
  "/:id",
  validate(updateSchema),
  asyncHandler(async (req, res) => {
    const payload = req.body as z.infer<typeof updateSchema>;

    const row = await prisma.tache.update({
      where: { id: String(req.params.id) },
      data: {
        titre: payload.titre,
        description: payload.description,
        assigneeId: payload.assignee_id,
        statut: payload.statut as TacheStatut | undefined,
        dueDate: payload.due_date !== undefined ? (payload.due_date ? new Date(payload.due_date) : null) : undefined,
        priorite: payload.priorite as TachePriorite | undefined,
      },
    });

    return ok(res, row);
  }),
);

router.delete(
  "/:id",
  asyncHandler(async (req, res) => {
    const row = await prisma.tache.delete({ where: { id: String(req.params.id) } });
    return ok(res, row);
  }),
);

export default router;
