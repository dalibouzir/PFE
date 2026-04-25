import type { NextFunction, Request, Response } from "express";

export class ApiError extends Error {
  statusCode: number;
  details?: unknown;

  constructor(statusCode: number, error: string, details?: unknown) {
    super(error);
    this.statusCode = statusCode;
    this.details = details;
  }
}

export function ok<T>(res: Response, data: T, status = 200) {
  return res.status(status).json(data);
}

export function fail(res: Response, statusCode: number, error: string, details?: unknown) {
  return res.status(statusCode).json({ success: false, error, details });
}

export function asyncHandler(fn: (req: Request, res: Response, next: NextFunction) => Promise<unknown>) {
  return (req: Request, res: Response, next: NextFunction) => {
    fn(req, res, next).catch(next);
  };
}
