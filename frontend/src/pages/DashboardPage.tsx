import { CirclePause, CirclePlay, RefreshCw, Square } from "lucide-react";
import { useCallback, useMemo, useRef, useState } from "react";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { Feedback } from "../components/Feedback";
import { LogPanel } from "../components/LogPanel";
import { PageHeader } from "../components/PageHeader";
import { SegmentedControl } from "../components/SegmentedControl";
import { StatGrid } from "../components/StatGrid";
import { StatusBadge } from "../components/StatusBadge";
import { useConfigEditor } from "../hooks/useConfigEditor";
import { usePolling } from "../hooks/usePolling";
import { scanAdb, startBot, stopBot, togglePause } from "../services/botApi";
import { apiErrorMessage } from "../services/http";
import { clearLogs, getLogs } from "../services/logsApi";
import { getStats } from "../services/statsApi";
import type { BotStatus, LogEntry, StatsPayload } from "../services/types";

type Props = { status: BotStatus | null; refreshStatus: () => Promise<void> };

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
  const { config, saving, error, savedMessage, isDirty, updatePath, save, reload } = useConfigEditor();
  const selectedCombo = config?.farm?.combo ?? "";
  const villageMode = config?.farm?.village === "builder" ? "builder" : "main";

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
    if (isDirty) {
      if (!(await save())) throw new Error("Không lưu được cấu hình. Bot chưa được khởi động.");
      return;
    }
    return startBot();
  }

  async function handleScanAdb() {
    if (isDirty) {
      const shouldSave = window.confirm(
        "Cấu hình có thay đổi chưa lưu. Nhấn OK để lưu rồi quét ADB; nhấn Hủy để giữ thay đổi và không quét.",
      );
      if (!shouldSave) return;
      if (!(await save())) throw new Error("Không lưu được cấu hình. Chưa quét ADB.");
    }
    await scanAdb();
    await reload();
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
          <Card title="Chế độ chạy">
            <SegmentedControl
              value={villageMode}
              columns={2}
              disabled={Boolean(status?.running)}
              options={[
                { value: "main", label: "Làng chính" },
                { value: "builder", label: "Làng đêm" },
              ]}
              onChange={(value) => updatePath(["farm", "village"], value)}
            />
            <Button className="mt-3 w-full" size="sm" variant="success" loading={saving} disabled={!isDirty || Boolean(status?.running)} onClick={save}>
              Lưu chế độ
            </Button>
          </Card>

          <Card title="Điều khiển phiên" action={<StatusBadge status={status} />}>
            <div className="flex items-center justify-between gap-3 rounded-lg border border-white/10 bg-black/20 px-4 py-3">
              <div className="min-w-0">
                <p className="text-xs font-medium uppercase tracking-wide text-slate-500">Thiết bị</p>
                <p className="mt-1 truncate font-mono text-sm text-white">{status?.active_devices?.[0] ?? config?.adb?.device ?? "Chưa có thiết bị"}</p>
              </div>
              <Button size="sm" variant="muted" loading={busyAction === "scan"} disabled={Boolean(busyAction) || Boolean(status?.running)} onClick={() => runAction("scan", handleScanAdb)}>
                <RefreshCw className="h-4 w-4" />Quét ADB
              </Button>
            </div>
            <div className="mt-4 grid grid-cols-3 gap-2">
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
            <dl className="mt-5 grid grid-cols-[auto_1fr] gap-x-4 gap-y-3 border-t border-white/10 pt-5 text-sm">
              <dt className="text-slate-500">Trạng thái</dt><dd className="text-right font-medium text-white">{status?.status ?? "Đang kết nối..."}</dd>
              {villageMode === "main" ? (
                <>
                  <dt className="text-slate-500">Combo</dt><dd className="truncate text-right font-medium text-white">{selectedCombo || "Chưa chọn"}</dd>
                  <dt className="text-slate-500">Góc đánh</dt><dd className="text-right font-medium text-white">{viewLabels[config?.farm?.attack_view] ?? config?.farm?.attack_view ?? "Chưa chọn"}</dd>
                  <dt className="text-slate-500">Next</dt><dd className="text-right font-mono font-medium text-white">{Number(stats?.current_session?.next ?? 0).toLocaleString("vi-VN")}</dd>
                </>
              ) : (
                <>
                  <dt className="text-slate-500">Chiến thuật</dt><dd className="text-right font-medium text-white">Tướng + Night Witch</dd>
                  <dt className="text-slate-500">Giai đoạn</dt><dd className="text-right font-medium text-white">Làng 1 → Làng 2</dd>
                </>
              )}
            </dl>
            {lastError ? <Feedback tone="warning" className="mt-4 break-words">{lastError}</Feedback> : null}
          </Card>
        </div>

        <div className="min-w-0 space-y-5">
          <Card title="Thống kê phiên"><StatGrid stats={stats} mode={villageMode} /></Card>

          <Card title="Theo dõi chạy tool"><LogPanel logs={logs} onClear={handleClearLogs} /></Card>
        </div>
      </div>
    </div>
  );
}
