import { Camera, Crosshair, Image as ImageIcon, RotateCcw, Save, Trash2, Undo2 } from "lucide-react";
import { MouseEvent, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { Feedback } from "../components/Feedback";
import { SelectInput, TextInput } from "../components/FormControls";
import { PageHeader } from "../components/PageHeader";
import { SegmentedControl } from "../components/SegmentedControl";
import { useConfigEditor } from "../hooks/useConfigEditor";
import { captureScreenshot, listReferenceImages, loadReferenceImage, saveCoordinatePoints, testTap } from "../services/coordinatesApi";
import { apiErrorMessage } from "../services/http";
import type { AppConfig, BotStatus, ReferenceImageItem, ScreenshotPayload } from "../services/types";

type CoordinateMode = "troops" | "spells";

const views = [
  { value: "trenbenphai", label: "Trên phải" },
  { value: "trenbentrai", label: "Trên trái" },
  { value: "duoibenphai", label: "Dưới phải" },
  { value: "duoibentrai", label: "Dưới trái" },
];

function targetFor(mode: CoordinateMode, view: string, groupIndex: number): string {
  return mode === "spells" ? `spell_group_${groupIndex}_zone_${view}` : `zone_${view}`;
}

function readPoints(config: AppConfig | null, mode: CoordinateMode, view: string, groupIndex: number): number[][] {
  const deploy = config?.deploy ?? {};
  if (mode === "troops") return deploy.deploy_zones?.[view] ?? [];
  return deploy.spell_groups?.[groupIndex]?.zones?.[view] ?? [];
}

function parseInitialTarget(raw: string | null): { view: string; groupIndex: number } {
  const troop = raw?.match(/^zone_(.+)$/);
  if (troop && views.some((item) => item.value === troop[1])) return { view: troop[1], groupIndex: 0 };
  const spell = raw?.match(/^spell_group_(\d+)_zone_(.+)$/);
  if (spell && views.some((item) => item.value === spell[2])) return { view: spell[2], groupIndex: Number(spell[1]) };
  return { view: "trenbenphai", groupIndex: 0 };
}

function CoordinateToolPage({ mode, status }: { mode: CoordinateMode; status: BotStatus | null }) {
  const imageRef = useRef<HTMLImageElement | null>(null);
  const [searchParams] = useSearchParams();
  const initial = parseInitialTarget(searchParams.get("target"));
  const { config, isDirty: configDirty, saving: configSaving, error: configError, savedMessage: configMessage, updatePath, save: saveConfig, reload } = useConfigEditor();
  const [view, setView] = useState(initial.view);
  const [groupIndex, setGroupIndex] = useState(initial.groupIndex);
  const [referenceImages, setReferenceImages] = useState<ReferenceImageItem[]>([]);
  const [referenceName, setReferenceName] = useState("");
  const [image, setImage] = useState<ScreenshotPayload | null>(null);
  const [imageSourceLabel, setImageSourceLabel] = useState("");
  const [points, setPoints] = useState<number[][]>([]);
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null);
  const [busy, setBusy] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const spellGroups = config?.deploy?.spell_groups ?? [];
  const safeGroupIndex = Math.min(groupIndex, Math.max(0, spellGroups.length - 1));
  const target = targetFor(mode, view, safeGroupIndex);
  const savedPoints = readPoints(config, mode, view, safeGroupIndex);
  const localDirty = JSON.stringify(points) !== JSON.stringify(savedPoints);
  const selectedPoint = selectedIndex === null ? null : points[selectedIndex] ?? null;
  const imageSrc = image ? `data:image/png;base64,${image.image_base64}` : "";

  const groupOptions = spellGroups.map((group: any, index: number) => ({ label: group?.name || `Nhóm thuốc ${index + 1}`, value: String(index) }));
  const referenceOptions = referenceImages.map((item) => ({ label: `${item.label} (${item.width}x${item.height})`, value: item.name }));

  useEffect(() => {
    listReferenceImages().then((items) => {
      setReferenceImages(items);
      if (items.length) setReferenceName(items[0].name);
    }).catch((err) => setError(apiErrorMessage(err)));
  }, []);

  useEffect(() => {
    setPoints(readPoints(config, mode, view, safeGroupIndex));
    setSelectedIndex(null);
  }, [config, mode, safeGroupIndex, view]);

  async function run(name: string, action: () => Promise<void>) {
    if (busy) return;
    setBusy(name); setError(""); setMessage("");
    try { await action(); } catch (err) { setError(apiErrorMessage(err)); } finally { setBusy(""); }
  }

  async function handleCapture() {
    await run("capture", async () => {
      const payload = await captureScreenshot();
      setImage(payload); setImageSourceLabel("Ảnh chụp ADB hiện tại");
      setMessage("Đã chụp màn hình. Click lên ảnh để thêm điểm polygon.");
    });
  }

  async function handleLoadReference() {
    if (!referenceName) { setError("Chưa có ảnh mẫu trong thư mục img."); return; }
    await run("reference", async () => {
      const payload = await loadReferenceImage(referenceName);
      const item = referenceImages.find((entry) => entry.name === referenceName);
      setImage(payload); setImageSourceLabel(item?.label ?? referenceName);
      setMessage(`Đã tải ảnh mẫu ${item?.label ?? referenceName}.`);
    });
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

  async function handleSave() {
    if (points.length < 3) { setError("Polygon cần ít nhất 3 điểm trước khi lưu."); return; }
    if (configDirty) { setError("Cấu hình chung đang có thay đổi chưa lưu. Hãy lưu cấu hình trước khi lưu tọa độ."); return; }
    await run("save", async () => {
      await saveCoordinatePoints(target, points);
      await reload();
      setMessage(`Đã lưu ${points.length} điểm cho góc ${views.find((item) => item.value === view)?.label}.`);
    });
  }

  async function handleTestTap() {
    if (!selectedPoint) { setError("Chọn một điểm trước khi test tap."); return; }
    if (status?.running) { setError("Hãy dừng bot trước khi Test Tap."); return; }
    await run("tap", async () => { await testTap(selectedPoint[0], selectedPoint[1]); setMessage(`Đã test tap ${selectedPoint[0]},${selectedPoint[1]}.`); });
  }

  function resetSaved() { setPoints(savedPoints); setSelectedIndex(null); setMessage("Đã tải lại polygon đang lưu."); setError(""); }

  return (
    <div>
      <PageHeader eyebrow="Hiệu chỉnh" title={mode === "spells" ? "Tọa độ thả thuốc" : "Tọa độ thả lính"} subtitle={mode === "spells" ? "Vùng thuốc dùng chung, phân theo nhóm thuốc và bốn góc nhìn." : "Bốn vùng thả quân dùng chung cho mọi combo."} />
      {(error || configError) ? <Feedback tone="error" className="mb-5">{error || configError}</Feedback> : message ? <Feedback tone="success" className="mb-5">{message}</Feedback> : configMessage ? <Feedback tone="success" className="mb-5">{configMessage}</Feedback> : null}

      <Card title="Nguồn ảnh">
        <div className="grid gap-3 lg:grid-cols-[minmax(260px,1fr)_auto_auto] lg:items-end">
          <SelectInput label="Ảnh mẫu trong COC/img" value={referenceName} options={referenceOptions.length ? referenceOptions : [{ label: "Chưa có ảnh mẫu", value: "" }]} onChange={(event) => setReferenceName(event.target.value)} />
          <Button variant="primary" loading={busy === "reference"} disabled={Boolean(busy) || !referenceName} onClick={handleLoadReference}><ImageIcon className="h-4 w-4" />Dùng ảnh mẫu</Button>
          <Button variant="muted" loading={busy === "capture"} disabled={Boolean(busy)} onClick={handleCapture}><Camera className="h-4 w-4" />Chụp từ ADB</Button>
        </div>
      </Card>

      <div className="mt-5 grid gap-5 xl:grid-cols-[minmax(0,1fr)_340px]">
        <div className="min-w-0 overflow-hidden rounded-lg border border-white/10 bg-black/30">
          {imageSrc ? (
            <div className="relative">
              <div className="absolute left-3 top-3 z-10 max-w-[calc(100%-1.5rem)] truncate rounded-lg bg-black/75 px-3 py-1.5 text-xs font-semibold text-white">{imageSourceLabel} · {image?.width}x{image?.height}</div>
              <img ref={imageRef} src={imageSrc} alt="Ảnh thiết lập tọa độ" onClick={handleImageClick} className="block h-auto w-full cursor-crosshair select-none" draggable={false} />
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
            <div className="flex aspect-video items-center justify-center p-8 text-center text-sm text-slate-500">Chọn ảnh mẫu hoặc chụp từ ADB để bắt đầu.</div>
          )}
        </div>

        <aside className="min-w-0 space-y-5">
          {mode === "spells" ? (
            <Card title="Quy tắc thả thuốc">
              <TextInput type="number" min={0} suffix="px" label="Khoảng cách tối thiểu" value={String(config?.attack_timing?.spell_min_point_distance_px ?? 120)} onChange={(event) => updatePath(["attack_timing", "spell_min_point_distance_px"], Number(event.target.value || 0))} />
              <Button className="mt-4 w-full" variant="success" loading={configSaving} disabled={!configDirty} onClick={saveConfig}>Lưu cấu hình</Button>
            </Card>
          ) : null}

          <Card title={mode === "spells" ? "Nhóm và góc" : "Góc thả quân"}>
            <div className="space-y-4">
              {mode === "spells" ? (
                groupOptions.length ? <SelectInput label="Nhóm thuốc" value={String(safeGroupIndex)} options={groupOptions} onChange={(event) => setGroupIndex(Number(event.target.value))} /> : <Feedback tone="warning">Chưa có spell group trong cấu hình.</Feedback>
              ) : null}
              <div><p className="mb-2 text-sm font-medium text-slate-300">Góc nhìn</p><SegmentedControl value={view} columns={2} options={views} onChange={setView} /></div>
              <p className="text-xs text-slate-500">Dùng chung cho tất cả combo.</p>
            </div>
          </Card>

          <Card title="Điểm polygon" action={<span className={`rounded-full px-2.5 py-1 text-xs font-bold ${localDirty ? "bg-amber-400/15 text-amber-200" : "bg-limewash/15 text-lime-200"}`}>{localDirty ? "Chưa lưu" : "Đã lưu"}</span>}>
            <div className="grid grid-cols-2 gap-2">
              <Button variant="success" loading={busy === "save"} disabled={Boolean(busy) || points.length < 3 || !localDirty} onClick={handleSave}><Save className="h-4 w-4" />Lưu</Button>
              <Button variant="muted" disabled={Boolean(busy) || !points.length} onClick={() => { setPoints((current) => current.slice(0, -1)); setSelectedIndex(null); }}><Undo2 className="h-4 w-4" />Hoàn tác</Button>
              <Button variant="muted" disabled={Boolean(busy) || !localDirty} onClick={resetSaved}><RotateCcw className="h-4 w-4" />Tải lại</Button>
              <Button variant="danger" disabled={Boolean(busy) || !points.length} onClick={() => { setPoints([]); setSelectedIndex(null); }}><Trash2 className="h-4 w-4" />Xóa hết</Button>
              <Button className="col-span-2" variant="ghost" loading={busy === "tap"} disabled={Boolean(busy) || !selectedPoint || Boolean(status?.running)} onClick={handleTestTap}><Crosshair className="h-4 w-4" />Test điểm đang chọn</Button>
            </div>
            {points.length > 0 && points.length < 3 ? <Feedback tone="warning" className="mt-4">Cần thêm {3 - points.length} điểm để tạo polygon.</Feedback> : null}
          </Card>

          <Card title={`Danh sách điểm (${points.length})`}>
            <div className="max-h-72 space-y-2 overflow-auto pr-1 font-mono text-xs">
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

export function TroopCoordinatesPage({ status }: { status: BotStatus | null }) { return <CoordinateToolPage mode="troops" status={status} />; }
export function SpellCoordinatesPage({ status }: { status: BotStatus | null }) { return <CoordinateToolPage mode="spells" status={status} />; }
