import { http } from "./http";
import type { AppConfig } from "./types";

export type SlotTemplateItem = {
  kind: string;
  count: number;
  path: string;
  files: {
    filename: string;
    image_base64: string;
  }[];
};

export type SlotTemplatesPayload = {
  kinds: string[];
  items: SlotTemplateItem[];
};

export type SlotDetectionItem = {
  kind: string;
  center: number[];
  score: number;
  template: string;
  count: number;
};

export async function getSlotTemplates(): Promise<SlotTemplatesPayload> {
  const response = await http.get<SlotTemplatesPayload>("/api/slots/templates");
  return response.data;
}

export async function saveSlotTemplate(
  kind: string,
  imageBase64: string,
  x: number,
  y: number,
  size = 76,
  cropRegion: number[] = [],
): Promise<SlotTemplatesPayload> {
  const response = await http.post<SlotTemplatesPayload>("/api/slots/templates", {
    kind,
    image_base64: imageBase64,
    x,
    y,
    size,
    crop_region: cropRegion,
  });
  return response.data;
}

export async function deleteSlotTemplate(kind: string, filename: string): Promise<SlotTemplatesPayload> {
  const response = await http.delete<SlotTemplatesPayload>(`/api/slots/templates/${encodeURIComponent(kind)}/${encodeURIComponent(filename)}`);
  return response.data;
}

export async function renameSlotKind(oldKind: string, newKind: string): Promise<AppConfig> {
  const response = await http.post<{ config: AppConfig }>("/api/slots/kinds/rename", {
    old_kind: oldKind,
    new_kind: newKind,
  });
  return response.data.config;
}

export async function detectSlots(imageBase64 = ""): Promise<SlotDetectionItem[]> {
  const response = await http.post<{ items: SlotDetectionItem[] }>("/api/slots/detect", {
    image_base64: imageBase64,
  });
  return response.data.items;
}
