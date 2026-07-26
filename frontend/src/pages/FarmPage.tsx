import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { PageHeader } from "../components/PageHeader";
import { SelectInput, TextInput, Toggle } from "../components/FormControls";
import { numberValue, useConfigEditor } from "../hooks/useConfigEditor";

export function FarmPage() {
  const { config, options, loading, saving, error, savedMessage, updatePath, save } = useConfigEditor();

  if (loading) {
    return <Card title="Farm">Đang tải cấu hình...</Card>;
  }
  if (!config) {
    return <Card title="Farm">{error || "Không tải được cấu hình."}</Card>;
  }

  const game = config.game;
  const farm = config.farm;
  const comboOptions = (options?.combos ?? [farm.combo]).map((name) => ({ label: name, value: name }));

  return (
    <div>
      <PageHeader
        eyebrow="Farm"
        title="Cấu hình tìm nhà"
        subtitle="Chọn combo, góc đánh, ngưỡng vàng/dầu và các cơ chế tự phục hồi khi bot bị kẹt."
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

      <div className="grid gap-5 xl:grid-cols-[1fr_360px]">
        <div className="space-y-5">
          <Card title="Combo và cách chọn base">
            <div className="grid gap-4 md:grid-cols-2">
              <SelectInput label="Combo lính" value={farm.combo} options={comboOptions} onChange={(event) => updatePath(["farm", "combo"], event.target.value)} />
              <SelectInput label="Góc đánh" value={farm.attack_view ?? "random"} options={options?.attack_views ?? []} onChange={(event) => updatePath(["farm", "attack_view"], event.target.value)} />
              <SelectInput
                label="Kiểu xét ngưỡng"
                value={farm.threshold_mode ?? "any"}
                options={[
                  { label: "Một điều kiện đạt là đánh", value: "any" },
                  { label: "Tất cả điều kiện phải đạt", value: "all" },
                  { label: "Chỉ xét tổng vàng + dầu", value: "total" },
                ]}
                onChange={(event) => updatePath(["farm", "threshold_mode"], event.target.value)}
              />
              <TextInput label="Số lần Next tối đa" value={String(farm.max_next)} onChange={(event) => updatePath(["farm", "max_next"], numberValue(event.target.value))} />
            </div>
          </Card>

          <Card title="Ngưỡng tài nguyên">
            <div className="grid gap-4 md:grid-cols-3">
              <TextInput label="Vàng tối thiểu" value={String(farm.gold_min)} onChange={(event) => updatePath(["farm", "gold_min"], numberValue(event.target.value))} />
              <TextInput label="Dầu tối thiểu" value={String(farm.elixir_min)} onChange={(event) => updatePath(["farm", "elixir_min"], numberValue(event.target.value))} />
              <TextInput label="Tổng vàng + dầu tối thiểu" value={String(farm.total_min)} onChange={(event) => updatePath(["farm", "total_min"], numberValue(event.target.value))} />
            </div>
          </Card>

          <Card title="Tùy chọn farm">
            <div className="grid gap-3 md:grid-cols-3">
              <Toggle label="Bật chờ lính khi farm" checked={Boolean(game.donate_when_farming)} onChange={(value) => updatePath(["game", "donate_when_farming"], value)} />
              <Toggle label="Tự đổi combo khi bắt đầu" checked={Boolean(game.change_combo_on_start)} onChange={(value) => updatePath(["game", "change_combo_on_start"], value)} />
              <Toggle label="Thống kê tài nguyên" checked={Boolean(game.resource_stats)} onChange={(value) => updatePath(["game", "resource_stats"], value)} />
            </div>
          </Card>
        </div>

        <div className="space-y-5">
          <Card title="Tự phục hồi">
            <div className="space-y-3">
              <Toggle label="Không thấy Attack thì mở lại game" checked={Boolean(game.restart_if_attack_missing)} onChange={(value) => updatePath(["game", "restart_if_attack_missing"], value)} />
              <Toggle label="Bật tự động dừng" checked={Boolean(game.auto_stop)} onChange={(value) => updatePath(["game", "auto_stop"], value)} />
              <Toggle label="Bỏ qua khởi động lại game" checked={Boolean(game.skip_restart_game)} onChange={(value) => updatePath(["game", "skip_restart_game"], value)} />
            </div>
            <div className="mt-4 grid gap-4">
              <TextInput label="Tự động dừng sau (giây)" value={String(game.auto_restart_after_seconds)} onChange={(event) => updatePath(["game", "auto_restart_after_seconds"], numberValue(event.target.value))} />
              <TextInput label="Restart khi OCR fail quá lâu (giây)" value={String(farm.ocr_fail_restart_seconds)} onChange={(event) => updatePath(["farm", "ocr_fail_restart_seconds"], numberValue(event.target.value))} />
              <TextInput label="Lỗi cycle liên tiếp tối đa" value={String(game.max_consecutive_cycle_errors)} onChange={(event) => updatePath(["game", "max_consecutive_cycle_errors"], numberValue(event.target.value))} />
              <TextInput label="Home restart fail tối đa" value={String(game.max_home_restart_failures ?? 3)} onChange={(event) => updatePath(["game", "max_home_restart_failures"], numberValue(event.target.value))} />
              <TextInput label="Chờ restart game (giây)" value={String(game.restart_wait_seconds)} onChange={(event) => updatePath(["game", "restart_wait_seconds"], numberValue(event.target.value))} />
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
