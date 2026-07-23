import type { BotStatus } from "../services/types";

export function StatusBadge({ status }: { status: BotStatus | null }) {
  const running = status?.running;
  const paused = status?.paused;
  const adbReady = status?.adb_ready;
  const label = running ? (paused ? "Tạm dừng" : "Đang chạy") : adbReady ? "Sẵn sàng" : "Chưa kết nối";
  const color = running
    ? paused
      ? "bg-warning/15 text-amber-300 ring-warning/30"
      : "bg-limewash/15 text-lime-300 ring-limewash/30"
    : adbReady
      ? "bg-sky-400/15 text-sky-300 ring-sky-400/30"
      : "bg-slate-500/15 text-slate-300 ring-slate-400/20";

  return <span className={`rounded-full px-3 py-1 text-xs font-bold ring-1 ${color}`}>{label}</span>;
}
