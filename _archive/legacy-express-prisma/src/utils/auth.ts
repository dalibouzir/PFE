import jwt from "jsonwebtoken";
import type { UserRole } from "@prisma/client";

const jwtSecret = process.env.JWT_SECRET || "change-this-secret";

type TokenPayload = {
  sub: string;
  role: UserRole;
  cooperativeId?: string | null;
};

export function signToken(payload: TokenPayload) {
  return jwt.sign(payload, jwtSecret, { expiresIn: "12h" });
}

export function verifyToken(token: string) {
  return jwt.verify(token, jwtSecret) as TokenPayload;
}
