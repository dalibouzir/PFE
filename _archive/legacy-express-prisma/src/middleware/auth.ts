import type { NextFunction, Request, Response } from "express";
import { UserRole } from "@prisma/client";
import { verifyToken } from "../utils/auth";
import { fail } from "../utils/http";

export function requireAuth(req: Request, res: Response, next: NextFunction) {
  const authHeader = req.headers.authorization;
  if (!authHeader || !authHeader.startsWith("Bearer ")) {
    return fail(res, 401, "Token manquant");
  }

  const token = authHeader.slice(7);
  try {
    const payload = verifyToken(token);
    req.auth = {
      userId: payload.sub,
      role: payload.role,
      cooperativeId: payload.cooperativeId,
    };
    next();
  } catch {
    return fail(res, 401, "Token invalide");
  }
}

export function requireRole(roles: UserRole[]) {
  return (req: Request, res: Response, next: NextFunction) => {
    if (!req.auth) {
      return fail(res, 401, "Authentification requise");
    }

    if (!roles.includes(req.auth.role)) {
      return fail(res, 403, "Permission refusee");
    }

    next();
  };
}
