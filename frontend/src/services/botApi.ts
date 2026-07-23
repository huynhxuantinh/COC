import { http } from "./http";
import type { BotStatus } from "./types";

export async function getBotStatus(): Promise<BotStatus> {
  const response = await http.get<BotStatus>("/api/bot/status");
  return response.data;
}

export async function scanAdb(): Promise<BotStatus> {
  const response = await http.post<BotStatus>("/api/bot/scan-adb");
  return response.data;
}

export async function startBot(): Promise<BotStatus> {
  const response = await http.post<BotStatus>("/api/bot/start");
  return response.data;
}

export async function togglePause(): Promise<BotStatus> {
  const response = await http.post<BotStatus>("/api/bot/pause-toggle");
  return response.data;
}

export async function stopBot(): Promise<BotStatus> {
  const response = await http.post<BotStatus>("/api/bot/stop");
  return response.data;
}
