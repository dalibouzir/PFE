import type { UserRole } from "@prisma/client";

declare global {
  namespace Express {
    interface AuthUserPayload {
      userId: string;
      role: UserRole;
      cooperativeId?: string | null;
    }

    interface Request {
      auth?: AuthUserPayload;
    }
  }
}

export {};
