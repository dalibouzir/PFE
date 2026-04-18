"use client";

import { io, type Socket } from "socket.io-client";
import { getApiBaseUrl } from "./client";

let socket: Socket | null = null;

function socketOrigin() {
  const url = getApiBaseUrl();
  try {
    const parsed = new URL(url);
    return `${parsed.protocol}//${parsed.host}`;
  } catch {
    return "http://localhost:8000";
  }
}

export function getSocketClient() {
  if (!socket) {
    socket = io(socketOrigin(), {
      transports: ["websocket", "polling"],
      autoConnect: true,
    });
  }
  return socket;
}
