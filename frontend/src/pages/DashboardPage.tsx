import { useCallback, useRef, useState } from "react";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { LogPanel } from "../components/LogPanel";
import { StatGrid } from "../components/StatGrid";
import { apiErrorMessage } from "../services/http";
import { clearLogs, getLogs } from "../services/logsApi";
import { getStats } from "../services/statsApi";
import { scanAdb, startBot, stopBot, togglePause } from "../services/botApi";
import type { BotStatus, LogEntry, StatsPayload } from "../services/types";
import { usePolling } from "../hooks/usePolling";

type Props = {
  status: BotStatus | null;
  refreshStatus: () => Promise<void>;
};

export function DashboardPage({ status, refreshStatus }: Props) {
  const [stats, setStats] = useState<StatsPayload | null>(null);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [error, setError] = useState("");
  const [busyAction, setBusyAction] = useState("");
  const afterRef = useRef(0);

  const refreshStats = useCallback(async () => {
    setStats(await getStats());
  }, []);

  const refreshLogs = useCallback(async () => {
    const payload = await getLogs(afterRef.current);
    if (payload.items.length) {
      setLogs((current) => [...current, ...payload.items].slice(-500));
    }
    afterRef.current = payload.next_after;
  }, []);

  usePolling(refreshStats, 2000);
  usePolling(refreshLogs, 1200);

  async function runAction(name: string, action: () => Promise<BotStatus | void>) {
    setError("");
    setBusyAction(name);
    try {
      await action();
      await refreshStatus();
      await refreshStats();
      await refreshLogs();
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setBusyAction("");
    }
  }

  async function handleClearLogs() {
    setError("");
    try {
      await clearLogs();
      afterRef.current = 0;
      setLogs([]);
    } catch (err) {
      setError(apiErrorMessage(err));
    }
  }

  return (
    <div className="space-y-5">
      <Card title="Trung tâm điều khiển" subtitle="Quét ADB trước, sau đó bắt đầu bot.">
        <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
          <div>
            <p className="text-2xl font-black text-white">{status?.status ?? "Đang tải..."}</p>
            <p className="mt-1 text-sm text-slate-400">
              ADB: {status?.adb_ready ? "đã kết nối" : "chưa kết nối"} · Bot:{" "}
              {status?.running ? (status.paused ? "tạm dừng" : "đang chạy") : "đang dừng"}
            </p>
          </div>
          <div className="grid grid-cols-2 gap-2 sm:flex">
            <Button variant="primary" disabled={busyAction !== "" || status?.running} onClick={() => runAction("scan", scanAdb)}>
              {busyAction === "scan" ? "Đang quét..." : "Quét ADB"}
            </Button>
            <Button variant="success" disabled={busyAction !== "" || status?.running} onClick={() => runAction("start", startBot)}>
              Bắt đầu
            </Button>
            <Button variant="muted" disabled={busyAction !== ""} onClick={() => runAction("pause", togglePause)}>
              {status?.paused ? "Tiếp tục" : "Tạm dừng"}
            </Button>
            <Button variant="danger" disabled={busyAction !== ""} onClick={() => runAction("stop", stopBot)}>
              Dừng
            </Button>
          </div>
        </div>
        {error && <div className="mt-4 rounded-lg border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-rose-200">{error}</div>}
      </Card>

      <Card title="Thống kê phiên" subtitle="Dữ liệu lấy từ callback của bot và file stats.">
        <StatGrid stats={stats} />
      </Card>

      <Card title="Theo dõi chạy tool">
        <LogPanel logs={logs} onClear={handleClearLogs} />
      </Card>
    </div>
  );
}
