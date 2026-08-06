import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { Feedback, LoadingState } from "../components/Feedback";
import { SelectInput, TextInput, Toggle } from "../components/FormControls";
import { PageHeader } from "../components/PageHeader";
import { numberValue, useConfigEditor } from "../hooks/useConfigEditor";

export function WallUpgradePage() {
  const { config, loading, saving, error, savedMessage, updatePath, save } = useConfigEditor();
  if (loading) return <LoadingState label="Đang tải cấu hình nâng tường..." />;
  if (!config) return <Feedback tone="error">{error || "Không tải được cấu hình."}</Feedback>;

  const wall = config.wall_upgrade ?? {};
  const enabled = Boolean(wall.enabled);

  return (
    <div>
      <PageHeader eyebrow="Tự động hóa" title="Nâng tường" subtitle="Điều kiện tài nguyên, chu kỳ nâng và cơ chế cooldown." action={<Button variant="success" loading={saving} onClick={save}>Lưu cấu hình</Button>} />
      {error ? <Feedback tone="error" className="mb-5">{error}</Feedback> : savedMessage ? <Feedback tone="success" className="mb-5">{savedMessage}</Feedback> : null}

      <Card title="Trạng thái" action={wall.dry_run && enabled ? <span className="rounded-full bg-amber-400/15 px-3 py-1 text-xs font-bold text-amber-200">Mô phỏng</span> : null}>
        <div className="grid gap-3 md:grid-cols-2">
          <Toggle label="Bật tự động nâng tường" checked={enabled} onChange={(value) => updatePath(["wall_upgrade", "enabled"], value)} />
          <Toggle label="Mô phỏng" hint="Chỉ kiểm tra và ghi log, không xác nhận nâng thật." checked={Boolean(wall.dry_run)} disabled={!enabled} onChange={(value) => updatePath(["wall_upgrade", "dry_run"], value)} />
        </div>
      </Card>

      <fieldset disabled={!enabled} className="mt-5 grid min-w-0 gap-5 disabled:opacity-45 xl:grid-cols-2">
        <div className="min-w-0 space-y-5">
          <Card title="Điều kiện kích hoạt">
            <div className="space-y-4">
              <Toggle label="Nâng sau số trận" checked={Boolean(wall.run_after_attacks_enabled ?? true)} onChange={(value) => updatePath(["wall_upgrade", "run_after_attacks_enabled"], value)} />
              <div className="grid gap-4 sm:grid-cols-2">
                {wall.run_after_attacks_enabled ? <TextInput type="number" min={1} suffix="trận" label="Chu kỳ nâng" value={String(wall.run_every_n_attacks ?? 20)} onChange={(event) => updatePath(["wall_upgrade", "run_every_n_attacks"], numberValue(event.target.value))} /> : null}
                <TextInput type="number" min={1} max={100} suffix="%" label="Ngưỡng tài nguyên" value={String(wall.trigger_percent ?? 95)} onChange={(event) => updatePath(["wall_upgrade", "trigger_percent"], numberValue(event.target.value))} />
              </div>
            </div>
          </Card>

          <Card title="Tài nguyên">
            <div className="grid gap-4 sm:grid-cols-2">
              <SelectInput label="Nguồn thanh toán" value={wall.pay_with ?? "auto"} onChange={(event) => updatePath(["wall_upgrade", "pay_with"], event.target.value)} options={[{ label: "Tự động", value: "auto" }, { label: "Vàng", value: "gold" }, { label: "Dầu", value: "elixir" }]} />
              <div className="hidden sm:block" />
              <TextInput type="number" min={1} label="Kho vàng tối đa" value={String(wall.gold_capacity ?? 6000000)} onChange={(event) => updatePath(["wall_upgrade", "gold_capacity"], numberValue(event.target.value))} />
              <TextInput type="number" min={1} label="Kho dầu tối đa" value={String(wall.elixir_capacity ?? 6000000)} onChange={(event) => updatePath(["wall_upgrade", "elixir_capacity"], numberValue(event.target.value))} />
              <TextInput type="number" min={0} label="Giữ lại vàng" value={String(wall.reserve_gold ?? 200000)} onChange={(event) => updatePath(["wall_upgrade", "reserve_gold"], numberValue(event.target.value))} />
              <TextInput type="number" min={0} label="Giữ lại dầu" value={String(wall.reserve_elixir ?? 200000)} onChange={(event) => updatePath(["wall_upgrade", "reserve_elixir"], numberValue(event.target.value))} />
            </div>
          </Card>
        </div>

        <div className="min-w-0 space-y-5">
          <Card title="Số lần thao tác">
            <div className="space-y-4">
              <Toggle label="Dùng nút +10" checked={Boolean(wall.use_add10)} onChange={(value) => updatePath(["wall_upgrade", "use_add10"], value)} />
              {wall.use_add10 ? (
                <TextInput type="number" min={1} suffix="lần" label="Tối đa số lần bấm +10" value={String(wall.max_add_rounds ?? 10)} onChange={(event) => updatePath(["wall_upgrade", "max_add_rounds"], numberValue(event.target.value))} />
              ) : (
                <TextInput type="number" min={1} suffix="lần" label="Số lần bấm +1" value={String(wall.add1_rounds ?? 1)} onChange={(event) => updatePath(["wall_upgrade", "add1_rounds"], numberValue(event.target.value))} />
              )}
            </div>
          </Card>

          <Card title="Cooldown khi thất bại">
            <div className="grid gap-4 sm:grid-cols-2">
              <TextInput type="number" min={1} suffix="trận" label="Lỗi tạm thời" value={String(wall.temporary_retry_backoff_attacks ?? 2)} onChange={(event) => updatePath(["wall_upgrade", "temporary_retry_backoff_attacks"], numberValue(event.target.value))} />
              <TextInput type="number" min={1} suffix="trận" label="Lỗi thực" value={String(wall.retry_backoff_attacks ?? 10)} onChange={(event) => updatePath(["wall_upgrade", "retry_backoff_attacks"], numberValue(event.target.value))} />
              {wall.dry_run ? <TextInput type="number" min={1} suffix="trận" label="Mô phỏng lại sau" value={String(wall.dry_run_retry_attacks ?? 10)} onChange={(event) => updatePath(["wall_upgrade", "dry_run_retry_attacks"], numberValue(event.target.value))} /> : null}
            </div>
          </Card>

          <details className="rounded-lg border border-white/10 bg-ink-850/90 p-5">
            <summary className="cursor-pointer text-sm font-semibold text-white">Nâng cao</summary>
            <div className="mt-5 grid gap-4 border-t border-white/10 pt-5 sm:grid-cols-2">
              <TextInput type="number" min={1} suffix="lần" label="Tối đa cuộn tìm Wall" value={String(wall.max_wall_search_scrolls ?? 9)} onChange={(event) => updatePath(["wall_upgrade", "max_wall_search_scrolls"], numberValue(event.target.value))} />
              <TextInput type="number" min={1} suffix="lần" label="Số lần đọc tài nguyên" value={String(wall.resource_read_attempts ?? 3)} onChange={(event) => updatePath(["wall_upgrade", "resource_read_attempts"], numberValue(event.target.value))} />
              <TextInput type="number" min={0} step={0.05} suffix="giây" label="Delay mỗi lần đọc" value={String(wall.read_attempt_delay ?? 0.45)} onChange={(event) => updatePath(["wall_upgrade", "read_attempt_delay"], Number(event.target.value || 0))} />
            </div>
          </details>
        </div>
      </fieldset>
    </div>
  );
}
