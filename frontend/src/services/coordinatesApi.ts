import { http } from "./http";
import type { AppConfig, ReferenceImageItem, ScreenshotPayload } from "./types";

export async function captureScreenshot(): Promise<ScreenshotPayload> {
  const response = await http.post<ScreenshotPayload>("/api/coordinates/screenshot");
  return response.data;
}

export async function listReferenceImages(): Promise<ReferenceImageItem[]> {
  const response = await http.get<{ items: ReferenceImageItem[] }>("/api/coordinates/reference-images");
  return response.data.items;
}

export async function loadReferenceImage(name: string): Promise<ScreenshotPayload> {
  const response = await http.get<ScreenshotPayload>(`/api/coordinates/reference-images/${encodeURIComponent(name)}`);
  return response.data;
}

export async function testTap(x: number, y: number): Promise<void> {
  await http.post("/api/coordinates/test-tap", { x, y });
}

export async function saveCoordinatePoints(target: string, points: number[][]): Promise<AppConfig> {
  const response = await http.post<{ config: AppConfig }>("/api/coordinates/save-points", { target, points });
  return response.data.config;
}
