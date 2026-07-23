import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { TextInput, Toggle } from "../components/FormControls";
import { numberValue, useConfigEditor } from "../hooks/useConfigEditor";

export function SurrenderPage() {
  const { config, loading, saving, error, savedMessage, updatePath, save } = useConfigEditor();

  if (loading) {
    return <Card title="Đầu hàng">Đang tải cấu hình...</Card>;
  }
  if (!config) {
    return <Card title="Đầu hàng">{error || "Không tải được cấu hình."}</Card>;
  }

  const surrender = config.surrender;

  return (
    <Card
      title="Luật kết thúc trận"
      subtitle="Bot vẫn đánh xong chu kỳ an toàn, rồi mới xử lý dừng/restart."
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
      <div className="grid gap-3 md:grid-cols-2">
        <Toggle label="Đầu hàng theo thời gian" checked={Boolean(surrender.by_time)} onChange={(value) => updatePath(["surrender", "by_time"], value)} />
        <Toggle label="Đầu hàng theo % phá hủy" checked={Boolean(surrender.by_destruction)} onChange={(value) => updatePath(["surrender", "by_destruction"], value)} />
        <Toggle label="Đầu hàng khi còn ít tài nguyên" checked={Boolean(surrender.when_low_loot)} onChange={(value) => updatePath(["surrender", "when_low_loot"], value)} />
        <Toggle label="Không đầu hàng (đánh hết)" checked={Boolean(surrender.never_surrender)} onChange={(value) => updatePath(["surrender", "never_surrender"], value)} />
      </div>

      <div className="mt-5 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        <TextInput label="Thời gian tối thiểu (giây)" value={String(surrender.time_min_seconds)} onChange={(event) => updatePath(["surrender", "time_min_seconds"], numberValue(event.target.value))} />
        <TextInput label="Thời gian tối đa (giây)" value={String(surrender.time_max_seconds)} onChange={(event) => updatePath(["surrender", "time_max_seconds"], numberValue(event.target.value))} />
        <TextInput label="Thời lượng trận tối đa (giây)" value={String(surrender.max_battle_seconds)} onChange={(event) => updatePath(["surrender", "max_battle_seconds"], numberValue(event.target.value))} />
        <TextInput label="% phá hủy tối thiểu" value={String(surrender.destruction_min_percent)} onChange={(event) => updatePath(["surrender", "destruction_min_percent"], numberValue(event.target.value))} />
        <TextInput label="% phá hủy tối đa" value={String(surrender.destruction_max_percent)} onChange={(event) => updatePath(["surrender", "destruction_max_percent"], numberValue(event.target.value))} />
        <TextInput label="Xác nhận nhảy damage bất thường (%)" value={String(surrender.damage_jump_confirm_percent)} onChange={(event) => updatePath(["surrender", "damage_jump_confirm_percent"], numberValue(event.target.value))} />
        <TextInput label="Tổng vàng + dầu còn lại <" value={String(surrender.total_remaining_less_than)} onChange={(event) => updatePath(["surrender", "total_remaining_less_than"], numberValue(event.target.value))} />
      </div>
    </Card>
  );
}
