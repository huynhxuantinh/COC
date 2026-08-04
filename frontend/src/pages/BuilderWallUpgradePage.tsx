import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { Feedback, LoadingState } from "../components/Feedback";
import { TextInput, Toggle } from "../components/FormControls";
import { PageHeader } from "../components/PageHeader";
import { numberValue, useConfigEditor } from "../hooks/useConfigEditor";

export function BuilderWallUpgradePage() {
  const { config, loading, saving, error, savedMessage, updatePath, save } = useConfigEditor();
  if (loading) return <LoadingState label="Đang tải cấu hình nâng tường Làng đêm..." />;
  if (!config) return <Feedback tone="error">{error || "Không tải được cấu hình."}</Feedback>;

  const path = ["builder_base", "wall_upgrade"];
  const wall = config.builder_base?.wall_upgrade ?? {};
  const enabled = Boolean(wall.enabled);
  const update = (key: string, value: unknown) => updatePath([...path, key], value);

  return (
    <div>
      <PageHeader
        eyebrow="Làng đêm"
        title="Nâng tường"
        subtitle="Tự chọn Vàng hoặc Dầu theo ngân sách còn lại lớn hơn."
        action={<Button variant="success" loading={saving} onClick={save}>Lưu cấu hình</Button>}
      />
      {error ? <Feedback tone="error" className="mb-5">{error}</Feedback> : savedMessage ? <Feedback tone="success" className="mb-5">{savedMessage}</Feedback> : null}

      <Card title="Trạng thái" action={wall.dry_run && enabled ? <span className="rounded-full bg-amber-400/15 px-3 py-1 text-xs font-bold text-amber-200">Mô phỏng</span> : null}>
        <div className="grid gap-3 md:grid-cols-2">
          <Toggle label="Bật tự động nâng tường" checked={enabled} onChange={(value) => update("enabled", value)} />
          <Toggle label="Mô phỏng" checked={Boolean(wall.dry_run)} disabled={!enabled} onChange={(value) => update("dry_run", value)} />
        </div>
      </Card>

      <fieldset disabled={!enabled} className="mt-5 grid min-w-0 gap-5 disabled:opacity-45 xl:grid-cols-2">
        <div className="min-w-0 space-y-5">
          <Card title="Điều kiện kích hoạt">
            <div className="space-y-4">
              <Toggle label="Nâng sau mỗi N trận" checked={Boolean(wall.run_after_attacks_enabled ?? true)} onChange={(value) => update("run_after_attacks_enabled", value)} />
              <div className="grid gap-4 sm:grid-cols-2">
                {wall.run_after_attacks_enabled ? <TextInput type="number" min={1} suffix="trận" label="Số trận" value={String(wall.run_every_n_attacks ?? 10)} onChange={(event) => update("run_every_n_attacks", numberValue(event.target.value))} /> : null}
                <TextInput type="number" min={1} max={100} suffix="%" label="Vàng hoặc Dầu đạt" value={String(wall.trigger_percent ?? 90)} onChange={(event) => update("trigger_percent", numberValue(event.target.value))} />
              </div>
            </div>
          </Card>

          <Card title="Tài nguyên">
            <div className="grid gap-4 sm:grid-cols-2">
              <TextInput type="number" min={1} label="Kho Vàng tối đa" value={String(wall.gold_capacity ?? 6000000)} onChange={(event) => update("gold_capacity", numberValue(event.target.value))} />
              <TextInput type="number" min={1} label="Kho Dầu tối đa" value={String(wall.elixir_capacity ?? 6000000)} onChange={(event) => update("elixir_capacity", numberValue(event.target.value))} />
              <TextInput type="number" min={0} label="Giữ lại Vàng" value={String(wall.reserve_gold ?? 200000)} onChange={(event) => update("reserve_gold", numberValue(event.target.value))} />
              <TextInput type="number" min={0} label="Giữ lại Dầu" value={String(wall.reserve_elixir ?? 200000)} onChange={(event) => update("reserve_elixir", numberValue(event.target.value))} />
            </div>
          </Card>
        </div>

        <div className="min-w-0 space-y-5">
          <Card title="Thao tác">
            <div className="grid gap-4 sm:grid-cols-2">
              <TextInput type="number" min={1} suffix="lần" label="Bấm +1" value={String(wall.add1_rounds ?? 1)} onChange={(event) => update("add1_rounds", numberValue(event.target.value))} />
              <TextInput type="number" min={0} suffix="lần" label="Cuộn tìm Wall tối đa" value={String(wall.max_wall_search_scrolls ?? 9)} onChange={(event) => update("max_wall_search_scrolls", numberValue(event.target.value))} />
            </div>
          </Card>

          <Card title="Khi thất bại">
            <TextInput type="number" min={1} suffix="trận" label="Thử lại sau" value={String(wall.retry_backoff_attacks ?? 10)} onChange={(event) => update("retry_backoff_attacks", numberValue(event.target.value))} />
          </Card>

          <details className="rounded-lg border border-white/10 bg-ink-850/90 p-5">
            <summary className="cursor-pointer text-sm font-semibold text-white">Đọc OCR</summary>
            <div className="mt-5 grid gap-4 border-t border-white/10 pt-5 sm:grid-cols-2">
              <TextInput type="number" min={1} suffix="lần" label="Đọc tài nguyên" value={String(wall.resource_read_attempts ?? 3)} onChange={(event) => update("resource_read_attempts", numberValue(event.target.value))} />
              <TextInput type="number" min={1} suffix="lần" label="Đọc giá" value={String(wall.cost_read_attempts ?? 3)} onChange={(event) => update("cost_read_attempts", numberValue(event.target.value))} />
              <TextInput type="number" min={0} step={0.05} suffix="giây" label="Delay mỗi lần đọc" value={String(wall.read_attempt_delay ?? 0.45)} onChange={(event) => update("read_attempt_delay", Number(event.target.value || 0))} />
            </div>
          </details>
        </div>
      </fieldset>
    </div>
  );
}
