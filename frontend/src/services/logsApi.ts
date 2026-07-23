import { http } from "./http";
import type { LogEntry } from "./types";

export async function getLogs(after = 0): Promise<{ items: LogEntry[]; next_after: number }> {
  const response = await http.get<{ items: LogEntry[]; next_after: number }>("/api/logs", {
    params: { after },
  });
  return response.data;
}

export async function clearLogs(): Promise<void> {
  await http.delete("/api/logs");
}
