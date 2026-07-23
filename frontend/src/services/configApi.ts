import { http } from "./http";
import type { AppConfig, OptionsPayload } from "./types";

export async function getConfig(): Promise<AppConfig> {
  const response = await http.get<{ config: AppConfig }>("/api/config");
  return response.data.config;
}

export async function saveConfig(config: AppConfig): Promise<AppConfig> {
  const response = await http.put<{ config: AppConfig }>("/api/config", { config });
  return response.data.config;
}

export async function getOptions(): Promise<OptionsPayload> {
  const response = await http.get<OptionsPayload>("/api/config/options");
  return response.data;
}
