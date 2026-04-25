import { Router } from "express";
import { CooperativeStatus, UserRole, UserStatus } from "@prisma/client";
import { z } from "zod";
import { prisma } from "../lib/prisma";
import { requireAuth, requireRole } from "../middleware/auth";
import { validate } from "../middleware/validate";
import { ApiError, asyncHandler, ok } from "../utils/http";
import { mapCooperative, mapUser } from "../utils/mappers";

const router = Router();

const cooperativeSchema = z.object({
  name: z.string().min(2),
  region: z.string().min(2),
  mode: z.string().optional(),
  address: z.string().optional(),
  phone: z.string().optional(),
  status: z.enum(["ACTIVE", "ONBOARDING", "SUSPENDED"]).optional(),
});

const managerSchema = z.object({
  full_name: z.string().min(3),
  email: z.string().email(),
  password: z.string().min(8),
  phone: z.string().optional().nullable(),
  cooperative_id: z.string().uuid(),
});

router.use(requireAuth, requireRole([UserRole.ADMIN]));

router.get(
  "/cooperatives",
  asyncHandler(async (_req, res) => {
    const rows = await prisma.cooperative.findMany({ orderBy: { createdAt: "desc" } });
    return ok(res, rows.map(mapCooperative));
  }),
);

router.post(
  "/cooperatives",
  validate(cooperativeSchema),
  asyncHandler(async (req, res) => {
    const payload = req.body as z.infer<typeof cooperativeSchema>;
    const created = await prisma.cooperative.create({
      data: {
        name: payload.name,
        region: payload.region,
        mode: payload.mode ?? "operationnel",
        address: payload.address,
        phone: payload.phone,
        status: payload.status ? (payload.status as CooperativeStatus) : CooperativeStatus.ACTIVE,
      },
    });

    return ok(res, mapCooperative(created), 201);
  }),
);

router.get(
  "/users",
  asyncHandler(async (_req, res) => {
    const users = await prisma.user.findMany({ orderBy: { createdAt: "desc" } });
    return ok(res, users.map(mapUser));
  }),
);

router.post(
  "/managers",
  validate(managerSchema),
  asyncHandler(async (req, res) => {
    const payload = req.body as z.infer<typeof managerSchema>;

    const coop = await prisma.cooperative.findUnique({ where: { id: payload.cooperative_id } });
    if (!coop) {
      throw new ApiError(404, "Cooperative introuvable");
    }

    const bcrypt = await import("bcryptjs");
    const passwordHash = await bcrypt.hash(payload.password, 10);

    const created = await prisma.user.create({
      data: {
        fullName: payload.full_name,
        email: payload.email,
        passwordHash,
        phone: payload.phone ?? null,
        cooperativeId: payload.cooperative_id,
        role: UserRole.MANAGER,
        status: UserStatus.ACTIVE,
      },
    });

    return ok(res, mapUser(created), 201);
  }),
);

router.patch(
  "/users/:id/disable",
  asyncHandler(async (req, res) => {
    const updated = await prisma.user.update({
      where: { id: String(req.params.id) },
      data: { status: UserStatus.DISABLED },
    });
    return ok(res, mapUser(updated));
  }),
);

router.patch(
  "/users/:id/enable",
  asyncHandler(async (req, res) => {
    const updated = await prisma.user.update({
      where: { id: String(req.params.id) },
      data: { status: UserStatus.ACTIVE },
    });
    return ok(res, mapUser(updated));
  }),
);

router.delete(
  "/users/:id",
  asyncHandler(async (req, res) => {
    const existing = await prisma.user.findUnique({ where: { id: String(req.params.id) } });
    if (!existing) throw new ApiError(404, "Utilisateur introuvable");

    const updated = await prisma.user.update({
      where: { id: String(req.params.id) },
      data: { status: UserStatus.DISABLED },
    });

    return ok(res, mapUser(updated));
  }),
);

export default router;
