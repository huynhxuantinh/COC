import type { StatsPayload } from "../services/types";

const labels: Record<string, string> = {
  attacks: "Trận",
  next: "Next",
  gold_seen: "Vàng",
  elixir_seen: "Dầu",
  dark_seen: "Dầu đen",
};

export function StatGrid({ stats }: { stats: StatsPayload | null }) {
  const current = stats?.current_session ?? {};
  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
      {Object.entries(labels).map(([key, label]) => (
        <div key={key} className="rounded-xl border border-white/10 bg-ink-900 p-4">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</p>
          <p className="mt-2 text-xl font-bold text-white">{Number(current[key] ?? 0).toLocaleString("vi-VN")}</p>
        </div>
      ))}
    </div>
  );
}
