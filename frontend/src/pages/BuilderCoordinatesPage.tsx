import { Camera, Crosshair, RotateCcw, Save, Trash2, Undo2 } from "lucide-react";
import { MouseEvent, useEffect, useRef, useState } from "react";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { Feedback } from "../components/Feedback";
import { PageHeader } from "../components/PageHeader";
import { SegmentedControl } from "../components/SegmentedControl";
import { useConfigEditor } from "../hooks/useConfigEditor";
import { captureScreenshot, saveCoordinatePoints, testTap } from "../services/coordinatesApi";
import { apiErrorMessage } from "../services/http";
import type { ScreenshotPayload } from "../services/types";

type Stage = "stage1" | "stage2";

const stageOptions = [
  { value: "stage1", label: "Làng 1" },
  { value: "stage2", label: "Làng 2" },
];

function savedZone(config: Record<string, any> | null, stage: Stage): number[][] {
  return config?.builder_base?.deploy?.[`${stage}_zone`] ?? [];
}

export function BuilderCoordinatesPage() {
  const imageRef = useRef<HTMLImageElement | null>(null);
  const { config, isDirty: configDirty, error: configError, reload } = useConfigEditor();
  const [stage, setStage] = useState<Stage>("stage1");
  const [image, setImage] = useState<ScreenshotPayload | null>(null);
  const [points, setPoints] = useState<number[][]>([]);
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null);
  const [busy, setBusy] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const storedPoints = savedZone(config, stage);
  const selectedPoint = selectedIndex === null ? null : points[selectedIndex] ?? null;
  const localDirty = JSON.stringify(points) !== JSON.stringify(storedPoints);
  const imageSrc = image ? `data:image/png;base64,${image.image_base64}` : "";

  useEffect(() => {
    setPoints(savedZone(config, stage));
    setSelectedIndex(null);
  }, [config, stage]);

  async function run(name: string, action: () => Promise<void>) {
    if (busy) return;
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

  function handleImageClick(event: MouseEvent<HTMLImageElement>) {
    if (!image || !imageRef.current) return;
    const rect = imageRef.current.getBoundingClientRect();
    const x = Math.round(((event.clientX - rect.left) / rect.width) * image.width);
    const y = Math.round(((event.clientY - rect.top) / rect.height) * image.height);
    const point = [Math.max(0, Math.min(image.width - 1, x)), Math.max(0, Math.min(image.height - 1, y))];
    setPoints((current) => [...current, point]);
    setSelectedIndex(points.length);
  }

  async function handleCapture() {
    await run("capture", async () => {
      setImage(await captureScreenshot());
      setMessage("Đã chụp màn hình.");
    });
  }

  async function handleSave() {
    if (points.length < 3) {
      setError("Vùng thả cần ít nhất 3 điểm.");
      return;
    }
    if (configDirty) {
      setError("Hãy lưu cấu hình chung trước khi lưu vùng thả.");
      return;
    }
    await run("save", async () => {
      await saveCoordinatePoints(`builder_${stage}_zone`, points);
      await reload();
      setMessage(`Đã lưu vùng thả ${stage === "stage1" ? "Làng 1" : "Làng 2"}.`);
    });
  }

  async function handleTestTap() {
    if (!selectedPoint) return;
    await run("tap", async () => {
      await testTap(selectedPoint[0], selectedPoint[1]);
      setMessage(`Đã test tap ${selectedPoint[0]},${selectedPoint[1]}.`);
    });
  }

  return (
    <div>
      <PageHeader eyebrow="Làng đêm" title="Tọa độ thả quân" subtitle="Vẽ vùng riêng cho Làng 1 và Làng 2 trên ảnh chụp ADB." />
      {(error || configError) ? <Feedback tone="error" className="mb-5">{error || configError}</Feedback> : message ? <Feedback tone="success" className="mb-5">{message}</Feedback> : null}

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_340px]">
        <div className="min-w-0 overflow-hidden rounded-lg border border-white/10 bg-black/30">
          {imageSrc ? (
            <div className="relative">
              <img ref={imageRef} src={imageSrc} alt="Ảnh thiết lập vùng Làng đêm" onClick={handleImageClick} className="block h-auto w-full cursor-crosshair select-none" draggable={false} />
              {image && points.length >= 2 ? (
                <svg className="pointer-events-none absolute inset-0 h-full w-full" viewBox={`0 0 ${image.width} ${image.height}`}>
                  <polygon points={points.map(([x, y]) => `${x},${y}`).join(" ")} fill={points.length >= 3 ? "rgba(56,189,248,.16)" : "none"} stroke="#38bdf8" strokeWidth="4" vectorEffect="non-scaling-stroke" />
                </svg>
              ) : null}
              {image && points.map(([x, y], index) => (
                <button key={`${x}-${y}-${index}`} type="button" aria-label={`Điểm ${index + 1}`} onClick={(event) => { event.stopPropagation(); setSelectedIndex(index); }} className={`absolute grid h-6 w-6 -translate-x-1/2 -translate-y-1/2 place-items-center rounded-full border-2 text-[10px] font-bold ${selectedIndex === index ? "border-white bg-pink-500 text-white" : "border-white bg-sky-400 text-slate-950"}`} style={{ left: `${(x / image.width) * 100}%`, top: `${(y / image.height) * 100}%` }}>{index + 1}</button>
              ))}
            </div>
          ) : (
            <div className="flex aspect-video items-center justify-center p-8 text-center text-sm text-slate-500">Mở đúng màn hình chuẩn bị của từng làng rồi bấm Chụp từ ADB.</div>
          )}
        </div>

        <aside className="space-y-5">
          <Card title="Giai đoạn">
            <SegmentedControl value={stage} columns={2} options={stageOptions} onChange={(value) => setStage(value as Stage)} />
            <Button className="mt-4 w-full" variant="primary" loading={busy === "capture"} disabled={Boolean(busy)} onClick={handleCapture}><Camera className="h-4 w-4" />Chụp từ ADB</Button>
          </Card>

          <Card title="Điểm polygon" action={<span className={`rounded-full px-2.5 py-1 text-xs font-bold ${localDirty ? "bg-amber-400/15 text-amber-200" : "bg-limewash/15 text-lime-200"}`}>{localDirty ? "Chưa lưu" : "Đã lưu"}</span>}>
            <div className="grid grid-cols-2 gap-2">
              <Button variant="success" loading={busy === "save"} disabled={Boolean(busy) || points.length < 3 || !localDirty} onClick={handleSave}><Save className="h-4 w-4" />Lưu</Button>
              <Button variant="muted" disabled={Boolean(busy) || !points.length} onClick={() => { setPoints((current) => current.slice(0, -1)); setSelectedIndex(null); }}><Undo2 className="h-4 w-4" />Hoàn tác</Button>
              <Button variant="muted" disabled={Boolean(busy) || !localDirty} onClick={() => { setPoints(storedPoints); setSelectedIndex(null); }}><RotateCcw className="h-4 w-4" />Tải lại</Button>
              <Button variant="danger" disabled={Boolean(busy) || !points.length} onClick={() => { setPoints([]); setSelectedIndex(null); }}><Trash2 className="h-4 w-4" />Xóa hết</Button>
              <Button className="col-span-2" variant="ghost" loading={busy === "tap"} disabled={Boolean(busy) || !selectedPoint} onClick={handleTestTap}><Crosshair className="h-4 w-4" />Test điểm đang chọn</Button>
            </div>
          </Card>

          <Card title={`Danh sách điểm (${points.length})`}>
            <div className="max-h-80 space-y-2 overflow-auto pr-1 font-mono text-xs">
              {points.length ? points.map(([x, y], index) => (
                <button key={`${x}-${y}-${index}`} type="button" onClick={() => setSelectedIndex(index)} className={`block w-full rounded-lg border px-3 py-2 text-left ${selectedIndex === index ? "border-pink-400 bg-pink-500/10 text-pink-100" : "border-white/10 bg-ink-900 text-slate-300"}`}>{index + 1}. [{x}, {y}]</button>
              )) : <p className="py-4 text-center font-sans text-slate-500">Chưa có điểm.</p>}
            </div>
          </Card>
        </aside>
      </div>
    </div>
  );
}
