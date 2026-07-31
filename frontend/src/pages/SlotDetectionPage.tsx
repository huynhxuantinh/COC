import { Camera, Image as ImageIcon, RotateCcw, ScanSearch, Trash2 } from "lucide-react";
import { PointerEvent, useEffect, useMemo, useRef, useState } from "react";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { ConfirmModal } from "../components/ConfirmModal";
import { EmptyState, Feedback } from "../components/Feedback";
import { PageHeader } from "../components/PageHeader";
import { SelectInput, TextInput } from "../components/FormControls";
import { captureScreenshot, listReferenceImages, loadReferenceImage } from "../services/coordinatesApi";
import { apiErrorMessage } from "../services/http";
import {
  deleteSlotTemplate,
  detectSlots,
  getSlotTemplates,
  saveSlotTemplate,
  type SlotDetectionItem,
  type SlotTemplatesPayload,
} from "../services/slotsApi";
import type { ReferenceImageItem, ScreenshotPayload } from "../services/types";

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
  const [referenceImages, setReferenceImages] = useState<ReferenceImageItem[]>([]);
  const [referenceName, setReferenceName] = useState("");
  const [imageSourceLabel, setImageSourceLabel] = useState("");
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
  const [pendingDelete, setPendingDelete] = useState<{ kind: string; filename: string } | null>(null);

  useEffect(() => {
    getSlotTemplates()
      .then((payload) => {
        setTemplates(payload);
        if (payload.kinds.length) setKind(payload.kinds[0]);
      })
      .catch((err) => setError(apiErrorMessage(err)));
  }, []);

  useEffect(() => {
    listReferenceImages()
      .then((items) => {
        setReferenceImages(items);
        if (items.length) setReferenceName(items[0].name);
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
  const referenceOptions = referenceImages.map((item) => ({ label: `${item.label} (${item.width}x${item.height})`, value: item.name }));

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
      setImageSourceLabel("Ảnh chụp ADB hiện tại");
      setSelectedPoint(null);
      setCropRegion(null);
      setDragStart(null);
      setDragCurrent(null);
      setDetections([]);
      setMessage("Đã chụp. Chọn loại icon rồi kéo chuột khoanh vùng icon trên thanh quân.");
    });
  }

  async function handleLoadReference() {
    if (!referenceName) {
      setError("Chưa có ảnh mẫu trong thư mục img.");
      return;
    }
    await run("reference", async () => {
      const payload = await loadReferenceImage(referenceName);
      const item = referenceImages.find((entry) => entry.name === referenceName);
      setImage(payload);
      setImageSourceLabel(item?.label ?? referenceName);
      setSelectedPoint(null);
      setCropRegion(null);
      setDragStart(null);
      setDragCurrent(null);
      setDetections([]);
      setMessage(`Đã tải ảnh mẫu ${item?.label ?? referenceName}.`);
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
      />

      {error ? <Feedback tone="error" className="mb-5">{error}</Feedback> : message ? <Feedback tone="success" className="mb-5">{message}</Feedback> : null}

      <Card title="Nguồn ảnh">
        <div className="grid gap-3 lg:grid-cols-[minmax(260px,1fr)_auto_auto] lg:items-end">
          <SelectInput label="Ảnh mẫu trong COC/img" value={referenceName} options={referenceOptions.length ? referenceOptions : [{ label: "Chưa có ảnh mẫu", value: "" }]} onChange={(event) => setReferenceName(event.target.value)} />
          <Button variant="primary" loading={busy === "reference"} disabled={busy !== "" || !referenceName} onClick={handleLoadReference}><ImageIcon className="h-4 w-4" />Dùng ảnh mẫu</Button>
          <Button variant="muted" loading={busy === "capture"} disabled={busy !== ""} onClick={handleCapture}><Camera className="h-4 w-4" />Chụp từ ADB</Button>
        </div>
      </Card>

      <div className="mt-5 grid gap-5 xl:grid-cols-[minmax(0,1fr)_360px]">
        <div className="min-w-0 overflow-hidden rounded-lg border border-white/10 bg-black/30">
          {imageSrc ? (
            <div className="relative">
              <div className="absolute left-3 top-3 z-20 max-w-[calc(100%-1.5rem)] truncate rounded-lg bg-black/75 px-3 py-1.5 text-xs font-semibold text-white">{imageSourceLabel} · {image?.width}x{image?.height}</div>
              <img
                ref={imageRef}
                src={imageSrc}
                alt="Ảnh thanh quân"
                onPointerDown={handlePointerDown}
                onPointerMove={handlePointerMove}
                onPointerUp={handlePointerUp}
                className="block h-auto w-full cursor-crosshair select-none"
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
              Chọn ảnh mẫu hoặc chụp từ ADB khi đang ở màn hình trận đấu có thanh quân.
            </div>
          )}
        </div>

        <aside className="space-y-4">
          <Card title="Crop và lưu mẫu">
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
              <Button className="w-full" variant="muted" disabled={!cropRegion && !selectedPoint} onClick={() => { setCropRegion(null); setSelectedPoint(null); setDragStart(null); setDragCurrent(null); }}>
                <RotateCcw className="h-4 w-4" />Reset crop
              </Button>
              <div className="rounded-lg border border-white/10 bg-ink-900 px-3 py-2 text-xs text-slate-400">
                {cropRegion ? `Vùng crop: [${cropRegion.join(", ")}]` : "Chưa có vùng tự cắt."}
              </div>
              <Button className="w-full" variant="success" disabled={busy !== "" || !image || !selectedPoint} onClick={handleSaveTemplate}>
                Lưu mẫu
              </Button>
              <Button className="w-full" variant="muted" disabled={busy !== ""} onClick={handleDetect}>
                <ScanSearch className="h-4 w-4" />Test nhận diện
              </Button>
            </div>
          </Card>

          <Card title="Mẫu hiện có">
            <div className="max-h-96 space-y-3 overflow-auto pr-1 text-sm text-slate-300">
              {(templates?.items ?? []).length === 0 ? <EmptyState title="Chưa có template" description="Crop một icon rồi lưu mẫu." /> : null}
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
                            onClick={() => setPendingDelete({ kind: item.kind, filename: file.filename })}
                          >
                            <Trash2 className="h-4 w-4" />
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
                <EmptyState title="Chưa có kết quả" description="Bấm Test nhận diện sau khi có template." />
              ) : (
                detections.map((item, index) => (
                  <div key={`${item.kind}-${index}`} className="rounded-lg bg-ink-900 px-3 py-2">
                    <div className="flex items-center justify-between gap-3"><span className="font-semibold text-white">{kindLabels[item.kind] ?? item.kind} x{item.count >= 0 ? item.count : "?"}</span><span className="font-mono text-sky-300">{item.score.toFixed(4)}</span></div>
                    <p className="mt-1 font-mono text-slate-500">[{item.center.join(", ")}] · {item.template}</p>
                  </div>
                ))
              )}
            </div>
          </Card>
        </aside>
      </div>

      <ConfirmModal
        open={Boolean(pendingDelete)}
        title="Xóa template?"
        description={pendingDelete ? `Template ${kindLabels[pendingDelete.kind] ?? pendingDelete.kind}/${pendingDelete.filename} sẽ không còn được dùng để nhận diện slot.` : ""}
        busy={busy.startsWith("delete-")}
        onClose={() => setPendingDelete(null)}
        onConfirm={async () => {
          if (!pendingDelete) return;
          await handleDeleteTemplate(pendingDelete.kind, pendingDelete.filename);
          setPendingDelete(null);
        }}
      />
    </div>
  );
}
