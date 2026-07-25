import { http } from "./http";

export type SlotTemplateItem = {
  kind: string;
  count: number;
  path: string;
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

export async function detectSlots(imageBase64 = ""): Promise<SlotDetectionItem[]> {
  const response = await http.post<{ items: SlotDetectionItem[] }>("/api/slots/detect", {
    image_base64: imageBase64,
  });
  return response.data.items;
}
