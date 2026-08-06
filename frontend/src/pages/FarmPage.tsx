import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { Feedback, LoadingState } from "../components/Feedback";
import { TextInput, Toggle } from "../components/FormControls";
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
  const { config, loading, saving, error, savedMessage, updatePath, save } = useConfigEditor();
  if (loading) return <LoadingState label="Đang tải cấu hình Farm..." />;
  if (!config) return <Feedback tone="error">{error || "Không tải được cấu hình."}</Feedback>;

  const game = config.game;
  const farm = config.farm;
  const thresholdMode = farm.threshold_mode ?? "any";
  const thresholds = [Number(farm.gold_min ?? 0), Number(farm.elixir_min ?? 0), Number(farm.total_min ?? 0)];
  const invalidThresholds = thresholdMode === "total" ? thresholds[2] <= 0 : !thresholds.some((value) => value > 0);
  return (
    <div>
      <PageHeader eyebrow="Farm" title="Cấu hình tìm nhà" subtitle="Điều kiện tài nguyên, góc đánh và giới hạn tìm trận." action={<Button variant="success" loading={saving} disabled={invalidThresholds} onClick={save}>Lưu cấu hình</Button>} />
      {error ? <Feedback tone="error" className="mb-5">{error}</Feedback> : savedMessage ? <Feedback tone="success" className="mb-5">{savedMessage}</Feedback> : null}
      {invalidThresholds ? <Feedback tone="warning" className="mb-5">{thresholdMode === "total" ? "Chế độ Chỉ xét tổng cần Tổng vàng + dầu lớn hơn 0." : "Hãy bật ít nhất một ngưỡng tài nguyên lớn hơn 0."}</Feedback> : null}

      <div className="space-y-5">
        <div className="grid gap-5 xl:grid-cols-[minmax(0,1.15fr)_minmax(420px,0.85fr)]">
          <div>
            <Card title="Điều kiện tài nguyên" subtitle="Giá trị 0 sẽ bỏ qua điều kiện tương ứng.">
              <div className="grid gap-4 md:grid-cols-3">
                <TextInput type="number" min={0} label="Vàng tối thiểu" value={String(farm.gold_min)} onChange={(event) => updatePath(["farm", "gold_min"], numberValue(event.target.value))} />
                <TextInput type="number" min={0} label="Dầu tối thiểu" value={String(farm.elixir_min)} onChange={(event) => updatePath(["farm", "elixir_min"], numberValue(event.target.value))} />
                <TextInput type="number" min={0} label="Tổng vàng + dầu" value={String(farm.total_min)} onChange={(event) => updatePath(["farm", "total_min"], numberValue(event.target.value))} />
              </div>
              <div className="mt-5">
                <p className="mb-2 text-sm font-medium text-slate-300">Cách xét ngưỡng</p>
                <SegmentedControl value={thresholdMode} columns={3} options={[
                  { value: "any", label: "Một điều kiện" },
                  { value: "all", label: "Tất cả điều kiện" },
                  { value: "total", label: "Chỉ xét tổng" },
                ]} onChange={(value) => updatePath(["farm", "threshold_mode"], value)} />
                <p className="mt-2 text-xs text-slate-500">Một điều kiện: chỉ cần một ngưỡng đạt. Tất cả: mọi ngưỡng khác 0 đều phải đạt.</p>
              </div>
              <div className="mt-5 border-t border-white/10 pt-5">
                <Toggle label="Thống kê tài nguyên sau trận" checked={Boolean(game.resource_stats)} onChange={(value) => updatePath(["game", "resource_stats"], value)} />
              </div>
            </Card>
          </div>

          <div>
            <Card title="Tìm và triển khai">
              <div className="space-y-5">
                <TextInput type="number" min={1} label="Số lần Next tối đa" hint="Bot dừng tìm khi đã bỏ qua đủ số nhà này." value={String(farm.max_next)} onChange={(event) => updatePath(["farm", "max_next"], numberValue(event.target.value))} />
                <div className="border-t border-white/10 pt-5">
                  <p className="mb-2 text-sm font-medium text-slate-300">Góc đánh</p>
                  <SegmentedControl value={farm.attack_view ?? "random"} columns={2} options={viewOptions} onChange={(value) => updatePath(["farm", "attack_view"], value)} />
                </div>
              </div>
            </Card>
          </div>
        </div>
      </div>
    </div>
  );
}
