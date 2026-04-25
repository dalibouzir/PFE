import express from "express";
import cors from "cors";
import path from "node:path";
import authRoutes from "./routes/auth";
import adminRoutes from "./routes/admin";
import membresRoutes from "./routes/membres";
import collectesRoutes from "./routes/collectes";
import stocksRoutes from "./routes/stocks";
import lotsRoutes from "./routes/lots";
import tresorerieRoutes from "./routes/tresorerie";
import facturesRoutes from "./routes/factures";
import tachesRoutes from "./routes/taches";
import evenementsRoutes from "./routes/evenements";
import iaRoutes from "./routes/ia";
import dashboardRoutes from "./routes/dashboard";
import parcellesRoutes from "./routes/parcelles";
import produitsRoutes from "./routes/produits";
import batchesRoutes from "./routes/batches";
import processStepsRoutes from "./routes/process-steps";
import analyticsRoutes from "./routes/analytics";
import referenceRoutes from "./routes/reference";
import chatRoutes from "./routes/chat";
import uploadsRoutes from "./routes/uploads";
import { errorHandler, notFound } from "./middleware/error-handler";
import { ok } from "./utils/http";

export function createApp() {
  const app = express();

  app.use(
    cors({
      origin: process.env.FRONTEND_URL?.split(",") ?? "*",
      credentials: true,
    }),
  );
  app.use(express.json({ limit: "2mb" }));
  app.use(express.urlencoded({ extended: true }));

  const uploadDir = path.resolve(process.cwd(), "uploads");
  app.use("/uploads", express.static(uploadDir));

  app.get("/health", (_req, res) => ok(res, { status: "ok" }));

  app.use("/api/auth", authRoutes);
  app.use("/api/admin", adminRoutes);
  app.use("/api/membres", membresRoutes);
  app.use("/api/collectes", collectesRoutes);
  app.use("/api/stocks", stocksRoutes);
  app.use("/api/lots", lotsRoutes);
  app.use("/api/tresorerie", tresorerieRoutes);
  app.use("/api/factures", facturesRoutes);
  app.use("/api/taches", tachesRoutes);
  app.use("/api/evenements", evenementsRoutes);
  app.use("/api/ia", iaRoutes);
  app.use("/api/dashboard", dashboardRoutes);
  app.use("/api/parcelles", parcellesRoutes);
  app.use("/api/produits", produitsRoutes);
  app.use("/api/batches", batchesRoutes);
  app.use("/api/process-steps", processStepsRoutes);
  app.use("/api/analytics", analyticsRoutes);
  app.use("/api/reference", referenceRoutes);
  app.use("/api/chat", chatRoutes);
  app.use("/api/uploads", uploadsRoutes);

  // Legacy aliases for the existing frontend hooks
  app.use("/auth", authRoutes);
  app.use("/admin", adminRoutes);
  app.use("/members", membresRoutes);
  app.use("/fields", parcellesRoutes);
  app.use("/products", produitsRoutes);
  app.use("/inputs", collectesRoutes);
  app.use("/stocks", stocksRoutes);
  app.use("/batches", batchesRoutes);
  app.use("/process-steps", processStepsRoutes);
  app.use("/analytics", analyticsRoutes);
  app.use("/reference", referenceRoutes);
  app.use("/chat", chatRoutes);

  app.use(notFound);
  app.use(errorHandler);

  return app;
}
