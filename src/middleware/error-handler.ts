import type { NextFunction, Request, Response } from "express";
import { ApiError, fail } from "../utils/http";

export function notFound(_req: Request, res: Response) {
  return fail(res, 404, "Route introuvable");
}

export function errorHandler(error: unknown, _req: Request, res: Response, next: NextFunction) {
  void next;
  if (error instanceof ApiError) {
    return fail(res, error.statusCode, error.message, error.details);
  }

  return fail(res, 500, "Erreur interne du serveur");
}
