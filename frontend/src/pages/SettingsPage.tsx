import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { TextInput, Toggle } from "../components/FormControls";
import { numberValue, useConfigEditor } from "../hooks/useConfigEditor";

export function SettingsPage() {
  const { config, loading, saving, error, savedMessage, updatePath, save } = useConfigEditor();

  if (loading) {
    return <Card title="Cài đặt">Đang tải cấu hình...</Card>;
  }
  if (!config) {
    return <Card title="Cài đặt">{error || "Không tải được cấu hình."}</Card>;
  }

  const adb = config.adb;
  const game = config.game;
  const ocr = config.ocr;
  const attackTiming = config.attack_timing ?? {};
  const useDefaultTiming = attackTiming.use_default ?? true;
  const timingDisabled = Boolean(useDefaultTiming);

  return (
    <div className="space-y-5">
      <Card
        title="Kết nối hệ thống"
        subtitle="Cấu hình local cho ADB, LDPlayer và Tesseract OCR."
        action={
          <Button variant="success" disabled={saving} onClick={save}>
            {saving ? "Đang lưu..." : "Lưu cấu hình"}
          </Button>
        }
      >
        {(error || savedMessage) && (
          <div className={`mb-4 rounded-lg px-4 py-3 text-sm ${error ? "border border-danger/30 bg-danger/10 text-rose-200" : "border border-limewash/30 bg-limewash/10 text-lime-200"}`}>
            {error || savedMessage}
          </div>
        )}
        <div className="grid gap-4">
          <TextInput label="ADB path" hint="Có thể để trống để tool tự dò adb.exe." value={adb.path ?? ""} onChange={(event) => updatePath(["adb", "path"], event.target.value)} />
          <TextInput label="Device" value={adb.device ?? "127.0.0.1:5555"} onChange={(event) => updatePath(["adb", "device"], event.target.value)} />
          <TextInput label="Package game" value={adb.package ?? "com.supercell.clashofclans"} onChange={(event) => updatePath(["adb", "package"], event.target.value)} />
          <TextInput label="Tesseract path" hint="Ví dụ: C:\\Program Files\\Tesseract-OCR\\tesseract.exe" value={ocr.tesseract_path ?? ""} onChange={(event) => updatePath(["ocr", "tesseract_path"], event.target.value)} />
        </div>
      </Card>

      <Card title="Restart và bảo vệ phiên" subtitle="Các giới hạn giúp bot tự phục hồi khi OCR/ADB lỗi.">
        <div className="grid gap-3 md:grid-cols-2">
          <Toggle label="Kết nối ADB khi bắt đầu" checked={Boolean(adb.connect_on_start)} onChange={(value) => updatePath(["adb", "connect_on_start"], value)} />
          <Toggle label="Bật OCR" checked={Boolean(ocr.enabled)} onChange={(value) => updatePath(["ocr", "enabled"], value)} />
          <Toggle label="Restart game định kỳ" checked={Boolean(game.periodic_restart_game)} onChange={(value) => updatePath(["game", "periodic_restart_game"], value)} />
        </div>
        <div className="mt-4 grid gap-4 md:grid-cols-3">
          <TextInput label="Restart từ (giây)" value={String(game.periodic_restart_min_seconds)} onChange={(event) => updatePath(["game", "periodic_restart_min_seconds"], numberValue(event.target.value))} />
          <TextInput label="Restart đến (giây)" value={String(game.periodic_restart_max_seconds)} onChange={(event) => updatePath(["game", "periodic_restart_max_seconds"], numberValue(event.target.value))} />
          <TextInput label="Độ phân giải" value={(game.resolution ?? [1600, 900]).join("x")} readOnly />
        </div>
      </Card>

      <Card title="Delay & tọa độ" subtitle="Tinh chỉnh nhịp thả quân, spell và khoảng nghỉ giữa các trận.">
        <div className="space-y-5">
          <Toggle
            label="Dùng cấu hình mặc định (Tọa độ & Delay chuẩn)"
            checked={Boolean(useDefaultTiming)}
            onChange={(value) => updatePath(["attack_timing", "use_default"], value)}
          />

          <div className={timingDisabled ? "pointer-events-none opacity-45" : ""}>
            <h3 className="mb-4 text-sm font-bold uppercase tracking-wide text-slate-300">Cài đặt Delay</h3>
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              <TextInput label="Thả lính (ms)" value={String(attackTiming.troop_delay_ms ?? 150)} onChange={(event) => updatePath(["attack_timing", "troop_delay_ms"], numberValue(event.target.value))} />
              <TextInput label="Thả băng từ (ms)" value={String(attackTiming.freeze_random_min_ms ?? 0)} onChange={(event) => updatePath(["attack_timing", "freeze_random_min_ms"], numberValue(event.target.value))} />
              <TextInput label="Thả băng đến (ms)" value={String(attackTiming.freeze_random_max_ms ?? 1000)} onChange={(event) => updatePath(["attack_timing", "freeze_random_max_ms"], numberValue(event.target.value))} />
              <TextInput label="Thả nộ sau từ (ms)" value={String(attackTiming.rage_random_min_ms ?? 2000)} onChange={(event) => updatePath(["attack_timing", "rage_random_min_ms"], numberValue(event.target.value))} />
              <TextInput label="Thả nộ sau đến (ms)" value={String(attackTiming.rage_random_max_ms ?? 4000)} onChange={(event) => updatePath(["attack_timing", "rage_random_max_ms"], numberValue(event.target.value))} />
              <TextInput label="Quân giáo kích hoạt từ (ms)" value={String(attackTiming.siege_activation_min_ms ?? 5000)} onChange={(event) => updatePath(["attack_timing", "siege_activation_min_ms"], numberValue(event.target.value))} />
              <TextInput label="Quân giáo kích hoạt đến (ms)" value={String(attackTiming.siege_activation_max_ms ?? 7000)} onChange={(event) => updatePath(["attack_timing", "siege_activation_max_ms"], numberValue(event.target.value))} />
              <TextInput label="Skill tướng từ (ms)" value={String(attackTiming.hero_skill_min_ms ?? 2000)} onChange={(event) => updatePath(["attack_timing", "hero_skill_min_ms"], numberValue(event.target.value))} />
              <TextInput label="Skill tướng đến (ms)" value={String(attackTiming.hero_skill_max_ms ?? 4000)} onChange={(event) => updatePath(["attack_timing", "hero_skill_max_ms"], numberValue(event.target.value))} />
              <TextInput label="Trận mới từ (ms)" value={String(attackTiming.next_battle_min_ms ?? 2000)} onChange={(event) => updatePath(["attack_timing", "next_battle_min_ms"], numberValue(event.target.value))} />
              <TextInput label="Trận mới đến (ms)" value={String(attackTiming.next_battle_max_ms ?? 5000)} onChange={(event) => updatePath(["attack_timing", "next_battle_max_ms"], numberValue(event.target.value))} />
              <TextInput label="Delay quét ADB (giây)" value={String(attackTiming.adb_delay_seconds ?? 0.3)} onChange={(event) => updatePath(["attack_timing", "adb_delay_seconds"], Number(event.target.value || 0))} />
              <TextInput label="Delay tìm tướng (giây)" value={String(attackTiming.hero_search_delay_seconds ?? 1.5)} onChange={(event) => updatePath(["attack_timing", "hero_search_delay_seconds"], Number(event.target.value || 0))} />
            </div>
          </div>

          <div className="grid gap-4 lg:grid-cols-[1fr_1.2fr]">
            <Toggle
              label="Chế độ Tối ưu"
              checked={Boolean(attackTiming.optimized_mode)}
              onChange={(value) => updatePath(["attack_timing", "optimized_mode"], value)}
              disabled={timingDisabled}
            />
            <div className="rounded-xl border border-white/10 bg-black/25 p-4 text-sm text-slate-400">
              Phù hợp với đa giả lập nhưng thao tác sẽ bị chậm hơn. Hiện chưa bật riêng cho MuMu Player.
            </div>
          </div>

          <div className="rounded-2xl border border-white/10 bg-ink-900 p-5">
            <h3 className="text-base font-bold text-white">Tùy chỉnh tọa độ thả spell</h3>
            <p className="mt-2 max-w-2xl text-sm text-slate-400">
              Dùng để thiết lập nhanh tọa độ thả spell theo góc nhìn. Giai đoạn này tool tọa độ sẽ mở sau, còn tọa độ hiện đang lưu trong config.
            </p>
            <Button className="mt-4 w-full bg-pink-600 hover:bg-pink-500" onClick={() => window.alert("Tool tọa độ sẽ làm ở bước sau. Hiện chỉnh tọa độ trực tiếp trong config.")}>
              Mở Tool Tọa Độ
            </Button>
          </div>
        </div>
      </Card>
    </div>
  );
}
