import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { Feedback, LoadingState } from "../components/Feedback";
import { TextInput, Toggle } from "../components/FormControls";
import { PageHeader } from "../components/PageHeader";
import { numberValue, useConfigEditor } from "../hooks/useConfigEditor";

export function SurrenderPage() {
  const { config, loading, saving, error, savedMessage, updatePath, save } = useConfigEditor();
  if (loading) return <LoadingState label="Đang tải cấu hình đầu hàng..." />;
  if (!config) return <Feedback tone="error">{error || "Không tải được cấu hình."}</Feedback>;
  const surrender = config.surrender;
  const locked = Boolean(surrender.never_surrender);

  return (
    <div>
      <PageHeader eyebrow="Trận đấu" title="Điều kiện kết thúc trận" subtitle="Bot kết thúc khi một trong các điều kiện đang bật được đáp ứng." action={<Button variant="success" loading={saving} onClick={save}>Lưu cấu hình</Button>} />
      {error ? <Feedback tone="error" className="mb-5">{error}</Feedback> : savedMessage ? <Feedback tone="success" className="mb-5">{savedMessage}</Feedback> : null}

      <div className="grid gap-5 xl:grid-cols-[360px_minmax(0,1fr)]">
        <Card title="Chế độ kết thúc trận">
          <div className="space-y-3">
            <Toggle label="Đầu hàng theo thời gian" checked={Boolean(surrender.by_time)} disabled={locked} onChange={(value) => updatePath(["surrender", "by_time"], value)} />
            <Toggle label="Đầu hàng theo % phá hủy" checked={Boolean(surrender.by_destruction)} disabled={locked} onChange={(value) => updatePath(["surrender", "by_destruction"], value)} />
            <Toggle label="Đầu hàng khi tài nguyên còn thấp" checked={Boolean(surrender.when_low_loot)} disabled={locked} onChange={(value) => updatePath(["surrender", "when_low_loot"], value)} />
            <Toggle label="Không đầu hàng theo ngưỡng" hint="Ba điều kiện phía trên bị tắt; bảo vệ damage đứng im và OCR lỗi vẫn hoạt động." checked={locked} onChange={(value) => updatePath(["surrender", "never_surrender"], value)} />
          </div>
        </Card>

        <div className="space-y-5">
          {(surrender.by_time && !locked) ? (
            <Card title="Theo thời gian">
              <div className="grid gap-4 sm:grid-cols-3">
                <TextInput type="number" min={0} suffix="giây" label="Từ" value={String(surrender.time_min_seconds)} onChange={(event) => updatePath(["surrender", "time_min_seconds"], numberValue(event.target.value))} />
                <TextInput type="number" min={0} suffix="giây" label="Đến" value={String(surrender.time_max_seconds)} onChange={(event) => updatePath(["surrender", "time_max_seconds"], numberValue(event.target.value))} />
                <TextInput type="number" min={1} max={175} suffix="giây" label="Trận tối đa" value={String(surrender.max_battle_seconds)} onChange={(event) => updatePath(["surrender", "max_battle_seconds"], numberValue(event.target.value))} />
              </div>
            </Card>
          ) : null}

          {(surrender.by_destruction && !locked) ? (
            <Card title="Theo phần trăm phá hủy">
              <div className="grid gap-4 sm:grid-cols-2">
                <TextInput type="number" min={0} max={100} suffix="%" label="Từ" value={String(surrender.destruction_min_percent)} onChange={(event) => updatePath(["surrender", "destruction_min_percent"], numberValue(event.target.value))} />
                <TextInput type="number" min={0} max={100} suffix="%" label="Đến" value={String(surrender.destruction_max_percent)} onChange={(event) => updatePath(["surrender", "destruction_max_percent"], numberValue(event.target.value))} />
              </div>
            </Card>
          ) : null}

          {(surrender.when_low_loot && !locked) ? (
            <Card title="Theo tài nguyên còn lại">
              <TextInput type="number" min={0} label="Tổng vàng + dầu nhỏ hơn" hint="Bot kết thúc khi tổng tài nguyên còn lại trên base thấp hơn ngưỡng này." value={String(surrender.total_remaining_less_than)} onChange={(event) => updatePath(["surrender", "total_remaining_less_than"], numberValue(event.target.value))} />
            </Card>
          ) : null}

          {locked ? <Feedback tone="info">Bot bỏ qua ngưỡng đầu hàng nhưng vẫn kết thúc khi damage đứng im hoặc restart khi OCR damage lỗi.</Feedback> : null}

          <Card title="Bảo vệ OCR damage" subtitle="Các ngưỡng an toàn khi số phá hủy bị mất hoặc đứng yên.">
            <div className="grid gap-4 md:grid-cols-2">
              <TextInput type="number" min={0} suffix="giây" label="Damage ? quá lâu" hint="Restart game khi OCR không đọc được liên tục." value={String(surrender.damage_unknown_restart_seconds ?? 20)} onChange={(event) => updatePath(["surrender", "damage_unknown_restart_seconds"], numberValue(event.target.value))} />
              <TextInput type="number" min={1} suffix="lần" label="Restart OCR damage tối đa" hint="Dừng bot khi OCR damage lỗi liên tiếp quá số lần này." value={String(surrender.max_damage_ocr_restarts ?? 3)} onChange={(event) => updatePath(["surrender", "max_damage_ocr_restarts"], numberValue(event.target.value))} />
              <TextInput type="number" min={0} suffix="giây" label="Damage đứng im" hint="Kết thúc trận khi damage không tăng." value={String(surrender.damage_stall_seconds ?? 20)} onChange={(event) => updatePath(["surrender", "damage_stall_seconds"], numberValue(event.target.value))} />
              <TextInput type="number" min={0} max={100} suffix="%" label="Xác nhận bước nhảy" hint="Giữ lại giá trị OCR tăng bất thường để đọc xác nhận." value={String(surrender.damage_jump_confirm_percent)} onChange={(event) => updatePath(["surrender", "damage_jump_confirm_percent"], numberValue(event.target.value))} />
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
