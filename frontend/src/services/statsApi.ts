import { http } from "./http";
import type { StatsPayload } from "./types";

export async function getStats(): Promise<StatsPayload> {
  const response = await http.get<StatsPayload>("/api/stats");
  return response.data;
}
