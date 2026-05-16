import { Router } from "express";
import { EtapeStatut, FluxType, LotStatut } from "@prisma/client";
import { z } from "zod";
import { prisma } from "../lib/prisma";
import { invalidateByPrefix } from "../lib/redis";
import { requireAuth } from "../middleware/auth";
import { validate } from "../middleware/validate";
import { emitDashboardUpdate } from "../socket/io";
import { ApiError, asyncHandler, ok } from "../utils/http";
import { mapEtape, mapLot } from "../utils/mappers";
import { getCooperativeId } from "./helpers";

const router = Router();

const lotSchema = z.object({
  code: z.string().min(3),
  product_id: z.string().uuid().optional().nullable(),
  produit: z.string().optional(),
  quantite_initiale_kg: z.number().positive(),
  statut: z.enum(["ACTIF", "TERMINE"]).optional(),
  cooperative_id: z.string().uuid().optional(),
  creation_date: z.string().optional(),
});

const etapeSchema = z.object({
  nom_etape: z.string().min(2),
  type: z.string().min(2),
  ordre: z.number().int().min(1),
  quantite_entree_kg: z.number().min(0),
  quantite_sortie_kg: z.number().min(0),
  perte_kg: z.number().min(0).optional(),
  statut: z.enum(["EN_COURS", "TERMINE"]).optional(),
  date_debut: z.string(),
  date_fin: z.string().optional().nullable(),
  notes: z.string().optional().nullable(),
  flux_type: z.enum(["PRE_RECOLTE", "POST_RECOLTE"]).optional(),
});

const lotUpdateSchema = lotSchema.partial();

function normalizeStatut(input?: string | null) {
  return input === "TERMINE" ? LotStatut.TERMINE : LotStatut.ACTIF;
}

function normalizeEtapeStatut(input?: string | null) {
  return input === "TERMINE" ? EtapeStatut.TERMINE : EtapeStatut.EN_COURS;
}

router.use(requireAuth);

router.get(
  "/",
  asyncHandler(async (req, res) => {
    const cooperativeId = getCooperativeId(req);
    const rows = await prisma.lot.findMany({
      where: { cooperativeId },
      include: { etapes: { orderBy: { ordre: "asc" } } },
      orderBy: { creationDate: "desc" },
    });

    const payload = rows.map((lot) => {
      const done = lot.etapes.filter((item) => item.statut === EtapeStatut.TERMINE).length;
      const progress = lot.etapes.length > 0 ? (done / lot.etapes.length) * 100 : 0;
      const totalLoss = lot.etapes.reduce((sum, item) => sum + item.perteKg, 0);
      const lossPct = lot.quantiteInitialeKg > 0 ? (totalLoss / lot.quantiteInitialeKg) * 100 : 0;

      return {
        ...mapLot(lot),
        total_stages: lot.etapes.length,
        completed_stages: done,
        progress_pct: Number(progress.toFixed(2)),
        loss_pct: Number(lossPct.toFixed(2)),
      };
    });

    return ok(res, payload);
  }),
);

router.post(
  "/",
  validate(lotSchema),
  asyncHandler(async (req, res) => {
    const payload = req.body as z.infer<typeof lotSchema>;
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
        quantiteInitialeKg: payload.quantite_initiale_kg,
        quantiteActuelleKg: payload.quantite_initiale_kg,
        statut: normalizeStatut(payload.statut),
        creationDate: payload.creation_date ? new Date(payload.creation_date) : new Date(),
        createdByUserId: req.auth?.userId,
      },
    });

    await invalidateByPrefix(`dashboard:${cooperativeId}`);
    emitDashboardUpdate("lots:updated", { cooperativeId, lotId: created.id });

    return ok(res, mapLot(created), 201);
  }),
);

router.get(
  "/:id",
  asyncHandler(async (req, res) => {
    const lot = await prisma.lot.findUnique({
      where: { id: String(req.params.id) },
      include: {
        etapes: { orderBy: { ordre: "asc" } },
        fluxMatieres: { orderBy: { date: "desc" } },
      },
    });

    if (!lot) throw new ApiError(404, "Lot introuvable");

    return ok(res, {
      ...mapLot(lot),
      etapes: lot.etapes.map(mapEtape),
      flux_matiere: lot.fluxMatieres.map((item) => ({
        id: item.id,
        lot_id: item.lotId,
        etape_id: item.etapeId,
        type: item.type,
        date: item.date.toISOString().slice(0, 10),
        notes: item.notes,
      })),
    });
  }),
);

router.put(
  "/:id",
  validate(lotUpdateSchema),
  asyncHandler(async (req, res) => {
    const payload = req.body as z.infer<typeof lotUpdateSchema>;
    const existing = await prisma.lot.findUnique({ where: { id: String(req.params.id) } });
    if (!existing) throw new ApiError(404, "Lot introuvable");

    const updated = await prisma.lot.update({
      where: { id: String(req.params.id) },
      data: {
        code: payload.code,
        productId: payload.product_id,
        produit: payload.produit,
        quantiteInitialeKg: payload.quantite_initiale_kg,
        quantiteActuelleKg: payload.quantite_initiale_kg,
        statut: payload.statut ? normalizeStatut(payload.statut) : undefined,
        creationDate: payload.creation_date ? new Date(payload.creation_date) : undefined,
      },
    });

    await invalidateByPrefix(`dashboard:${existing.cooperativeId}`);
    emitDashboardUpdate("lots:updated", { cooperativeId: existing.cooperativeId, lotId: updated.id });

    return ok(res, mapLot(updated));
  }),
);

router.patch(
  "/:id",
  validate(lotUpdateSchema),
  asyncHandler(async (req, res) => {
    const payload = req.body as z.infer<typeof lotUpdateSchema>;
    const existing = await prisma.lot.findUnique({ where: { id: String(req.params.id) } });
    if (!existing) throw new ApiError(404, "Lot introuvable");

    const updated = await prisma.lot.update({
      where: { id: String(req.params.id) },
      data: {
        code: payload.code,
        productId: payload.product_id,
        produit: payload.produit,
        quantiteInitialeKg: payload.quantite_initiale_kg,
        quantiteActuelleKg: payload.quantite_initiale_kg,
        statut: payload.statut ? normalizeStatut(payload.statut) : undefined,
        creationDate: payload.creation_date ? new Date(payload.creation_date) : undefined,
      },
    });

    await invalidateByPrefix(`dashboard:${existing.cooperativeId}`);
    emitDashboardUpdate("lots:updated", { cooperativeId: existing.cooperativeId, lotId: updated.id });

    return ok(res, mapLot(updated));
  }),
);

router.post(
  "/:id/etapes",
  validate(etapeSchema),
  asyncHandler(async (req, res) => {
    const payload = req.body as z.infer<typeof etapeSchema>;
    const lot = await prisma.lot.findUnique({ where: { id: String(req.params.id) } });
    if (!lot) throw new ApiError(404, "Lot introuvable");

    const perte = payload.perte_kg ?? Math.max(payload.quantite_entree_kg - payload.quantite_sortie_kg, 0);

    const etape = await prisma.etapeLot.upsert({
      where: { lotId_ordre: { lotId: String(req.params.id), ordre: payload.ordre } },
      update: {
        nomEtape: payload.nom_etape,
        type: payload.type,
        quantiteEntreeKg: payload.quantite_entree_kg,
        quantiteSortieKg: payload.quantite_sortie_kg,
        perteKg: perte,
        statut: normalizeEtapeStatut(payload.statut),
        dateDebut: new Date(payload.date_debut),
        dateFin: payload.date_fin ? new Date(payload.date_fin) : null,
        notes: payload.notes,
      },
      create: {
        lotId: String(req.params.id),
        nomEtape: payload.nom_etape,
        type: payload.type,
        ordre: payload.ordre,
        quantiteEntreeKg: payload.quantite_entree_kg,
        quantiteSortieKg: payload.quantite_sortie_kg,
        perteKg: perte,
        statut: normalizeEtapeStatut(payload.statut),
        dateDebut: new Date(payload.date_debut),
        dateFin: payload.date_fin ? new Date(payload.date_fin) : null,
        notes: payload.notes,
      },
    });

    await prisma.fluxMatiere.create({
      data: {
        lotId: String(req.params.id),
        etapeId: etape.id,
        type: payload.flux_type === "PRE_RECOLTE" ? FluxType.PRE_RECOLTE : FluxType.POST_RECOLTE,
        date: new Date(payload.date_debut),
        notes: payload.notes ?? `Mise a jour etape ${payload.nom_etape}`,
      },
    });

    await prisma.lot.update({
      where: { id: String(req.params.id) },
      data: {
        quantiteActuelleKg: payload.quantite_sortie_kg,
      },
    });

    await invalidateByPrefix(`dashboard:${lot.cooperativeId}`);
    emitDashboardUpdate("lots:updated", { cooperativeId: lot.cooperativeId, lotId: String(req.params.id) });

    return ok(res, mapEtape(etape), 201);
  }),
);

router.put(
  "/:id/etapes/:etapeId",
  validate(etapeSchema.partial()),
  asyncHandler(async (req, res) => {
    const payload = req.body as Partial<z.infer<typeof etapeSchema>>;

    const existing = await prisma.etapeLot.findUnique({ where: { id: String(req.params.etapeId) }, include: { lot: true } });
    if (!existing || existing.lotId !== String(req.params.id)) {
      throw new ApiError(404, "Etape introuvable");
    }

    const qtyIn = payload.quantite_entree_kg ?? existing.quantiteEntreeKg;
    const qtyOut = payload.quantite_sortie_kg ?? existing.quantiteSortieKg;
    const perte = payload.perte_kg ?? Math.max(qtyIn - qtyOut, 0);

    const etape = await prisma.etapeLot.update({
      where: { id: String(req.params.etapeId) },
      data: {
        nomEtape: payload.nom_etape,
        type: payload.type,
        ordre: payload.ordre,
        quantiteEntreeKg: qtyIn,
        quantiteSortieKg: qtyOut,
        perteKg: perte,
        statut: payload.statut ? normalizeEtapeStatut(payload.statut) : undefined,
        dateDebut: payload.date_debut ? new Date(payload.date_debut) : undefined,
        dateFin: payload.date_fin ? new Date(payload.date_fin) : payload.date_fin === null ? null : undefined,
        notes: payload.notes,
      },
    });

    await prisma.lot.update({ where: { id: String(req.params.id) }, data: { quantiteActuelleKg: qtyOut } });

    await invalidateByPrefix(`dashboard:${existing.lot.cooperativeId}`);
    emitDashboardUpdate("lots:updated", { cooperativeId: existing.lot.cooperativeId, lotId: String(req.params.id) });

    return ok(res, mapEtape(etape));
  }),
);

export default router;
