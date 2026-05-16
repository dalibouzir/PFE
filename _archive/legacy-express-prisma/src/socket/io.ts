import type { Server as HttpServer } from "node:http";
import { Server } from "socket.io";

let io: Server | null = null;

export function initSocket(server: HttpServer) {
  io = new Server(server, {
    cors: {
      origin: "*",
      credentials: true,
    },
  });

  io.on("connection", (socket) => {
    socket.on("join-dashboard", () => {
      socket.join("dashboard");
    });
  });

  return io;
}

export function getIo() {
  return io;
}

export function emitDashboardUpdate(event: string, payload?: unknown) {
  io?.to("dashboard").emit(event, payload ?? { updatedAt: new Date().toISOString() });
}
