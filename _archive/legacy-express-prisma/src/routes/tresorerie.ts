import { Router } from "express";
import { z } from "zod";
import { prisma } from "../lib/prisma";
import { requireAuth } from "../middleware/auth";
import { validate } from "../middleware/validate";
import { asyncHandler, ok } from "../utils/http";
import { getCooperativeId } from "./helpers";

const router = Router();

const schema = z.object({
  cooperative_id: z.string().uuid().optional(),
  mois: z.number().int().min(1).max(12),
  annee: z.number().int().min(2020).max(2100),
  recettes_fcfa: z.number().int().min(0),
  depenses_fcfa: z.number().int().min(0),
  solde_fcfa: z.number().int().optional(),
});

router.use(requireAuth);

router.get(
  "/",
  asyncHandler(async (req, res) => {
    const cooperativeId = getCooperativeId(req);
    const rows = await prisma.tresorerie.findMany({
      where: { cooperativeId },
      orderBy: [{ annee: "desc" }, { mois: "desc" }],
    });

    const current = rows[0] ?? null;

    return ok(res, {
      current,
      history: rows,
    });
  }),
);

router.post(
  "/",
  validate(schema),
  asyncHandler(async (req, res) => {
    const payload = req.body as z.infer<typeof schema>;
    const cooperativeId = payload.cooperative_id ?? getCooperativeId(req);

    const row = await prisma.tresorerie.upsert({
      where: {
        cooperativeId_mois_annee: {
          cooperativeId,
          mois: payload.mois,
          annee: payload.annee,
        },
      },
      update: {
        recettesFcfa: payload.recettes_fcfa,
        depensesFcfa: payload.depenses_fcfa,
        soldeFcfa: payload.solde_fcfa ?? payload.recettes_fcfa - payload.depenses_fcfa,
      },
      create: {
        cooperativeId,
        mois: payload.mois,
        annee: payload.annee,
        recettesFcfa: payload.recettes_fcfa,
        depensesFcfa: payload.depenses_fcfa,
        soldeFcfa: payload.solde_fcfa ?? payload.recettes_fcfa - payload.depenses_fcfa,
      },
    });

    return ok(res, row, 201);
  }),
);

export default router;
