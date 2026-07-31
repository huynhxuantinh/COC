import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { Feedback, LoadingState } from "../components/Feedback";
import { SelectInput, TextInput, Toggle } from "../components/FormControls";
import { PageHeader } from "../components/PageHeader";
import { SegmentedControl } from "../components/SegmentedControl";
import { numberValue, useConfigEditor } from "../hooks/useConfigEditor";

const viewOptions = [
  { value: "trenbenphai", label: "Trên phải" },
  { value: "trenbentrai", label: "Trên trái" },
  { value: "duoibenphai", label: "Dưới phải" },
  { value: "duoibentrai", label: "Dưới trái" },
  { value: "random", label: "Ngẫu nhiên" },
];

export function FarmPage() {
  const { config, options, loading, saving, error, savedMessage, updatePath, save } = useConfigEditor();
  if (loading) return <LoadingState label="Đang tải cấu hình Farm..." />;
  if (!config) return <Feedback tone="error">{error || "Không tải được cấu hình."}</Feedback>;

  const game = config.game;
  const farm = config.farm;
  const combo = config.combos?.[farm.combo];
  const comboSequence = combo?.deploy?.sequence ?? combo?.sequence ?? [];
  const comboOptions = (options?.combos ?? Object.keys(config.combos ?? {})).map((name) => ({ label: name, value: name }));

  return (
    <div>
      <PageHeader eyebrow="Farm" title="Cấu hình tìm nhà" subtitle="Chọn combo, điều kiện tài nguyên và góc triển khai quân." action={<Button variant="success" loading={saving} onClick={save}>Lưu cấu hình</Button>} />
      {error ? <Feedback tone="error" className="mb-5">{error}</Feedback> : savedMessage ? <Feedback tone="success" className="mb-5">{savedMessage}</Feedback> : null}

      <div className="space-y-5">
        <Card title="Combo chạy">
          <div className="grid gap-4 md:grid-cols-[minmax(240px,420px)_1fr] md:items-end">
            <SelectInput label="Combo" value={farm.combo} options={comboOptions} onChange={(event) => updatePath(["farm", "combo"], event.target.value)} />
            <div className="rounded-lg border border-white/10 bg-black/20 px-4 py-3 text-sm text-slate-400">
              {comboSequence.length ? <><span className="font-semibold text-white">{comboSequence.length}</span> bước thả quân đã cấu hình.</> : <span className="text-amber-200">Combo chưa có sequence thả quân.</span>}
            </div>
          </div>
        </Card>

        <div className="grid gap-5 xl:grid-cols-[minmax(0,1.25fr)_minmax(360px,0.75fr)]">
          <div className="space-y-5">
            <Card title="Điều kiện tài nguyên" subtitle="Giá trị 0 sẽ bỏ qua điều kiện tương ứng.">
              <div className="grid gap-4 md:grid-cols-3">
                <TextInput type="number" min={0} label="Vàng tối thiểu" value={String(farm.gold_min)} onChange={(event) => updatePath(["farm", "gold_min"], numberValue(event.target.value))} />
                <TextInput type="number" min={0} label="Dầu tối thiểu" value={String(farm.elixir_min)} onChange={(event) => updatePath(["farm", "elixir_min"], numberValue(event.target.value))} />
                <TextInput type="number" min={0} label="Tổng vàng + dầu" value={String(farm.total_min)} onChange={(event) => updatePath(["farm", "total_min"], numberValue(event.target.value))} />
              </div>
              <div className="mt-5">
                <p className="mb-2 text-sm font-medium text-slate-300">Cách xét ngưỡng</p>
                <SegmentedControl value={farm.threshold_mode ?? "any"} columns={3} options={[
                  { value: "any", label: "Một điều kiện" },
                  { value: "all", label: "Tất cả điều kiện" },
                  { value: "total", label: "Chỉ xét tổng" },
                ]} onChange={(value) => updatePath(["farm", "threshold_mode"], value)} />
                <p className="mt-2 text-xs text-slate-500">Một điều kiện: chỉ cần một ngưỡng đạt. Tất cả: mọi ngưỡng khác 0 đều phải đạt.</p>
              </div>
            </Card>

            <Card title="Góc đánh" subtitle="Ngẫu nhiên sẽ chọn một trong bốn góc mỗi trận.">
              <SegmentedControl value={farm.attack_view ?? "random"} columns={5} options={viewOptions} onChange={(value) => updatePath(["farm", "attack_view"], value)} />
            </Card>

            <Card title="Số lượng quân">
              <div className="grid gap-3 md:grid-cols-2">
                <Toggle label="Nhận diện vị trí slot" hint="Dùng template để tìm đúng vị trí quân và thuốc trên thanh triển khai." checked={Boolean(config.slot_detection?.enabled)} onChange={(value) => updatePath(["slot_detection", "enabled"], value)} />
                <Toggle label="Dùng số lượng nhập tay" hint="Số lượng lấy từ trang Tổng quan; vị trí slot vẫn được nhận diện." checked={Boolean(config.manual_army?.enabled)} onChange={(value) => updatePath(["manual_army", "enabled"], value)} />
              </div>
              {!config.slot_detection?.enabled ? <Feedback tone="warning" className="mt-4">Tắt nhận diện slot chỉ phù hợp khi mọi loại quân đã có tọa độ fallback.</Feedback> : null}
            </Card>
          </div>

          <div className="space-y-5">
            <Card title="Tìm trận">
              <TextInput type="number" min={0} label="Số lần Next tối đa" hint="Bot dừng tìm khi đã bỏ qua đủ số nhà này." value={String(farm.max_next)} onChange={(event) => updatePath(["farm", "max_next"], numberValue(event.target.value))} />
            </Card>

            <Card title="Tùy chọn farm">
              <div className="space-y-3">
                <Toggle label="Tự đổi combo khi bắt đầu" checked={Boolean(game.change_combo_on_start)} onChange={(value) => updatePath(["game", "change_combo_on_start"], value)} />
                <Toggle label="Thống kê tài nguyên" checked={Boolean(game.resource_stats)} onChange={(value) => updatePath(["game", "resource_stats"], value)} />
              </div>
            </Card>

            <details className="rounded-lg border border-white/10 bg-ink-850/90 p-5">
              <summary className="cursor-pointer text-sm font-semibold text-white">Tự phục hồi</summary>
              <div className="mt-5 space-y-3 border-t border-white/10 pt-5">
                <Toggle label="Không thấy Attack thì mở lại game" checked={Boolean(game.restart_if_attack_missing)} onChange={(value) => updatePath(["game", "restart_if_attack_missing"], value)} />
                <Toggle label="Bật tự động dừng" checked={Boolean(game.auto_stop)} onChange={(value) => updatePath(["game", "auto_stop"], value)} />
                <Toggle label="Bỏ qua khởi động lại game" checked={Boolean(game.skip_restart_game)} onChange={(value) => updatePath(["game", "skip_restart_game"], value)} />
                <div className="grid gap-4 pt-2 sm:grid-cols-2">
                  <TextInput type="number" min={0} suffix="giây" label="Tự dừng sau" value={String(game.auto_restart_after_seconds)} onChange={(event) => updatePath(["game", "auto_restart_after_seconds"], numberValue(event.target.value))} />
                  <TextInput type="number" min={0} suffix="giây" label="Restart khi OCR loot lỗi" value={String(farm.ocr_fail_restart_seconds)} onChange={(event) => updatePath(["farm", "ocr_fail_restart_seconds"], numberValue(event.target.value))} />
                  <TextInput type="number" min={1} suffix="lần" label="Restart OCR loot tối đa" value={String(farm.max_ocr_restarts ?? 3)} onChange={(event) => updatePath(["farm", "max_ocr_restarts"], numberValue(event.target.value))} />
                  <TextInput type="number" min={1} label="Lỗi cycle tối đa" value={String(game.max_consecutive_cycle_errors)} onChange={(event) => updatePath(["game", "max_consecutive_cycle_errors"], numberValue(event.target.value))} />
                  <TextInput type="number" min={1} label="Home restart fail tối đa" value={String(game.max_home_restart_failures ?? 3)} onChange={(event) => updatePath(["game", "max_home_restart_failures"], numberValue(event.target.value))} />
                  <TextInput type="number" min={0} suffix="giây" label="Chờ restart game" value={String(game.restart_wait_seconds)} onChange={(event) => updatePath(["game", "restart_wait_seconds"], numberValue(event.target.value))} />
                  <TextInput type="number" min={1} suffix="giây" label="Chờ màn hình kết quả" value={String(game.result_wait_seconds ?? 15)} onChange={(event) => updatePath(["game", "result_wait_seconds"], numberValue(event.target.value))} />
                </div>
              </div>
            </details>
          </div>
        </div>
      </div>
    </div>
  );
}
