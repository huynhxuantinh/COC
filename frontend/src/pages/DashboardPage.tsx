import { useCallback, useRef, useState } from "react";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { SelectInput, TextInput, Toggle } from "../components/FormControls";
import { LogPanel } from "../components/LogPanel";
import { StatGrid } from "../components/StatGrid";
import { numberValue, useConfigEditor } from "../hooks/useConfigEditor";
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
  const [actionError, setActionError] = useState("");
  const [busyAction, setBusyAction] = useState("");
  const afterRef = useRef(0);
  const {
    config,
    loading: configLoading,
    saving: configSaving,
    error: configError,
    savedMessage,
    isDirty,
    updatePath,
    save,
  } = useConfigEditor();
  const manualArmy = config?.manual_army ?? { enabled: false, counts: {} };
  const manualCounts = manualArmy.counts ?? {};

  const selectedCombo = config?.farm?.combo ?? "";
  const comboOptions = (Object.keys(config?.combos ?? {}).length ? Object.keys(config?.combos ?? {}) : [selectedCombo])
    .filter(Boolean)
    .map((name) => ({ label: name, value: name }));
  const deploy = selectedCombo && config?.combos?.[selectedCombo]
    ? (config.combos[selectedCombo].deploy ?? config.combos[selectedCombo])
    : config?.deploy;
  const slotLabels: Record<string, string> = {
    dragon: "Rồng điện",
    balloon: "Bóng",
    valkyrie: "Valkyrie",
    hero: "Tướng",
    rage: "Nộ",
    freeze: "Băng",
    poison: "Độc",
  };
  const comboSlots = Array.from(
    new Set<string>([
      ...((deploy?.sequence ?? []).map((step: any) => String(step.slot ?? "")).filter(Boolean)),
      ...((deploy?.spell_groups ?? [])
        .filter((group: any) => group.enabled !== false)
        .flatMap((group: any) => (group.slots ?? []).map((slot: unknown) => String(slot)).filter(Boolean))),
    ]),
  );

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
    setActionError("");
    setBusyAction(name);
    try {
      await action();
      await refreshStatus();
      await refreshStats();
      await refreshLogs();
    } catch (err) {
      setActionError(apiErrorMessage(err));
    } finally {
      setBusyAction("");
    }
  }

  async function handleClearLogs() {
    setActionError("");
    try {
      await clearLogs();
      afterRef.current = 0;
      setLogs([]);
    } catch (err) {
      setActionError(apiErrorMessage(err));
    }
  }

  async function handleStartBot() {
    if (isDirty) {
      await save();
    }
    return startBot();
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
            <Button variant="success" disabled={busyAction !== "" || configSaving || status?.running} onClick={() => runAction("start", handleStartBot)}>
              {busyAction === "start" || configSaving ? "Đang bắt đầu..." : "Bắt đầu"}
            </Button>
            <Button variant="muted" disabled={busyAction !== ""} onClick={() => runAction("pause", togglePause)}>
              {status?.paused ? "Tiếp tục" : "Tạm dừng"}
            </Button>
            <Button variant="danger" disabled={busyAction !== ""} onClick={() => runAction("stop", stopBot)}>
              Dừng
            </Button>
          </div>
        </div>
        {actionError && <div className="mt-4 rounded-lg border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-rose-200">{actionError}</div>}
      </Card>

      <Card
        title="Số quân thủ công"
        subtitle="Bật mục này nếu không muốn OCR số lượng trên thanh quân. Bot vẫn nhận diện vị trí slot, nhưng dùng số bạn nhập khi bắt đầu trận."
        action={
          <Button variant="success" disabled={configSaving || configLoading || !config} onClick={save}>
            {configSaving ? "Đang lưu..." : "Lưu số quân"}
          </Button>
        }
      >
        {(configError || savedMessage) && (
          <div className={`mb-4 rounded-lg px-4 py-3 text-sm ${configError ? "border border-danger/30 bg-danger/10 text-rose-200" : "border border-limewash/30 bg-limewash/10 text-lime-200"}`}>
            {configError || savedMessage}
          </div>
        )}
        <div className="mb-4">
          <Toggle
            label="Dùng số quân nhập tay"
            hint="Bật thì bot vẫn quét vị trí icon slot, nhưng không OCR số lượng. Tắt thì bot quét số lượng như bình thường."
            checked={Boolean(manualArmy.enabled)}
            disabled={configLoading || !config}
            onChange={(value) => updatePath(["manual_army", "enabled"], value)}
          />
        </div>
        <div className="mb-4">
          <SelectInput
            label="Combo áp dụng"
            value={selectedCombo}
            options={comboOptions}
            disabled={configLoading || !config}
            onChange={(event) => updatePath(["farm", "combo"], event.target.value)}
          />
        </div>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {comboSlots.map((kind) => (
            <TextInput
              key={kind}
              type="number"
              min={0}
              label={slotLabels[kind] ?? kind}
              disabled={configLoading || !config || !manualArmy.enabled}
              value={String(manualCounts[kind] ?? 0)}
              onChange={(event) => updatePath(["manual_army", "counts", kind], numberValue(event.target.value))}
            />
          ))}
        </div>
        {!comboSlots.length && <p className="mt-3 text-sm text-slate-400">Combo này chưa có slot quân/phép để nhập.</p>}
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
