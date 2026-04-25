import type { NextFunction, Request, Response } from "express";
import type { ZodError, ZodTypeAny } from "zod";
import { fail } from "../utils/http";

type Schema = ZodTypeAny;

export function validate(schema: Schema) {
  return (req: Request, res: Response, next: NextFunction) => {
    try {
      req.body = schema.parse(req.body);
      next();
    } catch (error) {
      const details = (error as ZodError).issues?.map((issue) => ({
        path: issue.path.join("."),
        message: issue.message,
      }));
      return fail(res, 400, "Validation invalide", details);
    }
  };
}
