import { MouseEvent, useEffect, useMemo, useRef, useState } from "react";
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

const targets = [
  { label: "Ảnh trên bên phải", value: "view_trenbenphai" },
  { label: "Ảnh trên bên trái", value: "view_trenbentrai" },
  { label: "Ảnh dưới bên phải", value: "view_duoibenphai" },
  { label: "Ảnh dưới bên trái", value: "view_duoibentrai" },
  { label: "Cạnh trên", value: "edge_top" },
  { label: "Cạnh dưới", value: "edge_bottom" },
  { label: "Cạnh trái", value: "edge_left" },
  { label: "Cạnh phải", value: "edge_right" },
  { label: "Thả theo hàng", value: "line_points" },
  { label: "Bốn góc map", value: "four_corner_points" },
  { label: "Spell nộ/băng", value: "spell_group_points" },
];

function readPoints(config: AppConfig | null, target: string): number[][] {
  const deploy = config?.deploy ?? {};
  if (target === "view_trenbenphai") return deploy.view_points?.trenbenphai ?? [];
  if (target === "view_trenbentrai") return deploy.view_points?.trenbentrai ?? [];
  if (target === "view_duoibenphai") return deploy.view_points?.duoibenphai ?? [];
  if (target === "view_duoibentrai") return deploy.view_points?.duoibentrai ?? [];
  if (target === "edge_top") return deploy.edge_points?.top ?? [];
  if (target === "edge_bottom") return deploy.edge_points?.bottom ?? [];
  if (target === "edge_left") return deploy.edge_points?.left ?? [];
  if (target === "edge_right") return deploy.edge_points?.right ?? [];
  if (target === "line_points") return deploy.line_points ?? [];
  if (target === "four_corner_points") return deploy.four_corner_points ?? [];
  if (target === "spell_group_points") return deploy.spell_groups?.[0]?.points ?? [];
  return [];
}

export function CoordinatesPage() {
  const imageRef = useRef<HTMLImageElement | null>(null);
  const { config, options, isDirty, reload } = useConfigEditor();
  const [referenceImages, setReferenceImages] = useState<ReferenceImageItem[]>([]);
  const [referenceName, setReferenceName] = useState("");
  const [target, setTarget] = useState("edge_top");
  const [comboName, setComboName] = useState("");
  const [image, setImage] = useState<ScreenshotPayload | null>(null);
  const [imageSourceLabel, setImageSourceLabel] = useState("");
  const [points, setPoints] = useState<number[][]>([]);
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null);
  const [busy, setBusy] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    listReferenceImages()
      .then((images) => {
        setReferenceImages(images);
        if (images.length > 0) {
          setReferenceName(images[0].name);
        }
      })
      .catch((err) => setError(apiErrorMessage(err)));
  }, []);

  useEffect(() => {
    setPoints(readPoints(config, target));
    setSelectedIndex(null);
  }, [config, target]);

  useEffect(() => {
    const activeCombo = config?.farm?.combo ?? "";
    if (activeCombo && !comboName) {
      setComboName(activeCombo);
    }
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
      setMessage(`Đã lưu ${points.length} tọa độ vào ${targets.find((item) => item.value === target)?.label}.`);
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
      <Card title="Tool lấy tọa độ" subtitle="Dùng 4 ảnh mẫu trong img/ hoặc chụp ADB trực tiếp, rồi click vào điểm muốn thả.">
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

        <div className="grid gap-4 xl:grid-cols-[1fr_320px]">
          <div className="overflow-hidden rounded-2xl border border-white/10 bg-black/30">
            {imageSrc ? (
              <div className="relative">
                <div className="absolute left-3 top-3 z-10 rounded-full bg-black/65 px-3 py-1 text-xs font-semibold text-white">
                  {imageSourceLabel || "Ảnh tọa độ"} · {image?.width}x{image?.height}
                </div>
                <img ref={imageRef} src={imageSrc} alt="Ảnh tọa độ" onClick={handleImageClick} className="block w-full cursor-crosshair select-none" draggable={false} />
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
            <SelectInput label="Lưu vào nhóm tọa độ" value={target} options={targets} onChange={(event) => setTarget(event.target.value)} />
            <SelectInput
              label="Lưu cho combo"
              value={comboName || config?.farm?.combo || ""}
              options={comboOptions}
              onChange={(event) => setComboName(event.target.value)}
            />
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
              <div className="mt-3 max-h-[420px] space-y-2 overflow-auto pr-1 font-mono text-xs">
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
