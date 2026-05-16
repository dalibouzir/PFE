import { FactureStatut } from "@prisma/client";
import { Router } from "express";
import { z } from "zod";
import { prisma } from "../lib/prisma";
import { requireAuth } from "../middleware/auth";
import { validate } from "../middleware/validate";
import { asyncHandler, ok } from "../utils/http";
import { getCooperativeId } from "./helpers";

const router = Router();

const createSchema = z.object({
  numero: z.string().min(3),
  membre_id: z.string().uuid(),
  montant_fcfa: z.number().int().min(0),
  statut: z.enum(["EN_ATTENTE", "ENCAISSEE"]).optional(),
  date_emission: z.string(),
  cooperative_id: z.string().uuid().optional(),
});

const updateSchema = z.object({ statut: z.enum(["EN_ATTENTE", "ENCAISSEE"]) });

router.use(requireAuth);

router.get(
  "/",
  asyncHandler(async (req, res) => {
    const cooperativeId = getCooperativeId(req);
    const statut = typeof req.query.statut === "string" ? req.query.statut : undefined;

    const rows = await prisma.facture.findMany({
      where: {
        cooperativeId,
        ...(statut ? { statut: statut === "ENCAISSEE" ? FactureStatut.ENCAISSEE : FactureStatut.EN_ATTENTE } : {}),
      },
      orderBy: { dateEmission: "desc" },
    });

    return ok(res, rows);
  }),
);

router.post(
  "/",
  validate(createSchema),
  asyncHandler(async (req, res) => {
    const payload = req.body as z.infer<typeof createSchema>;
    const cooperativeId = payload.cooperative_id ?? getCooperativeId(req);

    const row = await prisma.facture.create({
      data: {
        cooperativeId,
        numero: payload.numero,
        membreId: payload.membre_id,
        montantFcfa: payload.montant_fcfa,
        statut: payload.statut === "ENCAISSEE" ? FactureStatut.ENCAISSEE : FactureStatut.EN_ATTENTE,
        dateEmission: new Date(payload.date_emission),
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
    const row = await prisma.facture.update({
      where: { id: String(req.params.id) },
      data: {
        statut: payload.statut === "ENCAISSEE" ? FactureStatut.ENCAISSEE : FactureStatut.EN_ATTENTE,
      },
    });

    return ok(res, row);
  }),
);

export default router;
