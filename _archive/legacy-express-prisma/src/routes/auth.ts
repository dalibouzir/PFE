import { Router } from "express";
import bcrypt from "bcryptjs";
import { z } from "zod";
import { prisma } from "../lib/prisma";
import { requireAuth } from "../middleware/auth";
import { validate } from "../middleware/validate";
import { signToken } from "../utils/auth";
import { ApiError, asyncHandler, ok } from "../utils/http";
import { mapCooperative, mapUser } from "../utils/mappers";

const router = Router();

const loginSchema = z.object({
  email: z.string().email(),
  password: z.string().min(6),
});

const updateSchema = z.object({
  full_name: z.string().min(2).optional(),
  email: z.string().email().optional(),
  phone: z.string().min(6).optional().nullable(),
  password: z.string().min(8).optional(),
});

router.post(
  "/login",
  validate(loginSchema),
  asyncHandler(async (req, res) => {
    const { email, password } = req.body as z.infer<typeof loginSchema>;

    const user = await prisma.user.findUnique({ where: { email } });
    if (!user) {
      throw new ApiError(401, "Email ou mot de passe invalide");
    }

    const valid = await bcrypt.compare(password, user.passwordHash);
    if (!valid) {
      throw new ApiError(401, "Email ou mot de passe invalide");
    }

    const token = signToken({
      sub: user.id,
      role: user.role,
      cooperativeId: user.cooperativeId,
    });

    return ok(res, { access_token: token, token_type: "bearer" });
  }),
);

router.get(
  "/me",
  requireAuth,
  asyncHandler(async (req, res) => {
    const user = await prisma.user.findUnique({
      where: { id: req.auth!.userId },
      include: { cooperative: true },
    });

    if (!user) {
      throw new ApiError(404, "Utilisateur introuvable");
    }

    return ok(res, {
      ...mapUser(user),
      cooperative: user.cooperative ? mapCooperative(user.cooperative) : null,
    });
  }),
);

router.patch(
  "/me",
  requireAuth,
  validate(updateSchema),
  asyncHandler(async (req, res) => {
    const payload = req.body as z.infer<typeof updateSchema>;

    const data: {
      fullName?: string;
      email?: string;
      phone?: string | null;
      passwordHash?: string;
    } = {};

    if (payload.full_name) data.fullName = payload.full_name;
    if (payload.email) data.email = payload.email;
    if (payload.phone !== undefined) data.phone = payload.phone;
    if (payload.password) {
      data.passwordHash = await bcrypt.hash(payload.password, 10);
    }

    const user = await prisma.user.update({
      where: { id: req.auth!.userId },
      data,
    });

    return ok(res, mapUser(user));
  }),
);

export default router;
