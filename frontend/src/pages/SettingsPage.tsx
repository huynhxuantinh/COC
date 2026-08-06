import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { Feedback, LoadingState } from "../components/Feedback";
import { TextInput, Toggle } from "../components/FormControls";
import { PageHeader } from "../components/PageHeader";
import { numberValue, useConfigEditor } from "../hooks/useConfigEditor";

export function SettingsPage() {
  const { config, loading, saving, error, savedMessage, updatePath, save } = useConfigEditor();
  if (loading) return <LoadingState label="Đang tải cài đặt..." />;
  if (!config) return <Feedback tone="error">{error || "Không tải được cấu hình."}</Feedback>;

  const adb = config.adb;
  const game = config.game;
  const farm = config.farm;
  const ocr = config.ocr;
  const attackTiming = config.attack_timing ?? {};
  const customTiming = !(attackTiming.use_default ?? true);

  return (
    <div>
      <PageHeader eyebrow="Hệ thống" title="Cài đặt" subtitle="Kết nối giả lập, OCR, phục hồi phiên và timing kỹ thuật." action={<Button variant="success" loading={saving} onClick={save}>Lưu cấu hình</Button>} />
      {error ? <Feedback tone="error" className="mb-5">{error}</Feedback> : savedMessage ? <Feedback tone="success" className="mb-5">{savedMessage}</Feedback> : null}

      <div className="grid gap-5 xl:grid-cols-2">
        <div className="space-y-5">
          <Card title="ADB và LDPlayer">
            <div className="space-y-4">
              <TextInput label="Đường dẫn ADB" hint="Để trống nếu dùng Quét ADB ở Tổng quan." value={adb.path ?? ""} onChange={(event) => updatePath(["adb", "path"], event.target.value)} />
              <div className="grid gap-4 sm:grid-cols-2">
                <TextInput label="Device" value={adb.device ?? "127.0.0.1:5555"} onChange={(event) => updatePath(["adb", "device"], event.target.value)} />
                <TextInput type="number" min={0} label="LDPlayer index" value={String(game.ldplayer_index ?? 0)} onChange={(event) => updatePath(["game", "ldplayer_index"], numberValue(event.target.value))} />
                <TextInput label="Package game" value={adb.package ?? "com.supercell.clashofclans"} onChange={(event) => updatePath(["adb", "package"], event.target.value)} />
                <TextInput label="Độ phân giải" value={(game.resolution ?? [1600, 900]).join("x")} readOnly />
                <TextInput type="number" min={0} suffix="lần" label="Zoom out ở làng chính" value={String(game.home_zoom_out_keyevents ?? 3)} onChange={(event) => updatePath(["game", "home_zoom_out_keyevents"], numberValue(event.target.value))} />
              </div>
              <div className="grid gap-3 sm:grid-cols-2">
                <Toggle label="Kết nối ADB khi bắt đầu" checked={Boolean(adb.connect_on_start)} onChange={(value) => updatePath(["adb", "connect_on_start"], value)} />
                <Toggle label="Quét sâu tìm ADB" hint="Chỉ bật khi quét nhanh không thấy LDPlayer." checked={Boolean(adb.deep_scan)} onChange={(value) => updatePath(["adb", "deep_scan"], value)} />
              </div>
            </div>
          </Card>

          <Card title="OCR">
            <div className="space-y-4">
              <Toggle label="Bật OCR" checked={Boolean(ocr.enabled)} onChange={(value) => updatePath(["ocr", "enabled"], value)} />
              {ocr.enabled ? <TextInput label="Đường dẫn Tesseract" value={ocr.tesseract_path ?? ""} onChange={(event) => updatePath(["ocr", "tesseract_path"], event.target.value)} /> : null}
            </div>
          </Card>
        </div>

        <div className="space-y-5">
          <Card title="Bảo vệ phiên">
            <div className="space-y-3">
              <Toggle label="Không thấy Attack thì mở lại game" checked={Boolean(game.restart_if_attack_missing)} onChange={(value) => updatePath(["game", "restart_if_attack_missing"], value)} />
              <Toggle label="Tự động dừng" checked={Boolean(game.auto_stop)} onChange={(value) => updatePath(["game", "auto_stop"], value)} />
              {game.auto_stop ? <TextInput type="number" min={1} suffix="giây" label="Dừng sau" value={String(game.auto_restart_after_seconds)} onChange={(event) => updatePath(["game", "auto_restart_after_seconds"], numberValue(event.target.value))} /> : null}
              <Toggle label="Bỏ qua restart game khi khởi động" checked={Boolean(game.skip_restart_game)} onChange={(value) => updatePath(["game", "skip_restart_game"], value)} />
            </div>
            <details className="mt-5 rounded-lg border border-white/10 bg-black/20 p-4">
              <summary className="cursor-pointer text-sm font-semibold text-slate-200">Ngưỡng phục hồi</summary>
              <div className="mt-4 grid gap-4 border-t border-white/10 pt-4 sm:grid-cols-2">
                <TextInput type="number" min={0} suffix="giây" label="OCR loot lỗi" value={String(farm.ocr_fail_restart_seconds)} onChange={(event) => updatePath(["farm", "ocr_fail_restart_seconds"], numberValue(event.target.value))} />
                <TextInput type="number" min={1} suffix="lần" label="Restart OCR loot tối đa" value={String(farm.max_ocr_restarts ?? 3)} onChange={(event) => updatePath(["farm", "max_ocr_restarts"], numberValue(event.target.value))} />
                <TextInput type="number" min={1} suffix="lần" label="Lỗi cycle tối đa" value={String(game.max_consecutive_cycle_errors)} onChange={(event) => updatePath(["game", "max_consecutive_cycle_errors"], numberValue(event.target.value))} />
                <TextInput type="number" min={1} suffix="lần" label="Home restart fail tối đa" value={String(game.max_home_restart_failures ?? 3)} onChange={(event) => updatePath(["game", "max_home_restart_failures"], numberValue(event.target.value))} />
                <TextInput type="number" min={1} suffix="giây" label="Chờ restart game" value={String(game.restart_wait_seconds)} onChange={(event) => updatePath(["game", "restart_wait_seconds"], numberValue(event.target.value))} />
                <TextInput type="number" min={1} suffix="giây" label="Chờ màn hình kết quả" value={String(game.result_wait_seconds ?? 15)} onChange={(event) => updatePath(["game", "result_wait_seconds"], numberValue(event.target.value))} />
              </div>
            </details>
          </Card>

          <Card title="Restart định kỳ">
            <div className="space-y-4">
              <Toggle label="Restart game định kỳ" checked={Boolean(game.periodic_restart_game)} onChange={(value) => updatePath(["game", "periodic_restart_game"], value)} />
              {game.periodic_restart_game ? (
                <div className="grid gap-4 sm:grid-cols-2">
                  <TextInput type="number" min={1} suffix="giây" label="Restart từ" value={String(game.periodic_restart_min_seconds)} onChange={(event) => updatePath(["game", "periodic_restart_min_seconds"], numberValue(event.target.value))} />
                  <TextInput type="number" min={1} suffix="giây" label="Restart đến" value={String(game.periodic_restart_max_seconds)} onChange={(event) => updatePath(["game", "periodic_restart_max_seconds"], numberValue(event.target.value))} />
                </div>
              ) : null}
            </div>
          </Card>
        </div>

        <div className="space-y-5 xl:col-span-2">
          <Card title="Timing thao tác">
            <div className="space-y-5">
              <Toggle label="Kích hoạt kỹ năng tướng" checked={Boolean(attackTiming.activate_hero_skill ?? true)} onChange={(value) => updatePath(["attack_timing", "activate_hero_skill"], value)} />
              <Toggle label="Dùng timing tùy chỉnh" hint="Tắt để dùng delay riêng trong sequence của combo." checked={customTiming} onChange={(value) => updatePath(["attack_timing", "use_default"], !value)} />
              {customTiming ? (
                <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                  <TextInput type="number" min={0} suffix="ms" label="Delay thả lính" value={String(attackTiming.troop_delay_ms ?? 80)} onChange={(event) => updatePath(["attack_timing", "troop_delay_ms"], numberValue(event.target.value))} />
                  <TextInput type="number" min={0} suffix="ms" label="Băng từ" value={String(attackTiming.freeze_random_min_ms ?? 0)} onChange={(event) => updatePath(["attack_timing", "freeze_random_min_ms"], numberValue(event.target.value))} />
                  <TextInput type="number" min={0} suffix="ms" label="Băng đến" value={String(attackTiming.freeze_random_max_ms ?? 250)} onChange={(event) => updatePath(["attack_timing", "freeze_random_max_ms"], numberValue(event.target.value))} />
                  <TextInput type="number" min={0} suffix="ms" label="Nộ từ" value={String(attackTiming.rage_random_min_ms ?? 500)} onChange={(event) => updatePath(["attack_timing", "rage_random_min_ms"], numberValue(event.target.value))} />
                  <TextInput type="number" min={0} suffix="ms" label="Nộ đến" value={String(attackTiming.rage_random_max_ms ?? 1200)} onChange={(event) => updatePath(["attack_timing", "rage_random_max_ms"], numberValue(event.target.value))} />
                  <TextInput type="number" min={0.01} step={0.01} suffix="giây" label="Delay quét ADB" value={String(attackTiming.adb_delay_seconds ?? 0.18)} onChange={(event) => updatePath(["attack_timing", "adb_delay_seconds"], Number(event.target.value || 0))} />
                </div>
              ) : null}
            </div>
          </Card>

          <details className="rounded-lg border border-white/10 bg-ink-850/90 p-5">
            <summary className="cursor-pointer text-sm font-semibold text-white">Timing nâng cao</summary>
            <div className="mt-5 grid gap-4 border-t border-white/10 pt-5 sm:grid-cols-2 lg:grid-cols-3">
              <TextInput type="number" min={0} suffix="ms" label="Skill tướng từ" value={String(attackTiming.hero_skill_min_ms ?? 2000)} onChange={(event) => updatePath(["attack_timing", "hero_skill_min_ms"], numberValue(event.target.value))} />
              <TextInput type="number" min={0} suffix="ms" label="Skill tướng đến" value={String(attackTiming.hero_skill_max_ms ?? 4000)} onChange={(event) => updatePath(["attack_timing", "hero_skill_max_ms"], numberValue(event.target.value))} />
              <TextInput type="number" min={0} suffix="ms" label="Trận mới từ" value={String(attackTiming.next_battle_min_ms ?? 2000)} onChange={(event) => updatePath(["attack_timing", "next_battle_min_ms"], numberValue(event.target.value))} />
              <TextInput type="number" min={0} suffix="ms" label="Trận mới đến" value={String(attackTiming.next_battle_max_ms ?? 5000)} onChange={(event) => updatePath(["attack_timing", "next_battle_max_ms"], numberValue(event.target.value))} />
              <TextInput type="number" min={0} step={0.1} suffix="giây" label="Delay tìm tướng" value={String(attackTiming.hero_search_delay_seconds ?? 1.5)} onChange={(event) => updatePath(["attack_timing", "hero_search_delay_seconds"], Number(event.target.value || 0))} />
              <Toggle label="Chế độ tối ưu" checked={Boolean(attackTiming.optimized_mode)} onChange={(value) => updatePath(["attack_timing", "optimized_mode"], value)} disabled={!customTiming} />
            </div>
          </details>
        </div>
      </div>
    </div>
  );
}
