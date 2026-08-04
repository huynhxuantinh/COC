import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { Feedback, LoadingState } from "../components/Feedback";
import { TextInput, Toggle } from "../components/FormControls";
import { PageHeader } from "../components/PageHeader";
import { useConfigEditor } from "../hooks/useConfigEditor";

function decimal(value: string): number {
  return Number(value || 0);
}

export function BuilderStrategyPage() {
  const { config, loading, saving, error, savedMessage, updatePath, save } = useConfigEditor();
  if (loading) return <LoadingState label="Đang tải chiến thuật Làng đêm..." />;
  if (!config) return <Feedback tone="error">{error || "Không tải được cấu hình."}</Feedback>;

  const deploy = config.builder_base?.deploy ?? {};
  const timing = config.builder_base?.timing ?? {};
  const elixirCart = config.builder_base?.elixir_cart ?? {};

  return (
    <div>
      <PageHeader
        eyebrow="Làng đêm"
        title="Chiến thuật"
        subtitle="Thiết lập nhịp thả quân và kích hoạt kỹ năng cho hai giai đoạn."
        action={<Button variant="success" loading={saving} onClick={save}>Lưu cấu hình</Button>}
      />
      {error ? <Feedback tone="error" className="mb-5">{error}</Feedback> : savedMessage ? <Feedback tone="success" className="mb-5">{savedMessage}</Feedback> : null}

      <div className="grid gap-5 xl:grid-cols-2">
        <Card title="Thả quân">
          <div className="grid gap-4 sm:grid-cols-2">
            <TextInput type="number" min={0} step={1} suffix="lần" label="Zoom nhỏ Làng 1" value={String(deploy.stage1_zoom_out_count ?? 3)} onChange={(event) => updatePath(["builder_base", "deploy", "stage1_zoom_out_count"], Number(event.target.value || 0))} />
            <TextInput type="number" min={0} step={1} suffix="lần" label="Zoom nhỏ Làng 2" value={String(deploy.stage2_zoom_out_count ?? 3)} onChange={(event) => updatePath(["builder_base", "deploy", "stage2_zoom_out_count"], Number(event.target.value || 0))} />
            <TextInput type="number" min={0} step={0.05} suffix="giây" label="Khoảng cách giữa các ô" value={String(deploy.troop_delay_seconds ?? 0.5)} onChange={(event) => updatePath(["builder_base", "deploy", "troop_delay_seconds"], decimal(event.target.value))} />
            <TextInput type="number" min={1} suffix="điểm" label="Số điểm ngẫu nhiên" value={String(deploy.random_points ?? 64)} onChange={(event) => updatePath(["builder_base", "deploy", "random_points"], Number(event.target.value || 1))} />
            <TextInput type="number" min={0} suffix="px" label="Khoảng cách điểm từ" value={String(deploy.point_spacing_min_px ?? 20)} onChange={(event) => updatePath(["builder_base", "deploy", "point_spacing_min_px"], Number(event.target.value || 0))} />
            <TextInput type="number" min={0} suffix="px" label="Khoảng cách điểm đến" value={String(deploy.point_spacing_max_px ?? 45)} onChange={(event) => updatePath(["builder_base", "deploy", "point_spacing_max_px"], Number(event.target.value || 0))} />
          </div>
        </Card>

        <Card title="Kỹ năng">
          <div className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <TextInput type="number" min={0} step={0.5} suffix="giây" label="Kỹ năng lính sau" value={String(deploy.troop_skill_delay_seconds ?? 3)} onChange={(event) => updatePath(["builder_base", "deploy", "troop_skill_delay_seconds"], decimal(event.target.value))} />
              <TextInput type="number" min={0} step={1} suffix="giây" label="Kỹ năng tướng lần đầu" value={String(deploy.hero_first_skill_delay_seconds ?? 28)} onChange={(event) => updatePath(["builder_base", "deploy", "hero_first_skill_delay_seconds"], decimal(event.target.value))} />
            </div>
            <Toggle label="Bấm lại kỹ năng tướng khi hồi" checked={Boolean(deploy.hero_repeat_skill)} onChange={(value) => updatePath(["builder_base", "deploy", "hero_repeat_skill"], value)} />
            {deploy.hero_repeat_skill ? (
              <div className="grid gap-4 sm:grid-cols-2">
                <TextInput type="number" min={1} step={1} suffix="giây" label="Cách tối thiểu giữa hai lần" value={String(deploy.hero_repeat_min_seconds ?? 15)} onChange={(event) => updatePath(["builder_base", "deploy", "hero_repeat_min_seconds"], decimal(event.target.value))} />
                <TextInput type="number" min={0.5} step={0.5} suffix="giây" label="Chu kỳ kiểm tra" value={String(deploy.hero_ready_poll_seconds ?? 2)} onChange={(event) => updatePath(["builder_base", "deploy", "hero_ready_poll_seconds"], decimal(event.target.value))} />
              </div>
            ) : null}
          </div>
        </Card>

        <Card title="Elixir Cart" className="xl:col-span-2">
          <div className="grid gap-4 sm:grid-cols-2">
            <Toggle label="Tự động nhận dầu" checked={Boolean(elixirCart.enabled ?? true)} onChange={(value) => updatePath(["builder_base", "elixir_cart", "enabled"], value)} />
            {elixirCart.enabled ?? true ? (
              <TextInput type="number" min={1} step={1} suffix="trận" label="Nhận dầu sau mỗi" value={String(elixirCart.collect_every_n_attacks ?? 1)} onChange={(event) => updatePath(["builder_base", "elixir_cart", "collect_every_n_attacks"], Math.max(1, Number(event.target.value || 1)))} />
            ) : null}
          </div>
        </Card>

        <Card title="Bảo vệ trận đấu" className="xl:col-span-2">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <TextInput type="number" min={0} step={1} suffix="giây" label="Damage ? quá lâu" value={String(timing.damage_unknown_restart_seconds ?? 20)} onChange={(event) => updatePath(["builder_base", "timing", "damage_unknown_restart_seconds"], decimal(event.target.value))} />
            <TextInput type="number" min={0} step={1} suffix="giây" label="Damage và hình đứng" value={String(timing.damage_stall_seconds ?? 20)} onChange={(event) => updatePath(["builder_base", "timing", "damage_stall_seconds"], decimal(event.target.value))} />
            <TextInput type="number" min={0} step={1} suffix="giây" label="Màn hình không xác định" value={String(timing.unknown_state_restart_seconds ?? 12)} onChange={(event) => updatePath(["builder_base", "timing", "unknown_state_restart_seconds"], decimal(event.target.value))} />
            <TextInput type="number" min={1} step={1} suffix="lần" label="Restart tối đa" value={String(timing.max_watchdog_restarts ?? 3)} onChange={(event) => updatePath(["builder_base", "timing", "max_watchdog_restarts"], Math.max(1, Number(event.target.value || 1)))} />
          </div>
        </Card>

        <Card title="Thời gian chờ" className="xl:col-span-2">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <TextInput type="number" min={0.1} step={0.5} suffix="giây" label="Sau nút Attack" value={String(timing.after_attack_seconds ?? 1.5)} onChange={(event) => updatePath(["builder_base", "timing", "after_attack_seconds"], decimal(event.target.value))} />
            <TextInput type="number" min={0.1} step={0.5} suffix="giây" label="Sau Find Now" value={String(timing.after_find_now_seconds ?? 6)} onChange={(event) => updatePath(["builder_base", "timing", "after_find_now_seconds"], decimal(event.target.value))} />
            <TextInput type="number" min={0.1} step={0.5} suffix="giây" label="Quét trạng thái" value={String(timing.screen_poll_seconds ?? 1)} onChange={(event) => updatePath(["builder_base", "timing", "screen_poll_seconds"], decimal(event.target.value))} />
            <TextInput type="number" min={30} step={5} suffix="giây" label="Giới hạn trận" value={String(timing.battle_timeout_seconds ?? 190)} onChange={(event) => updatePath(["builder_base", "timing", "battle_timeout_seconds"], decimal(event.target.value))} />
          </div>
        </Card>
      </div>
    </div>
  );
}
