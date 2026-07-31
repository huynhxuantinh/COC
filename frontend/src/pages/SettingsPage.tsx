import { ExternalLink } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { Feedback, LoadingState } from "../components/Feedback";
import { SelectInput, TextInput, Toggle } from "../components/FormControls";
import { PageHeader } from "../components/PageHeader";
import { numberValue, useConfigEditor } from "../hooks/useConfigEditor";

function SectionLabel({ children }: { children: string }) {
  return <h3 className="border-b border-white/10 pb-2 text-xs font-bold uppercase tracking-[0.16em] text-slate-500">{children}</h3>;
}

export function SettingsPage() {
  const navigate = useNavigate();
  const { config, loading, saving, error, savedMessage, updatePath, save } = useConfigEditor();
  if (loading) return <LoadingState label="Đang tải cài đặt..." />;
  if (!config) return <Feedback tone="error">{error || "Không tải được cấu hình."}</Feedback>;

  const adb = config.adb;
  const game = config.game;
  const ocr = config.ocr;
  const attackTiming = config.attack_timing ?? {};
  const wall = config.wall_upgrade ?? {};
  const customTiming = !(attackTiming.use_default ?? true);
  const wallEnabled = Boolean(wall.enabled);

  return (
    <div>
      <PageHeader eyebrow="Hệ thống" title="Cài đặt" subtitle="Kết nối, timing và các cơ chế tự động ít thay đổi." action={<Button variant="success" loading={saving} onClick={save}>Lưu cấu hình</Button>} />
      {error ? <Feedback tone="error" className="mb-5">{error}</Feedback> : savedMessage ? <Feedback tone="success" className="mb-5">{savedMessage}</Feedback> : null}

      <div className="grid gap-5 xl:grid-cols-2">
        <div className="space-y-5">
          <Card title="ADB và LDPlayer">
            <div className="space-y-4">
              <TextInput label="Đường dẫn ADB" hint="Để trống nếu muốn dùng chức năng Quét ADB ở trang Tổng quan." value={adb.path ?? ""} onChange={(event) => updatePath(["adb", "path"], event.target.value)} />
              <div className="grid gap-4 sm:grid-cols-2">
                <TextInput label="Device" value={adb.device ?? "127.0.0.1:5555"} onChange={(event) => updatePath(["adb", "device"], event.target.value)} />
                <TextInput type="number" min={0} label="LDPlayer index" value={String(game.ldplayer_index ?? 0)} onChange={(event) => updatePath(["game", "ldplayer_index"], numberValue(event.target.value))} />
                <TextInput label="Package game" value={adb.package ?? "com.supercell.clashofclans"} onChange={(event) => updatePath(["adb", "package"], event.target.value)} />
                <TextInput type="number" min={0} suffix="lần" label="Zoom out ở làng chính" value={String(game.home_zoom_out_keyevents ?? 3)} onChange={(event) => updatePath(["game", "home_zoom_out_keyevents"], numberValue(event.target.value))} />
              </div>
              <div className="grid gap-3 sm:grid-cols-2">
                <Toggle label="Kết nối ADB khi bắt đầu" checked={Boolean(adb.connect_on_start)} onChange={(value) => updatePath(["adb", "connect_on_start"], value)} />
                <Toggle label="Quét sâu tìm ADB" hint="Chỉ bật khi quét nhanh không tìm thấy LDPlayer." checked={Boolean(adb.deep_scan)} onChange={(value) => updatePath(["adb", "deep_scan"], value)} />
              </div>
            </div>
          </Card>

          <Card title="OCR">
            <div className="space-y-4">
              <Toggle label="Bật OCR" checked={Boolean(ocr.enabled)} onChange={(value) => updatePath(["ocr", "enabled"], value)} />
              {ocr.enabled ? <TextInput label="Đường dẫn Tesseract" value={ocr.tesseract_path ?? ""} onChange={(event) => updatePath(["ocr", "tesseract_path"], event.target.value)} /> : null}
            </div>
          </Card>

          <Card title="Timing thao tác">
            <div className="space-y-5">
              <Toggle label="Dùng timing tùy chỉnh" hint="Tắt để dùng delay riêng trong sequence của combo." checked={customTiming} onChange={(value) => updatePath(["attack_timing", "use_default"], !value)} />
              {customTiming ? (
                <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                  <TextInput type="number" min={0} suffix="ms" label="Delay thả lính" value={String(attackTiming.troop_delay_ms ?? 80)} onChange={(event) => updatePath(["attack_timing", "troop_delay_ms"], numberValue(event.target.value))} />
                  <TextInput type="number" min={0} suffix="ms" label="Băng từ" value={String(attackTiming.freeze_random_min_ms ?? 0)} onChange={(event) => updatePath(["attack_timing", "freeze_random_min_ms"], numberValue(event.target.value))} />
                  <TextInput type="number" min={0} suffix="ms" label="Băng đến" value={String(attackTiming.freeze_random_max_ms ?? 250)} onChange={(event) => updatePath(["attack_timing", "freeze_random_max_ms"], numberValue(event.target.value))} />
                  <TextInput type="number" min={0} suffix="ms" label="Nộ từ" value={String(attackTiming.rage_random_min_ms ?? 500)} onChange={(event) => updatePath(["attack_timing", "rage_random_min_ms"], numberValue(event.target.value))} />
                  <TextInput type="number" min={0} suffix="ms" label="Nộ đến" value={String(attackTiming.rage_random_max_ms ?? 1200)} onChange={(event) => updatePath(["attack_timing", "rage_random_max_ms"], numberValue(event.target.value))} />
                  <TextInput type="number" min={0} step={0.01} suffix="giây" label="Delay quét ADB" value={String(attackTiming.adb_delay_seconds ?? 0.18)} onChange={(event) => updatePath(["attack_timing", "adb_delay_seconds"], Number(event.target.value || 0))} />
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
              <div className="sm:col-span-2 lg:col-span-3"><Toggle label="Chế độ tối ưu" checked={Boolean(attackTiming.optimized_mode)} onChange={(value) => updatePath(["attack_timing", "optimized_mode"], value)} disabled={!customTiming} /></div>
            </div>
          </details>
        </div>

        <div className="space-y-5">
          <Card title="Restart định kỳ">
            <div className="space-y-4">
              <Toggle label="Restart game định kỳ" checked={Boolean(game.periodic_restart_game)} onChange={(value) => updatePath(["game", "periodic_restart_game"], value)} />
              {game.periodic_restart_game ? (
                <div className="grid gap-4 sm:grid-cols-2">
                  <TextInput type="number" min={0} suffix="giây" label="Restart từ" value={String(game.periodic_restart_min_seconds)} onChange={(event) => updatePath(["game", "periodic_restart_min_seconds"], numberValue(event.target.value))} />
                  <TextInput type="number" min={0} suffix="giây" label="Restart đến" value={String(game.periodic_restart_max_seconds)} onChange={(event) => updatePath(["game", "periodic_restart_max_seconds"], numberValue(event.target.value))} />
                </div>
              ) : null}
              <TextInput label="Độ phân giải game" value={(game.resolution ?? [1600, 900]).join("x")} readOnly />
            </div>
          </Card>

          <Card title="Tọa độ thuốc" subtitle="Khoảng cách ngẫu nhiên tối thiểu để tránh cast trùng.">
            <div className="grid gap-4 sm:grid-cols-[1fr_auto] sm:items-end">
              <TextInput type="number" min={0} suffix="px" label="Khoảng cách giữa hai điểm" value={String(attackTiming.spell_min_point_distance_px ?? 120)} onChange={(event) => updatePath(["attack_timing", "spell_min_point_distance_px"], numberValue(event.target.value))} />
              <Button variant="primary" onClick={() => navigate("/coordinates/spells?target=spell_group_0_zone_trenbenphai")}><ExternalLink className="h-4 w-4" />Mở editor</Button>
            </div>
          </Card>

          <Card title="Nâng tường" action={wall.dry_run && wallEnabled ? <span className="rounded-full bg-amber-400/15 px-3 py-1 text-xs font-bold text-amber-200">Mô phỏng</span> : null}>
            <div className="space-y-5">
              <Toggle label="Bật tự động nâng tường" checked={wallEnabled} onChange={(value) => updatePath(["wall_upgrade", "enabled"], value)} />
              <fieldset disabled={!wallEnabled} className="space-y-5 disabled:opacity-45">
                <div className="space-y-3">
                  <SectionLabel>Kích hoạt</SectionLabel>
                  <Toggle label="Mô phỏng nâng tường" hint="Bot kiểm tra và ghi log nhưng không xác nhận nâng thật." checked={Boolean(wall.dry_run)} onChange={(value) => updatePath(["wall_upgrade", "dry_run"], value)} />
                  <Toggle label="Nâng sau số trận" checked={Boolean(wall.run_after_attacks_enabled ?? true)} onChange={(value) => updatePath(["wall_upgrade", "run_after_attacks_enabled"], value)} />
                  {wall.run_after_attacks_enabled ? <TextInput type="number" min={1} suffix="trận" label="Chu kỳ nâng" value={String(wall.run_every_n_attacks ?? 20)} onChange={(event) => updatePath(["wall_upgrade", "run_every_n_attacks"], numberValue(event.target.value))} /> : null}
                </div>

                <div className="space-y-4">
                  <SectionLabel>Điều kiện tài nguyên</SectionLabel>
                  <div className="grid gap-4 sm:grid-cols-2">
                    <TextInput type="number" min={1} max={100} suffix="%" label="Ngưỡng kích hoạt" value={String(wall.trigger_percent ?? 95)} onChange={(event) => updatePath(["wall_upgrade", "trigger_percent"], numberValue(event.target.value))} />
                    <SelectInput label="Nguồn thanh toán" value={wall.pay_with ?? "auto"} onChange={(event) => updatePath(["wall_upgrade", "pay_with"], event.target.value)} options={[{ label: "Tự động", value: "auto" }, { label: "Vàng", value: "gold" }, { label: "Dầu", value: "elixir" }]} />
                    <TextInput type="number" min={1} label="Kho vàng tối đa" value={String(wall.gold_capacity ?? 6000000)} onChange={(event) => updatePath(["wall_upgrade", "gold_capacity"], numberValue(event.target.value))} />
                    <TextInput type="number" min={1} label="Kho dầu tối đa" value={String(wall.elixir_capacity ?? 6000000)} onChange={(event) => updatePath(["wall_upgrade", "elixir_capacity"], numberValue(event.target.value))} />
                    <TextInput type="number" min={0} label="Giữ lại vàng" value={String(wall.reserve_gold ?? 200000)} onChange={(event) => updatePath(["wall_upgrade", "reserve_gold"], numberValue(event.target.value))} />
                    <TextInput type="number" min={0} label="Giữ lại dầu" value={String(wall.reserve_elixir ?? 200000)} onChange={(event) => updatePath(["wall_upgrade", "reserve_elixir"], numberValue(event.target.value))} />
                  </div>
                </div>

                <div className="space-y-4">
                  <SectionLabel>Số lần thao tác</SectionLabel>
                  <Toggle label="Dùng nút +10" checked={Boolean(wall.use_add10)} onChange={(value) => updatePath(["wall_upgrade", "use_add10"], value)} />
                  {wall.use_add10 ? (
                    <TextInput type="number" min={1} suffix="lần" label="Tối đa số lần bấm +10" value={String(wall.max_add_rounds ?? 10)} onChange={(event) => updatePath(["wall_upgrade", "max_add_rounds"], numberValue(event.target.value))} />
                  ) : (
                    <TextInput type="number" min={1} suffix="lần" label="Số lần bấm +1" value={String(wall.add1_rounds ?? 1)} onChange={(event) => updatePath(["wall_upgrade", "add1_rounds"], numberValue(event.target.value))} />
                  )}
                </div>

                <div className="space-y-4">
                  <SectionLabel>Xử lý lỗi và cooldown</SectionLabel>
                  <div className="grid gap-4 sm:grid-cols-2">
                    <TextInput type="number" min={1} suffix="trận" label="Nghỉ khi lỗi tạm thời" value={String(wall.temporary_retry_backoff_attacks ?? 2)} onChange={(event) => updatePath(["wall_upgrade", "temporary_retry_backoff_attacks"], numberValue(event.target.value))} />
                    <TextInput type="number" min={1} suffix="trận" label="Nghỉ khi lỗi thực" value={String(wall.retry_backoff_attacks ?? 10)} onChange={(event) => updatePath(["wall_upgrade", "retry_backoff_attacks"], numberValue(event.target.value))} />
                  </div>
                </div>

                <details className="rounded-lg border border-white/10 bg-black/20 p-4">
                  <summary className="cursor-pointer text-sm font-semibold text-slate-200">Nâng cao</summary>
                  <div className="mt-4 grid gap-4 border-t border-white/10 pt-4 sm:grid-cols-2">
                    <TextInput type="number" min={1} suffix="lần" label="Tối đa cuộn tìm Wall" value={String(wall.max_wall_search_scrolls ?? 9)} onChange={(event) => updatePath(["wall_upgrade", "max_wall_search_scrolls"], numberValue(event.target.value))} />
                    <TextInput type="number" min={1} suffix="lần" label="Số lần đọc tài nguyên" value={String(wall.resource_read_attempts ?? 3)} onChange={(event) => updatePath(["wall_upgrade", "resource_read_attempts"], numberValue(event.target.value))} />
                    <TextInput type="number" min={1} suffix="lần" label="Số lần đọc giá" value={String(wall.cost_read_attempts ?? 3)} onChange={(event) => updatePath(["wall_upgrade", "cost_read_attempts"], numberValue(event.target.value))} />
                    <TextInput type="number" min={0} step={0.05} suffix="giây" label="Delay mỗi lần đọc" value={String(wall.read_attempt_delay ?? 0.45)} onChange={(event) => updatePath(["wall_upgrade", "read_attempt_delay"], Number(event.target.value || 0))} />
                  </div>
                </details>
              </fieldset>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
