import type { Request } from "express";
import { ApiError } from "../utils/http";

export function getCooperativeId(req: Request) {
  const fromQuery = typeof req.query.cooperative_id === "string" ? req.query.cooperative_id : null;
  const fromBody = typeof req.body?.cooperative_id === "string" ? req.body.cooperative_id : null;
  const fromAuth = req.auth?.cooperativeId ?? null;

  const cooperativeId = fromQuery || fromBody || fromAuth;
  if (!cooperativeId) {
    throw new ApiError(400, "cooperative_id requis");
  }
  return cooperativeId;
}

export function parsePagination(req: Request) {
  const page = Number(req.query.page ?? 1);
  const pageSize = Number(req.query.page_size ?? 25);
  const safePage = Number.isFinite(page) && page > 0 ? page : 1;
  const safePageSize = Number.isFinite(pageSize) && pageSize > 0 ? Math.min(pageSize, 100) : 25;

  return {
    page: safePage,
    pageSize: safePageSize,
    skip: (safePage - 1) * safePageSize,
    take: safePageSize,
  };
}
