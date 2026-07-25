import { MouseEvent, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { SelectInput } from "../components/FormControls";
import { useConfigEditor } from "../hooks/useConfigEditor";
import {
  captureScreenshot,
  listReferenceImages,
  loadReferenceImage,
  saveCoordinatePoints,
  testTap,
} from "../services/coordinatesApi";
import { apiErrorMessage } from "../services/http";
import type { AppConfig, ReferenceImageItem, ScreenshotPayload } from "../services/types";

type CoordinateMode = "troops" | "spells";

type TargetOption = {
  label: string;
  value: string;
};

const troopTargets: TargetOption[] = [
  { label: "Vùng thả trên phải", value: "zone_trenbenphai" },
  { label: "Vùng thả trên trái", value: "zone_trenbentrai" },
  { label: "Vùng thả dưới phải", value: "zone_duoibenphai" },
  { label: "Vùng thả dưới trái", value: "zone_duoibentrai" },
];

const viewTargets = [
  { label: "trên phải", value: "trenbenphai" },
  { label: "trên trái", value: "trenbentrai" },
  { label: "dưới phải", value: "duoibenphai" },
  { label: "dưới trái", value: "duoibentrai" },
];

const spellGroups = [
  { label: "Nộ 1", value: "spell_no1", read: (deploy: any, view: string) => deploy.spells?.[0]?.zones?.[view] ?? [] },
  { label: "Băng", value: "spell_bang", read: (deploy: any, view: string) => deploy.spells?.[1]?.zones?.[view] ?? [] },
  { label: "Nộ 2", value: "spell_no2", read: (deploy: any, view: string) => deploy.spells?.[2]?.zones?.[view] ?? [] },
  { label: "Nhóm Nộ/Băng", value: "spell_group", read: (deploy: any, view: string) => deploy.spell_groups?.[0]?.zones?.[view] ?? [] },
];

const spellTargets: TargetOption[] = spellGroups.flatMap((spell) =>
  viewTargets.map((view) => ({
    label: `${spell.label} - ${view.label}`,
    value: `${spell.value}_zone_${view.value}`,
  })),
);

const allTargets = [...troopTargets, ...spellTargets];

function readPoints(config: AppConfig | null, target: string): number[][] {
  const deploy = config?.deploy ?? {};
  if (target === "zone_trenbenphai") return deploy.deploy_zones?.trenbenphai ?? [];
  if (target === "zone_trenbentrai") return deploy.deploy_zones?.trenbentrai ?? [];
  if (target === "zone_duoibenphai") return deploy.deploy_zones?.duoibenphai ?? [];
  if (target === "zone_duoibentrai") return deploy.deploy_zones?.duoibentrai ?? [];
  for (const spell of spellGroups) {
    for (const view of viewTargets) {
      if (target === `${spell.value}_zone_${view.value}`) return spell.read(deploy, view.value);
    }
  }
  return [];
}

function targetLabel(target: string): string {
  return allTargets.find((item) => item.value === target)?.label ?? target;
}

function defaultTarget(mode: CoordinateMode): string {
  return mode === "spells" ? "spell_no1_zone_trenbenphai" : "zone_trenbenphai";
}

function allowedTargets(mode: CoordinateMode): TargetOption[] {
  return mode === "spells" ? spellTargets : troopTargets;
}

function CoordinateToolPage({ mode }: { mode: CoordinateMode }) {
  const imageRef = useRef<HTMLImageElement | null>(null);
  const [searchParams] = useSearchParams();
  const { config, options, isDirty, reload } = useConfigEditor();
  const targets = allowedTargets(mode);
  const [referenceImages, setReferenceImages] = useState<ReferenceImageItem[]>([]);
  const [referenceName, setReferenceName] = useState("");
  const [target, setTarget] = useState(searchParams.get("target") || defaultTarget(mode));
  const [comboName, setComboName] = useState("");
  const [image, setImage] = useState<ScreenshotPayload | null>(null);
  const [imageSourceLabel, setImageSourceLabel] = useState("");
  const [points, setPoints] = useState<number[][]>([]);
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null);
  const [busy, setBusy] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    const queryTarget = searchParams.get("target");
    if (queryTarget && targets.some((item) => item.value === queryTarget)) {
      setTarget(queryTarget);
      return;
    }
    if (!targets.some((item) => item.value === target)) {
      setTarget(defaultTarget(mode));
    }
  }, [mode, searchParams, target, targets]);

  useEffect(() => {
    listReferenceImages()
      .then((images) => {
        setReferenceImages(images);
        if (images.length > 0) setReferenceName(images[0].name);
      })
      .catch((err) => setError(apiErrorMessage(err)));
  }, []);

  useEffect(() => {
    setPoints(readPoints(config, target));
    setSelectedIndex(null);
  }, [config, target]);

  useEffect(() => {
    const activeCombo = config?.farm?.combo ?? "";
    if (activeCombo && !comboName) setComboName(activeCombo);
  }, [config, comboName]);

  const imageSrc = image ? `data:image/png;base64,${image.image_base64}` : "";
  const selectedPoint = useMemo(() => {
    if (selectedIndex === null) return null;
    return points[selectedIndex] ?? null;
  }, [points, selectedIndex]);

  const referenceOptions = referenceImages.map((item) => ({
    label: `${item.label} (${item.width}x${item.height})`,
    value: item.name,
  }));
  const comboOptions = [
    ...(options?.combos ?? []).map((name) => ({ label: `Combo: ${name}`, value: name })),
    { label: "Tất cả combo", value: "__all__" },
    { label: "Chỉ deploy mặc định", value: "__global__" },
  ];

  const pageTitle = mode === "spells" ? "Tọa độ thả thuốc" : "Tọa độ thả lính";
  const pageSubtitle =
    mode === "spells"
      ? "Cấu hình vùng polygon thả Nộ/Băng theo 4 góc nhìn. Mỗi vùng cần tối thiểu 3 điểm."
      : "Chỉ cấu hình 4 vùng polygon để thả quân. Mỗi vùng cần tối thiểu 3 điểm để bot random bên trong.";
  const isZoneTarget = mode === "spells" || target.startsWith("zone_");

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
      setMessage("Đã chụp màn hình. Click lên ảnh để thêm tọa độ.");
    });
  }

  async function handleLoadReference() {
    if (!referenceName) {
      setError("Chưa có ảnh mẫu trong thư mục img.");
      return;
    }
    await run("reference", async () => {
      const payload = await loadReferenceImage(referenceName);
      const item = referenceImages.find((imageItem) => imageItem.name === referenceName);
      setImage(payload);
      setImageSourceLabel(item?.label ?? referenceName);
      setMessage(`Đã tải ảnh mẫu: ${item?.label ?? referenceName}. Click lên ảnh để lấy tọa độ.`);
    });
  }

  function handleImageClick(event: MouseEvent<HTMLImageElement>) {
    if (!image || !imageRef.current) return;
    const rect = imageRef.current.getBoundingClientRect();
    const x = Math.round(((event.clientX - rect.left) / rect.width) * image.width);
    const y = Math.round(((event.clientY - rect.top) / rect.height) * image.height);
    const clamped = [
      Math.max(0, Math.min(image.width - 1, x)),
      Math.max(0, Math.min(image.height - 1, y)),
    ];
    setPoints((current) => [...current, clamped]);
    setSelectedIndex(points.length);
  }

  async function handleSave() {
    if (isDirty) {
      setError("Đang có thay đổi cấu hình chưa lưu. Bấm Lưu cấu hình trước rồi hãy lưu tọa độ.");
      return;
    }
    await run("save", async () => {
      await saveCoordinatePoints(target, points, comboName || config?.farm?.combo || "");
      await reload();
      setMessage(`Đã lưu ${points.length} tọa độ vào ${targetLabel(target)}.`);
    });
  }

  async function handleTestTap() {
    if (!selectedPoint) {
      setError("Chọn 1 tọa độ trong danh sách trước khi test tap.");
      return;
    }
    await run("tap", async () => {
      await testTap(selectedPoint[0], selectedPoint[1]);
      setMessage(`Đã test tap ${selectedPoint[0]},${selectedPoint[1]}.`);
    });
  }

  function undoPoint() {
    setPoints((current) => current.slice(0, -1));
    setSelectedIndex(null);
  }

  return (
    <div className="space-y-5">
      <Card title={pageTitle} subtitle={pageSubtitle}>
        {(error || message) && (
          <div className={`mb-4 rounded-lg px-4 py-3 text-sm ${error ? "border border-danger/30 bg-danger/10 text-rose-200" : "border border-limewash/30 bg-limewash/10 text-lime-200"}`}>
            {error || message}
          </div>
        )}

        <div className="mb-4 grid gap-3 lg:grid-cols-[1fr_auto_auto]">
          <SelectInput
            label="Ảnh mẫu trong COC/img"
            value={referenceName}
            options={referenceOptions.length ? referenceOptions : [{ label: "Chưa có ảnh mẫu", value: "" }]}
            onChange={(event) => setReferenceName(event.target.value)}
          />
          <div className="flex items-end">
            <Button className="w-full" variant="primary" disabled={busy !== "" || !referenceName} onClick={handleLoadReference}>
              {busy === "reference" ? "Đang tải..." : "Dùng ảnh mẫu"}
            </Button>
          </div>
          <div className="flex items-end">
            <Button className="w-full" variant="muted" disabled={busy !== ""} onClick={handleCapture}>
              {busy === "capture" ? "Đang chụp..." : "Chụp từ ADB"}
            </Button>
          </div>
        </div>

        <div className="grid gap-4 xl:grid-cols-[1fr_340px]">
          <div className="overflow-hidden rounded-2xl border border-white/10 bg-black/30">
            {imageSrc ? (
              <div className="relative">
                <div className="absolute left-3 top-3 z-10 rounded-full bg-black/65 px-3 py-1 text-xs font-semibold text-white">
                  {imageSourceLabel || "Ảnh tọa độ"} · {image?.width}x{image?.height}
                </div>
                <img ref={imageRef} src={imageSrc} alt="Ảnh tọa độ" onClick={handleImageClick} className="block w-full cursor-crosshair select-none" draggable={false} />
                {image && isZoneTarget && points.length >= 2 ? (
                  <svg className="pointer-events-none absolute inset-0 h-full w-full" viewBox={`0 0 ${image.width} ${image.height}`} preserveAspectRatio="none">
                    <polyline
                      points={[...points, ...(points.length >= 3 ? [points[0]] : [])].map(([x, y]) => `${x},${y}`).join(" ")}
                      fill={points.length >= 3 ? "rgba(56, 189, 248, 0.16)" : "none"}
                      stroke="rgb(56, 189, 248)"
                      strokeWidth="4"
                    />
                  </svg>
                ) : null}
                {image &&
                  points.map(([x, y], index) => (
                    <button
                      key={`${x}-${y}-${index}`}
                      type="button"
                      onClick={(event) => {
                        event.stopPropagation();
                        setSelectedIndex(index);
                      }}
                      className={`absolute h-5 w-5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 text-[10px] font-black ${
                        selectedIndex === index ? "border-pink-300 bg-pink-500 text-white" : "border-white bg-sky-400 text-slate-950"
                      }`}
                      style={{
                        left: `${(x / image.width) * 100}%`,
                        top: `${(y / image.height) * 100}%`,
                      }}
                    >
                      {index + 1}
                    </button>
                  ))}
              </div>
            ) : (
              <div className="flex aspect-video items-center justify-center p-8 text-center text-sm text-slate-500">
                Chưa có ảnh. Chọn 1 ảnh mẫu rồi bấm Dùng ảnh mẫu, hoặc bấm Chụp từ ADB.
              </div>
            )}
          </div>

          <aside className="space-y-4">
            <div className={`rounded-2xl border p-4 ${mode === "spells" ? "border-pink-400/20 bg-pink-500/5" : "border-sky-400/20 bg-sky-500/5"}`}>
              <p className="text-sm font-bold text-white">{mode === "spells" ? "Chọn thuốc/spell" : "Chọn nhóm thả lính"}</p>
              <div className="mt-3 grid grid-cols-2 gap-2">
                {targets.map((item) => (
                  <button
                    key={item.value}
                    type="button"
                    onClick={() => setTarget(item.value)}
                    className={`rounded-lg border px-3 py-2 text-left text-xs font-semibold transition ${
                      target === item.value
                        ? mode === "spells"
                          ? "border-pink-300 bg-pink-500 text-white"
                          : "border-sky-300 bg-sky-400 text-slate-950"
                        : "border-white/10 bg-ink-900 text-slate-300 hover:border-sky-400/50"
                    }`}
                  >
                    {item.label}
                  </button>
                ))}
              </div>
            </div>

            <SelectInput
              label="Lưu cho combo"
              value={comboName || config?.farm?.combo || ""}
              options={comboOptions}
              onChange={(event) => setComboName(event.target.value)}
            />

            <div className="rounded-xl border border-white/10 bg-black/25 p-3 text-sm text-slate-300">
              Đang chọn: <span className="font-semibold text-white">{targetLabel(target)}</span>
              {isZoneTarget ? (
                <span className="mt-1 block text-xs text-slate-500">Click theo viền vùng muốn thả, tối thiểu 3 điểm.</span>
              ) : null}
            </div>

            <div className="grid grid-cols-2 gap-2">
              <Button variant="success" disabled={busy !== ""} onClick={handleSave}>
                Lưu điểm
              </Button>
              <Button variant="muted" disabled={points.length === 0 || busy !== ""} onClick={undoPoint}>
                Xóa điểm cuối
              </Button>
              <Button variant="danger" disabled={points.length === 0 || busy !== ""} onClick={() => setPoints([])}>
                Xóa hết
              </Button>
              <Button variant="muted" disabled={!selectedPoint || busy !== ""} onClick={handleTestTap}>
                Test tap
              </Button>
            </div>

            <div className="rounded-xl border border-white/10 bg-black/25 p-4">
              <p className="text-sm font-semibold text-white">Danh sách điểm</p>
              <div className="mt-3 max-h-[360px] space-y-2 overflow-auto pr-1 font-mono text-xs">
                {points.length === 0 ? (
                  <p className="font-sans text-slate-500">Chưa có điểm.</p>
                ) : (
                  points.map(([x, y], index) => (
                    <button
                      key={`${x}-${y}-${index}`}
                      type="button"
                      onClick={() => setSelectedIndex(index)}
                      className={`block w-full rounded-lg border px-3 py-2 text-left ${
                        selectedIndex === index ? "border-pink-400 bg-pink-500/15 text-pink-100" : "border-white/10 bg-ink-900 text-slate-200"
                      }`}
                    >
                      {index + 1}. [{x}, {y}]
                    </button>
                  ))
                )}
              </div>
            </div>
          </aside>
        </div>
      </Card>
    </div>
  );
}

export function TroopCoordinatesPage() {
  return <CoordinateToolPage mode="troops" />;
}

export function SpellCoordinatesPage() {
  return <CoordinateToolPage mode="spells" />;
}
