import { Cable, CirclePause, CirclePlay, RefreshCw, Square } from "lucide-react";
import { useCallback, useMemo, useRef, useState } from "react";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { Feedback, LoadingState } from "../components/Feedback";
import { SelectInput, TextInput, Toggle } from "../components/FormControls";
import { LogPanel } from "../components/LogPanel";
import { PageHeader } from "../components/PageHeader";
import { StatGrid } from "../components/StatGrid";
import { StatusBadge } from "../components/StatusBadge";
import { numberValue, useConfigEditor } from "../hooks/useConfigEditor";
import { usePolling } from "../hooks/usePolling";
import { scanAdb, startBot, stopBot, togglePause } from "../services/botApi";
import { apiErrorMessage } from "../services/http";
import { clearLogs, getLogs } from "../services/logsApi";
import { getStats } from "../services/statsApi";
import type { BotStatus, LogEntry, StatsPayload } from "../services/types";

type Props = { status: BotStatus | null; refreshStatus: () => Promise<void> };

const slotLabels: Record<string, string> = {
  dragon: "Rồng điện",
  balloon: "Bóng",
  valkyrie: "Valkyrie",
  hero: "Tướng",
  rage: "Nộ",
  freeze: "Băng",
  poison: "Độc",
};

const viewLabels: Record<string, string> = {
  random: "Ngẫu nhiên 4 góc",
  trenbenphai: "Trên phải",
  trenbentrai: "Trên trái",
  duoibenphai: "Dưới phải",
  duoibentrai: "Dưới trái",
};

export function DashboardPage({ status, refreshStatus }: Props) {
  const [stats, setStats] = useState<StatsPayload | null>(null);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [actionError, setActionError] = useState("");
  const [pollError, setPollError] = useState("");
  const [busyAction, setBusyAction] = useState("");
  const afterRef = useRef(0);
  const { config, loading, saving, error, savedMessage, isDirty, updatePath, save } = useConfigEditor();

  const manualArmy = config?.manual_army ?? { enabled: false, counts: {} };
  const selectedCombo = config?.farm?.combo ?? "";
  const comboOptions = Object.keys(config?.combos ?? {}).map((name) => ({ label: name, value: name }));
  const deploy = selectedCombo && config?.combos?.[selectedCombo]
    ? (config.combos[selectedCombo].deploy ?? config.combos[selectedCombo])
    : config?.deploy;
  const comboSlots = useMemo(() => Array.from(new Set<string>([
    ...((deploy?.sequence ?? []).map((step: any) => String(step.slot ?? "")).filter(Boolean)),
    ...((config?.deploy?.spell_groups ?? []).filter((group: any) => group.enabled !== false).flatMap((group: any) => (group.slots ?? []).map(String))),
  ])), [config?.deploy?.spell_groups, deploy?.sequence]);

  const lastError = useMemo(() => [...logs].reverse().find((entry) => /\[(ERROR|WARN)\]/.test(entry.message))?.message ?? "", [logs]);

  const refreshStats = useCallback(async () => {
    try {
      setStats(await getStats());
      setPollError("");
    } catch (err) {
      setPollError(apiErrorMessage(err));
    }
  }, []);

  const refreshLogs = useCallback(async () => {
    try {
      const payload = await getLogs(afterRef.current);
      if (payload.items.length) setLogs((current) => [...current, ...payload.items].slice(-1000));
      afterRef.current = payload.next_after;
      setPollError("");
    } catch (err) {
      setPollError(apiErrorMessage(err));
    }
  }, []);

  usePolling(refreshStats, 2000);
  usePolling(refreshLogs, 1200);

  async function runAction(name: string, action: () => Promise<BotStatus | void>) {
    if (busyAction) return;
    setActionError("");
    setBusyAction(name);
    try {
      await action();
      await Promise.all([refreshStatus(), refreshStats(), refreshLogs()]);
    } catch (err) {
      setActionError(apiErrorMessage(err));
    } finally {
      setBusyAction("");
    }
  }

  async function handleStartBot() {
    if (isDirty && !(await save())) throw new Error("Không lưu được cấu hình. Bot chưa được khởi động.");
    return startBot();
  }

  async function handleClearLogs() {
    try {
      await clearLogs();
      afterRef.current = 0;
      setLogs([]);
    } catch (err) {
      setActionError(apiErrorMessage(err));
    }
  }

  return (
    <div>
      <PageHeader eyebrow="Vận hành" title="Tổng quan" subtitle="Kết nối LDPlayer, điều khiển bot và theo dõi phiên farm tại một nơi." />

      {(actionError || pollError || error) ? <Feedback tone="error" className="mb-5">{actionError || pollError || error}</Feedback> : null}
      {savedMessage ? <Feedback tone="success" className="mb-5">{savedMessage}</Feedback> : null}

      <div className="grid gap-5 xl:grid-cols-[380px_minmax(0,1fr)]">
        <div className="space-y-5">
          <Card title="Thiết bị" subtitle="Quét ADB trước khi bắt đầu bot.">
            <div className="flex items-center justify-between gap-3 rounded-lg border border-white/10 bg-black/20 px-4 py-3">
              <div className="min-w-0">
                <p className="text-xs font-medium uppercase tracking-wide text-slate-500">LDPlayer đang chọn</p>
                <p className="mt-1 truncate font-mono text-sm text-white">{status?.active_devices?.[0] ?? config?.adb?.device ?? "Chưa có thiết bị"}</p>
              </div>
              <StatusBadge status={status} />
            </div>
            <Button className="mt-4 w-full" variant="primary" loading={busyAction === "scan"} disabled={Boolean(busyAction) || Boolean(status?.running)} onClick={() => runAction("scan", scanAdb)}>
              <RefreshCw className="h-4 w-4" />Quét ADB
            </Button>
          </Card>

          <Card title="Điều khiển bot">
            <div className="grid grid-cols-3 gap-2">
              <Button variant="success" loading={busyAction === "start" || saving} disabled={Boolean(busyAction) || saving || Boolean(status?.running) || !status?.adb_ready} onClick={() => runAction("start", handleStartBot)}>
                <CirclePlay className="h-4 w-4" /><span className="hidden sm:inline">Bắt đầu</span><span className="sm:hidden">Chạy</span>
              </Button>
              <Button variant="warning" loading={busyAction === "pause"} disabled={Boolean(busyAction) || !status?.running} onClick={() => runAction("pause", togglePause)}>
                <CirclePause className="h-4 w-4" />{status?.paused ? "Tiếp tục" : "Tạm dừng"}
              </Button>
              <Button variant="danger" loading={busyAction === "stop"} disabled={Boolean(busyAction) || !status?.running} onClick={() => runAction("stop", stopBot)}>
                <Square className="h-4 w-4" />Dừng
              </Button>
            </div>
          </Card>

          <Card title="Trạng thái phiên">
            <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-3 text-sm">
              <dt className="text-slate-500">Trạng thái</dt><dd className="text-right font-medium text-white">{status?.status ?? "Đang kết nối..."}</dd>
              <dt className="text-slate-500">Combo</dt><dd className="truncate text-right font-medium text-white">{selectedCombo || "Chưa chọn"}</dd>
              <dt className="text-slate-500">Góc đánh</dt><dd className="text-right font-medium text-white">{viewLabels[config?.farm?.attack_view] ?? config?.farm?.attack_view ?? "Chưa chọn"}</dd>
              <dt className="text-slate-500">Next</dt><dd className="text-right font-mono font-medium text-white">{Number(stats?.current_session?.next ?? 0).toLocaleString("vi-VN")}</dd>
            </dl>
            {lastError ? <Feedback tone="warning" className="mt-4 break-words">{lastError}</Feedback> : null}
          </Card>
        </div>

        <div className="min-w-0 space-y-5">
          <Card title="Thống kê phiên"><StatGrid stats={stats} /></Card>

          <Card
            title="Số quân thủ công"
            subtitle="Số lượng theo combo; vị trí slot vẫn lấy từ nhận diện template."
            action={<Button variant="success" loading={saving} disabled={loading || !config || !isDirty} onClick={save}>Lưu cấu hình</Button>}
          >
            {loading ? <LoadingState /> : (
              <div className="space-y-4">
                <Toggle label="Dùng số quân nhập tay" hint="Tắt để bot đọc số lượng trực tiếp trên thanh quân." checked={Boolean(manualArmy.enabled)} disabled={!config} onChange={(value) => updatePath(["manual_army", "enabled"], value)} />
                {manualArmy.enabled ? (
                  <>
                    <SelectInput label="Combo áp dụng" value={selectedCombo} options={comboOptions} disabled={!comboOptions.length} onChange={(event) => updatePath(["farm", "combo"], event.target.value)} />
                    {comboSlots.length ? (
                      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                        {comboSlots.map((kind) => (
                          <TextInput key={kind} type="number" min={0} max={config?.slot_detection?.count_max_by_kind?.[kind] ?? 99} label={slotLabels[kind] ?? kind} value={String(manualArmy.counts?.[kind] ?? 0)} onChange={(event) => updatePath(["manual_army", "counts", kind], numberValue(event.target.value))} />
                        ))}
                      </div>
                    ) : <Feedback tone="warning">Combo này chưa có quân hoặc thuốc.</Feedback>}
                    {isDirty ? <Feedback tone="warning">Số quân đã thay đổi nhưng chưa lưu.</Feedback> : null}
                  </>
                ) : null}
              </div>
            )}
          </Card>

          <Card title="Theo dõi chạy tool"><LogPanel logs={logs} onClear={handleClearLogs} /></Card>
        </div>
      </div>
    </div>
  );
}
