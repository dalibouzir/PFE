import { Router } from "express";
import type { Request } from "express";
import { MembreStatut } from "@prisma/client";
import { z } from "zod";
import { prisma } from "../lib/prisma";
import { requireAuth } from "../middleware/auth";
import { validate } from "../middleware/validate";
import { ApiError, asyncHandler, ok } from "../utils/http";
import { mapCollecte, mapMember } from "../utils/mappers";
import { getCooperativeId, parsePagination } from "./helpers";

const router = Router();

const memberSchema = z.object({
  code: z.string().optional(),
  full_name: z.string().min(3),
  phone: z.string().min(8),
  village: z.string().optional().nullable(),
  main_product: z.string().optional().nullable(),
  parcel_count: z.number().int().min(0).optional(),
  area_hectares: z.number().min(0).optional(),
  join_date: z.string().optional().nullable(),
  specialty: z.string().optional().nullable(),
  status: z.enum(["active", "inactive", "seasonal"]).optional(),
  cooperative_id: z.string().uuid().optional(),
});

const memberUpdateSchema = memberSchema.partial();

router.use(requireAuth);

router.get(
  "/",
  asyncHandler(async (req, res) => {
    const cooperativeId = getCooperativeId(req);
    const { skip, take, page, pageSize } = parsePagination(req);

    const [items, total] = await Promise.all([
      prisma.membre.findMany({
        where: { cooperativeId, deletedAt: null },
        orderBy: { createdAt: "desc" },
        skip,
        take,
      }),
      prisma.membre.count({ where: { cooperativeId, deletedAt: null } }),
    ]);

    return ok(res, {
      items: items.map(mapMember),
      page,
      page_size: pageSize,
      total,
    });
  }),
);

router.post(
  "/",
  validate(memberSchema),
  asyncHandler(async (req, res) => {
    const payload = req.body as z.infer<typeof memberSchema>;
    const cooperativeId = payload.cooperative_id ?? getCooperativeId(req);
    const [prenom, ...rest] = payload.full_name.trim().split(" ");
    const nom = rest.join(" ") || prenom;

    const created = await prisma.membre.create({
      data: {
        cooperativeId,
        code: payload.code ?? `MBR-${Math.floor(Math.random() * 9000 + 1000)}`,
        nom,
        prenom,
        fullName: payload.full_name,
        phone: payload.phone,
        village: payload.village,
        culturePrincipale: payload.main_product,
        mainProduct: payload.main_product,
        parcelCount: payload.parcel_count ?? 0,
        areaHectares: payload.area_hectares ?? 0,
        joinDate: payload.join_date ? new Date(payload.join_date) : null,
        specialty: payload.specialty,
        statut:
          payload.status === "inactive"
            ? MembreStatut.INACTIF
            : payload.status === "seasonal"
              ? MembreStatut.SAISONNIER
              : MembreStatut.ACTIF,
      },
    });

    return ok(res, mapMember(created), 201);
  }),
);

router.get(
  "/:id",
  asyncHandler(async (req, res) => {
    const member = await prisma.membre.findUnique({ where: { id: String(req.params.id) } });
    if (!member || member.deletedAt) {
      throw new ApiError(404, "Membre introuvable");
    }

    const collectes = await prisma.collecte.findMany({
      where: { membreId: member.id },
      orderBy: { date: "desc" },
      take: 30,
    });

    return ok(res, {
      ...mapMember(member),
      collecte_history: collectes.map(mapCollecte),
    });
  }),
);

async function updateMember(req: Request, memberId: string) {
  const payload = req.body as z.infer<typeof memberUpdateSchema>;

  const data: {
    fullName?: string;
    phone?: string;
    village?: string | null;
    mainProduct?: string | null;
    culturePrincipale?: string | null;
    parcelCount?: number;
    areaHectares?: number;
    joinDate?: Date | null;
    specialty?: string | null;
    statut?: MembreStatut;
  } = {};

  if (payload.full_name) data.fullName = payload.full_name;
  if (payload.phone) data.phone = payload.phone;
  if (payload.village !== undefined) data.village = payload.village;
  if (payload.main_product !== undefined) {
    data.mainProduct = payload.main_product;
    data.culturePrincipale = payload.main_product;
  }
  if (payload.parcel_count !== undefined) data.parcelCount = payload.parcel_count;
  if (payload.area_hectares !== undefined) data.areaHectares = payload.area_hectares;
  if (payload.join_date !== undefined) data.joinDate = payload.join_date ? new Date(payload.join_date) : null;
  if (payload.specialty !== undefined) data.specialty = payload.specialty;
  if (payload.status) {
    data.statut =
      payload.status === "inactive"
        ? MembreStatut.INACTIF
        : payload.status === "seasonal"
          ? MembreStatut.SAISONNIER
          : MembreStatut.ACTIF;
  }

  return prisma.membre.update({ where: { id: memberId }, data });
}

router.put(
  "/:id",
  validate(memberUpdateSchema),
  asyncHandler(async (req, res) => {
    const updated = await updateMember(req, String(req.params.id));
    return ok(res, mapMember(updated));
  }),
);

router.patch(
  "/:id",
  validate(memberUpdateSchema),
  asyncHandler(async (req, res) => {
    const updated = await updateMember(req, String(req.params.id));
    return ok(res, mapMember(updated));
  }),
);

router.delete(
  "/:id",
  asyncHandler(async (req, res) => {
    const updated = await prisma.membre.update({
      where: { id: String(req.params.id) },
      data: { deletedAt: new Date(), statut: MembreStatut.INACTIF },
    });
    return ok(res, mapMember(updated));
  }),
);

router.post(
  "/:id/contact",
  asyncHandler(async (_req, res) => {
    return ok(res, { success: true, sent: true });
  }),
);

export default router;
