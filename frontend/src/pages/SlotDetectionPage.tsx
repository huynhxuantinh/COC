import { PointerEvent, useEffect, useMemo, useRef, useState } from "react";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { PageHeader } from "../components/PageHeader";
import { SelectInput, TextInput } from "../components/FormControls";
import { captureScreenshot } from "../services/coordinatesApi";
import { apiErrorMessage } from "../services/http";
import {
  deleteSlotTemplate,
  detectSlots,
  getSlotTemplates,
  saveSlotTemplate,
  type SlotDetectionItem,
  type SlotTemplatesPayload,
} from "../services/slotsApi";
import type { ScreenshotPayload } from "../services/types";

const kindLabels: Record<string, string> = {
  dragon: "Rồng điện",
  balloon: "Bóng",
  valkyrie: "Valkyrie",
  hero: "Tướng",
  rage: "Nộ",
  freeze: "Băng",
};

const cropPresets = [48, 64, 76, 96, 112];

function clampCropSize(value: number): number {
  if (!Number.isFinite(value)) return 76;
  return Math.max(32, Math.min(140, Math.round(value)));
}

function templateImageSrc(filename: string, imageBase64: string): string {
  const lower = filename.toLowerCase();
  const mime = lower.endsWith(".webp") ? "image/webp" : lower.endsWith(".jpg") || lower.endsWith(".jpeg") ? "image/jpeg" : "image/png";
  return `data:${mime};base64,${imageBase64}`;
}

export function SlotDetectionPage() {
  const imageRef = useRef<HTMLImageElement | null>(null);
  const [templates, setTemplates] = useState<SlotTemplatesPayload | null>(null);
  const [kind, setKind] = useState("dragon");
  const [cropSize, setCropSize] = useState(76);
  const [image, setImage] = useState<ScreenshotPayload | null>(null);
  const [selectedPoint, setSelectedPoint] = useState<number[] | null>(null);
  const [cropRegion, setCropRegion] = useState<number[] | null>(null);
  const [dragStart, setDragStart] = useState<number[] | null>(null);
  const [dragCurrent, setDragCurrent] = useState<number[] | null>(null);
  const [detections, setDetections] = useState<SlotDetectionItem[]>([]);
  const [busy, setBusy] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    getSlotTemplates()
      .then((payload) => {
        setTemplates(payload);
        if (payload.kinds.length) setKind(payload.kinds[0]);
      })
      .catch((err) => setError(apiErrorMessage(err)));
  }, []);

  const imageSrc = image ? `data:image/png;base64,${image.image_base64}` : "";
  const cropBox = useMemo(() => {
    if (!image) return null;
    if (dragStart && dragCurrent) {
      const x1 = Math.min(dragStart[0], dragCurrent[0]);
      const y1 = Math.min(dragStart[1], dragCurrent[1]);
      const x2 = Math.max(dragStart[0], dragCurrent[0]);
      const y2 = Math.max(dragStart[1], dragCurrent[1]);
      return {
        left: (x1 / image.width) * 100,
        top: (y1 / image.height) * 100,
        width: ((x2 - x1) / image.width) * 100,
        height: ((y2 - y1) / image.height) * 100,
      };
    }
    if (cropRegion && cropRegion.length >= 4) {
      return {
        left: (cropRegion[0] / image.width) * 100,
        top: (cropRegion[1] / image.height) * 100,
        width: (cropRegion[2] / image.width) * 100,
        height: (cropRegion[3] / image.height) * 100,
      };
    }
    if (!selectedPoint) return null;
    const half = cropSize / 2;
    const left = Math.max(0, selectedPoint[0] - half);
    const top = Math.max(0, selectedPoint[1] - half);
    const right = Math.min(image.width, selectedPoint[0] + half);
    const bottom = Math.min(image.height, selectedPoint[1] + half);
    return {
      left: (left / image.width) * 100,
      top: (top / image.height) * 100,
      width: ((right - left) / image.width) * 100,
      height: ((bottom - top) / image.height) * 100,
    };
  }, [cropRegion, cropSize, dragCurrent, dragStart, image, selectedPoint]);
  const kindOptions = useMemo(
    () => (templates?.kinds ?? ["dragon", "balloon", "valkyrie", "hero", "rage", "freeze"]).map((value) => ({ label: kindLabels[value] ?? value, value })),
    [templates],
  );

  async function run(name: string, action: () => Promise<void>) {
    setBusy(name);
    setError("");
    setMessage("");
    try {
      await action();
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setBusy("");
    }
  }

  async function handleCapture() {
    await run("capture", async () => {
      const payload = await captureScreenshot();
      setImage(payload);
      setSelectedPoint(null);
      setCropRegion(null);
      setDragStart(null);
      setDragCurrent(null);
      setDetections([]);
      setMessage("Đã chụp. Chọn loại icon rồi kéo chuột khoanh vùng icon trên thanh quân.");
    });
  }

  function imagePoint(event: PointerEvent<HTMLImageElement>): number[] | null {
    if (!image || !imageRef.current) return null;
    const rect = imageRef.current.getBoundingClientRect();
    const x = Math.round(((event.clientX - rect.left) / rect.width) * image.width);
    const y = Math.round(((event.clientY - rect.top) / rect.height) * image.height);
    return [
      Math.max(0, Math.min(image.width - 1, x)),
      Math.max(0, Math.min(image.height - 1, y)),
    ];
  }

  function handlePointerDown(event: PointerEvent<HTMLImageElement>) {
    const point = imagePoint(event);
    if (!point) return;
    setDragStart(point);
    setDragCurrent(point);
    setSelectedPoint(point);
    setCropRegion(null);
  }

  function handlePointerMove(event: PointerEvent<HTMLImageElement>) {
    if (!dragStart) return;
    const point = imagePoint(event);
    if (!point) return;
    setDragCurrent(point);
  }

  function handlePointerUp(event: PointerEvent<HTMLImageElement>) {
    const end = imagePoint(event);
    if (!end || !dragStart) return;
    const x1 = Math.min(dragStart[0], end[0]);
    const y1 = Math.min(dragStart[1], end[1]);
    const x2 = Math.max(dragStart[0], end[0]);
    const y2 = Math.max(dragStart[1], end[1]);
    const width = x2 - x1;
    const height = y2 - y1;
    if (width >= 8 && height >= 8) {
      setCropRegion([x1, y1, width, height]);
      setSelectedPoint([Math.round(x1 + width / 2), Math.round(y1 + height / 2)]);
    } else {
      setSelectedPoint(end);
      setCropRegion(null);
    }
    setDragStart(null);
    setDragCurrent(null);
  }

  async function handleSaveTemplate() {
    if (!image || !selectedPoint) {
      setError("Chụp ảnh rồi click vào icon trước.");
      return;
    }
    await run("save", async () => {
      const payload = await saveSlotTemplate(kind, image.image_base64, selectedPoint[0], selectedPoint[1], cropSize, cropRegion ?? []);
      setTemplates(payload);
      const suffix = cropRegion ? ` vùng [${cropRegion.join(", ")}]` : ` tại ${selectedPoint[0]},${selectedPoint[1]}`;
      setMessage(`Đã lưu mẫu ${kindLabels[kind] ?? kind}${suffix}.`);
    });
  }

  async function handleDeleteTemplate(templateKind: string, filename: string) {
    if (!window.confirm(`Xóa template ${templateKind}/${filename}?`)) return;
    await run(`delete-${templateKind}-${filename}`, async () => {
      const payload = await deleteSlotTemplate(templateKind, filename);
      setTemplates(payload);
      setMessage(`Đã xóa template ${kindLabels[templateKind] ?? templateKind}: ${filename}.`);
    });
  }

  async function handleDetect() {
    await run("detect", async () => {
      const items = await detectSlots(image?.image_base64 ?? "");
      setDetections(items);
      setMessage(`Đã nhận diện ${items.length} slot.`);
    });
  }

  return (
    <div>
      <PageHeader
        eyebrow="Hiệu chỉnh"
        title="Nhận diện slot"
        subtitle="Chụp màn hình trận, khoanh icon quân/phép, lưu mẫu rồi test nhận diện."
        action={
          <Button variant="primary" disabled={busy !== ""} onClick={handleCapture}>
            {busy === "capture" ? "Đang chụp..." : "Chụp từ ADB"}
          </Button>
        }
      />

      {(error || message) && (
        <div className={`mb-5 rounded-lg px-4 py-3 text-sm ${error ? "border border-danger/30 bg-danger/10 text-rose-200" : "border border-limewash/30 bg-limewash/10 text-lime-200"}`}>
          {error || message}
        </div>
      )}

      <div className="grid gap-5 xl:grid-cols-[1fr_340px]">
        <div className="overflow-hidden rounded-2xl border border-white/10 bg-black/30">
          {imageSrc ? (
            <div className="relative">
              <img
                ref={imageRef}
                src={imageSrc}
                alt="Ảnh thanh quân"
                onPointerDown={handlePointerDown}
                onPointerMove={handlePointerMove}
                onPointerUp={handlePointerUp}
                className="block w-full cursor-crosshair select-none"
                draggable={false}
              />
              {selectedPoint ? (
                <div
                  className="absolute h-6 w-6 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-pink-200 bg-pink-500/80"
                  style={{ left: `${(selectedPoint[0] / (image?.width ?? 1)) * 100}%`, top: `${(selectedPoint[1] / (image?.height ?? 1)) * 100}%` }}
                />
              ) : null}
              {cropBox ? (
                <div
                  className="pointer-events-none absolute border-2 border-sky-300 bg-sky-400/10 shadow-[0_0_0_9999px_rgba(0,0,0,0.18)]"
                  style={{
                    left: `${cropBox.left}%`,
                    top: `${cropBox.top}%`,
                    width: `${cropBox.width}%`,
                    height: `${cropBox.height}%`,
                  }}
                />
              ) : null}
              {image &&
                detections.map((item, index) => (
                  <div
                    key={`${item.kind}-${index}`}
                    className="absolute -translate-x-1/2 -translate-y-1/2 rounded-lg border border-lime-200 bg-black/75 px-2 py-1 text-xs font-bold text-lime-100"
                    style={{ left: `${(item.center[0] / image.width) * 100}%`, top: `${(item.center[1] / image.height) * 100}%` }}
                  >
                    {kindLabels[item.kind] ?? item.kind} x{item.count >= 0 ? item.count : "?"}
                  </div>
                ))}
            </div>
          ) : (
            <div className="flex aspect-video items-center justify-center p-8 text-center text-sm text-slate-500">
              Bấm Chụp từ ADB khi đang ở màn hình trận đấu có thanh quân.
            </div>
          )}
        </div>

        <aside className="space-y-4">
          <Card title="Lưu mẫu icon">
            <div className="space-y-3">
              <SelectInput label="Loại icon" value={kind} options={kindOptions} onChange={(event) => setKind(event.target.value)} />
              <TextInput
                label="Kích thước crop"
                type="number"
                min={32}
                max={140}
                step={4}
                hint="Kéo chuột khoanh vùng icon để crop tự do."
                value={String(cropSize)}
                onChange={(event) => setCropSize(clampCropSize(Number(event.target.value || 76)))}
              />
              <div className="grid grid-cols-5 gap-2">
                {cropPresets.map((size) => (
                  <button
                    key={size}
                    type="button"
                    onClick={() => setCropSize(size)}
                    className={`rounded-lg border px-2 py-2 text-xs font-bold transition ${
                      cropSize === size ? "border-sky-300 bg-sky-400 text-slate-950" : "border-white/10 bg-ink-900 text-slate-300 hover:border-sky-400/50"
                    }`}
                  >
                    {size}
                  </button>
                ))}
              </div>
              <div className="grid grid-cols-2 gap-2">
                <Button variant="muted" disabled={cropSize <= 32} onClick={() => setCropSize((value) => clampCropSize(value - 4))}>
                  Thu nhỏ
                </Button>
                <Button variant="muted" disabled={cropSize >= 140} onClick={() => setCropSize((value) => clampCropSize(value + 4))}>
                  Phóng to
                </Button>
              </div>
              <Button className="w-full" variant="muted" disabled={!cropRegion} onClick={() => setCropRegion(null)}>
                Bỏ vùng tự cắt
              </Button>
              <div className="rounded-lg border border-white/10 bg-ink-900 px-3 py-2 text-xs text-slate-400">
                {cropRegion ? `Vùng crop: [${cropRegion.join(", ")}]` : "Chưa có vùng tự cắt."}
              </div>
              <Button className="w-full" variant="success" disabled={busy !== "" || !image || !selectedPoint} onClick={handleSaveTemplate}>
                Lưu mẫu
              </Button>
              <Button className="w-full" variant="muted" disabled={busy !== ""} onClick={handleDetect}>
                Test nhận diện
              </Button>
            </div>
          </Card>

          <Card title="Mẫu hiện có">
            <div className="max-h-96 space-y-3 overflow-auto text-sm text-slate-300">
              {(templates?.items ?? []).map((item) => (
                <div key={item.kind} className="rounded-lg bg-ink-900 px-3 py-2">
                  <div className="mb-2 flex items-center justify-between">
                    <span className="font-semibold text-white">{kindLabels[item.kind] ?? item.kind}</span>
                    <span className="font-mono text-sky-300">{item.count}</span>
                  </div>
                  <div className="space-y-2">
                    {(item.files ?? []).length === 0 ? (
                      <p className="text-xs text-slate-500">Chưa có mẫu.</p>
                    ) : (
                      (item.files ?? []).map((file) => (
                        <div key={file.filename} className="flex items-center gap-3 rounded-lg border border-white/10 bg-black/25 p-2">
                          <img
                            src={templateImageSrc(file.filename, file.image_base64)}
                            alt={file.filename}
                            className="h-12 w-12 rounded border border-white/10 bg-black object-contain"
                          />
                          <span className="min-w-0 flex-1 truncate font-mono text-xs text-slate-300" title={file.filename}>
                            {file.filename}
                          </span>
                          <Button
                            className="px-3 py-1.5"
                            variant="danger"
                            disabled={busy !== ""}
                            onClick={() => handleDeleteTemplate(item.kind, file.filename)}
                          >
                            Xóa
                          </Button>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              ))}
            </div>
          </Card>

          <Card title="Kết quả test">
            <div className="max-h-64 space-y-2 overflow-auto text-xs text-slate-300">
              {detections.length === 0 ? (
                <p className="text-slate-500">Chưa có kết quả.</p>
              ) : (
                detections.map((item, index) => (
                  <div key={`${item.kind}-${index}`} className="rounded-lg bg-ink-900 px-3 py-2">
                    {kindLabels[item.kind] ?? item.kind} x{item.count >= 0 ? item.count : "?"} [{item.center.join(", ")}] score {item.score}
                  </div>
                ))
              )}
            </div>
          </Card>
        </aside>
      </div>
    </div>
  );
}
