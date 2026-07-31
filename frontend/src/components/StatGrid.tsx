import type { StatsPayload } from "../services/types";

const labels: Record<string, string> = {
  attacks: "Trận",
  next: "Next",
  gold_seen: "Vàng nhận",
  elixir_seen: "Dầu nhận",
};

export function StatGrid({ stats }: { stats: StatsPayload | null }) {
  const current = stats?.current_session ?? {};
  return (
    <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
      {Object.entries(labels).map(([key, label]) => (
        <div key={key} className="min-w-0 rounded-lg border border-white/10 bg-ink-900 p-4">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</p>
          <p className="mt-2 truncate text-xl font-bold tabular-nums text-white" title={Number(current[key] ?? 0).toLocaleString("vi-VN")}>{Number(current[key] ?? 0).toLocaleString("vi-VN")}</p>
        </div>
      ))}
    </div>
  );
}
