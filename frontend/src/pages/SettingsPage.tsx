import { useNavigate } from "react-router-dom";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { PageHeader } from "../components/PageHeader";
import { SelectInput, TextInput, Toggle } from "../components/FormControls";
import { numberValue, useConfigEditor } from "../hooks/useConfigEditor";

export function SettingsPage() {
  const navigate = useNavigate();
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
  const wallUpgrade = config.wall_upgrade ?? {};
  const useDefaultTiming = attackTiming.use_default ?? true;
  const timingDisabled = Boolean(useDefaultTiming);

  return (
    <div>
      <PageHeader
        eyebrow="Hệ thống"
        title="Cài đặt tool"
        subtitle="ADB, OCR, restart định kỳ và nhịp thao tác nâng cao."
        action={
          <Button variant="success" disabled={saving} onClick={save}>
            {saving ? "Đang lưu..." : "Lưu cấu hình"}
          </Button>
        }
      />

      {(error || savedMessage) && (
        <div className={`mb-5 rounded-lg px-4 py-3 text-sm ${error ? "border border-danger/30 bg-danger/10 text-rose-200" : "border border-limewash/30 bg-limewash/10 text-lime-200"}`}>
          {error || savedMessage}
        </div>
      )}

      <div className="grid gap-5 xl:grid-cols-[1fr_380px]">
        <div className="space-y-5">
          <Card title="ADB và game">
            <div className="grid gap-4">
              <TextInput label="ADB path" value={adb.path ?? ""} onChange={(event) => updatePath(["adb", "path"], event.target.value)} />
              <div className="grid gap-4 md:grid-cols-2">
                <TextInput label="Device" value={adb.device ?? "127.0.0.1:5555"} onChange={(event) => updatePath(["adb", "device"], event.target.value)} />
                <TextInput label="Package game" value={adb.package ?? "com.supercell.clashofclans"} onChange={(event) => updatePath(["adb", "package"], event.target.value)} />
              </div>
              <div className="grid gap-3 md:grid-cols-2">
                <Toggle label="Kết nối ADB khi bắt đầu" checked={Boolean(adb.connect_on_start)} onChange={(value) => updatePath(["adb", "connect_on_start"], value)} />
                <Toggle label="Quét sâu tìm ADB" checked={Boolean(adb.deep_scan)} onChange={(value) => updatePath(["adb", "deep_scan"], value)} />
              </div>
            </div>
          </Card>

          <Card title="OCR">
            <div className="grid gap-4">
              <Toggle label="Bật OCR" checked={Boolean(ocr.enabled)} onChange={(value) => updatePath(["ocr", "enabled"], value)} />
              <TextInput label="Tesseract path" value={ocr.tesseract_path ?? ""} onChange={(event) => updatePath(["ocr", "tesseract_path"], event.target.value)} />
            </div>
          </Card>

          <Card title="Delay nâng cao">
            <div className="space-y-5">
              <Toggle
                label="Dùng cấu hình mặc định"
                checked={Boolean(useDefaultTiming)}
                onChange={(value) => updatePath(["attack_timing", "use_default"], value)}
              />

              <div className={timingDisabled ? "pointer-events-none opacity-45" : ""}>
                <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                  <TextInput label="Thả lính (ms)" value={String(attackTiming.troop_delay_ms ?? 80)} onChange={(event) => updatePath(["attack_timing", "troop_delay_ms"], numberValue(event.target.value))} />
                  <TextInput label="Thả băng từ (ms)" value={String(attackTiming.freeze_random_min_ms ?? 0)} onChange={(event) => updatePath(["attack_timing", "freeze_random_min_ms"], numberValue(event.target.value))} />
                  <TextInput label="Thả băng đến (ms)" value={String(attackTiming.freeze_random_max_ms ?? 250)} onChange={(event) => updatePath(["attack_timing", "freeze_random_max_ms"], numberValue(event.target.value))} />
                  <TextInput label="Thả nộ sau từ (ms)" value={String(attackTiming.rage_random_min_ms ?? 500)} onChange={(event) => updatePath(["attack_timing", "rage_random_min_ms"], numberValue(event.target.value))} />
                  <TextInput label="Thả nộ sau đến (ms)" value={String(attackTiming.rage_random_max_ms ?? 1200)} onChange={(event) => updatePath(["attack_timing", "rage_random_max_ms"], numberValue(event.target.value))} />
                  <TextInput label="Skill tướng từ (ms)" value={String(attackTiming.hero_skill_min_ms ?? 2000)} onChange={(event) => updatePath(["attack_timing", "hero_skill_min_ms"], numberValue(event.target.value))} />
                  <TextInput label="Skill tướng đến (ms)" value={String(attackTiming.hero_skill_max_ms ?? 4000)} onChange={(event) => updatePath(["attack_timing", "hero_skill_max_ms"], numberValue(event.target.value))} />
                  <TextInput label="Trận mới từ (ms)" value={String(attackTiming.next_battle_min_ms ?? 2000)} onChange={(event) => updatePath(["attack_timing", "next_battle_min_ms"], numberValue(event.target.value))} />
                  <TextInput label="Trận mới đến (ms)" value={String(attackTiming.next_battle_max_ms ?? 5000)} onChange={(event) => updatePath(["attack_timing", "next_battle_max_ms"], numberValue(event.target.value))} />
                  <TextInput label="Delay quét ADB (giây)" value={String(attackTiming.adb_delay_seconds ?? 0.18)} onChange={(event) => updatePath(["attack_timing", "adb_delay_seconds"], Number(event.target.value || 0))} />
                  <TextInput label="Delay tìm tướng (giây)" value={String(attackTiming.hero_search_delay_seconds ?? 1.5)} onChange={(event) => updatePath(["attack_timing", "hero_search_delay_seconds"], Number(event.target.value || 0))} />
                </div>
                <div className="mt-4">
                  <Toggle label="Chế độ tối ưu" checked={Boolean(attackTiming.optimized_mode)} onChange={(value) => updatePath(["attack_timing", "optimized_mode"], value)} disabled={timingDisabled} />
                </div>
              </div>
            </div>
          </Card>
        </div>

        <div className="space-y-5">
          <Card title="Restart định kỳ">
            <div className="space-y-4">
              <Toggle label="Restart game định kỳ" checked={Boolean(game.periodic_restart_game)} onChange={(value) => updatePath(["game", "periodic_restart_game"], value)} />
              <TextInput label="Restart từ (giây)" value={String(game.periodic_restart_min_seconds)} onChange={(event) => updatePath(["game", "periodic_restart_min_seconds"], numberValue(event.target.value))} />
              <TextInput label="Restart đến (giây)" value={String(game.periodic_restart_max_seconds)} onChange={(event) => updatePath(["game", "periodic_restart_max_seconds"], numberValue(event.target.value))} />
              <TextInput label="Độ phân giải" value={(game.resolution ?? [1600, 900]).join("x")} readOnly />
            </div>
          </Card>

          <Card title="Camera LDPlayer">
            <div className="space-y-4">
              <TextInput
                label="Zoom out ở làng chính (lần)"
                type="number"
                min={0}
                value={String(game.home_zoom_out_keyevents ?? 3)}
                onChange={(event) => updatePath(["game", "home_zoom_out_keyevents"], numberValue(event.target.value))}
              />
              <TextInput
                label="LDPlayer index"
                type="number"
                min={0}
                value={String(game.ldplayer_index ?? 0)}
                onChange={(event) => updatePath(["game", "ldplayer_index"], numberValue(event.target.value))}
              />
            </div>
          </Card>

          <Card title="Nâng tường">
            <div className="space-y-4">
              <Toggle
                label="Bật tự động nâng tường"
                checked={Boolean(wallUpgrade.enabled)}
                onChange={(value) => updatePath(["wall_upgrade", "enabled"], value)}
              />
              <Toggle
                label="Mô phỏng nâng tường"
                checked={Boolean(wallUpgrade.dry_run)}
                onChange={(value) => updatePath(["wall_upgrade", "dry_run"], value)}
              />
              <Toggle
                label="Bật nâng sau số trận"
                checked={Boolean(wallUpgrade.run_after_attacks_enabled ?? true)}
                onChange={(value) => updatePath(["wall_upgrade", "run_after_attacks_enabled"], value)}
              />
              <Toggle
                label="Nâng 10 tường mỗi lần"
                checked={Boolean(wallUpgrade.use_add10)}
                onChange={(value) => updatePath(["wall_upgrade", "use_add10"], value)}
              />
              <div className="grid gap-4 md:grid-cols-2">
                <TextInput
                  label="Chạy sau số trận"
                  type="number"
                  min={1}
                  value={String(wallUpgrade.run_every_n_attacks ?? 20)}
                  onChange={(event) => updatePath(["wall_upgrade", "run_every_n_attacks"], numberValue(event.target.value))}
                />
                <TextInput
                  label="Ngưỡng tài nguyên (%)"
                  type="number"
                  min={1}
                  max={100}
                  value={String(wallUpgrade.trigger_percent ?? 95)}
                  onChange={(event) => updatePath(["wall_upgrade", "trigger_percent"], numberValue(event.target.value))}
                />
              </div>
              <SelectInput
                label="Dùng tài nguyên"
                value={wallUpgrade.pay_with ?? "auto"}
                onChange={(event) => updatePath(["wall_upgrade", "pay_with"], event.target.value)}
                options={[
                  { label: "Tự động", value: "auto" },
                  { label: "Vàng", value: "gold" },
                  { label: "Dầu", value: "elixir" },
                ]}
              />
              <div className="grid gap-4 md:grid-cols-2">
                <TextInput
                  label="Kho vàng tối đa"
                  type="number"
                  min={1}
                  value={String(wallUpgrade.gold_capacity ?? 6000000)}
                  onChange={(event) => updatePath(["wall_upgrade", "gold_capacity"], numberValue(event.target.value))}
                />
                <TextInput
                  label="Kho dầu tối đa"
                  type="number"
                  min={1}
                  value={String(wallUpgrade.elixir_capacity ?? 6000000)}
                  onChange={(event) => updatePath(["wall_upgrade", "elixir_capacity"], numberValue(event.target.value))}
                />
                <TextInput
                  label="Giữ lại vàng"
                  type="number"
                  min={0}
                  value={String(wallUpgrade.reserve_gold ?? 200000)}
                  onChange={(event) => updatePath(["wall_upgrade", "reserve_gold"], numberValue(event.target.value))}
                />
                <TextInput
                  label="Giữ lại dầu"
                  type="number"
                  min={0}
                  value={String(wallUpgrade.reserve_elixir ?? 200000)}
                  onChange={(event) => updatePath(["wall_upgrade", "reserve_elixir"], numberValue(event.target.value))}
                />
              </div>
              <div className="grid gap-4 md:grid-cols-4">
                <TextInput
                  label="Số lần bấm +1"
                  type="number"
                  min={1}
                  value={String(wallUpgrade.add1_rounds ?? 1)}
                  onChange={(event) => updatePath(["wall_upgrade", "add1_rounds"], numberValue(event.target.value))}
                />
                <TextInput
                  label="Tối đa lần bấm +10"
                  type="number"
                  min={1}
                  value={String(wallUpgrade.max_add_rounds ?? 10)}
                  onChange={(event) => updatePath(["wall_upgrade", "max_add_rounds"], numberValue(event.target.value))}
                />
                <TextInput
                  label="Nghỉ lỗi tạm thời"
                  type="number"
                  min={1}
                  value={String(wallUpgrade.temporary_retry_backoff_attacks ?? 2)}
                  onChange={(event) => updatePath(["wall_upgrade", "temporary_retry_backoff_attacks"], numberValue(event.target.value))}
                />
                <TextInput
                  label="Nghỉ sau lỗi (trận)"
                  type="number"
                  min={1}
                  value={String(wallUpgrade.retry_backoff_attacks ?? 10)}
                  onChange={(event) => updatePath(["wall_upgrade", "retry_backoff_attacks"], numberValue(event.target.value))}
                />
              </div>
            </div>
          </Card>

          <Card title="Tọa độ thuốc">
            <div className="space-y-4">
              <TextInput
                label="Khoảng cách tối thiểu giữa 2 điểm thuốc (px)"
                type="number"
                min={0}
                value={String(attackTiming.spell_min_point_distance_px ?? 120)}
                onChange={(event) => updatePath(["attack_timing", "spell_min_point_distance_px"], numberValue(event.target.value))}
              />
              <Button className="w-full bg-violet-500 hover:bg-violet-400" onClick={() => navigate("/coordinates/spells?target=spell_group_zone_trenbenphai")}>
                Mở tọa độ Nộ/Băng
              </Button>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
