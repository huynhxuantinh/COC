import type { StatsPayload } from "../services/types";

const mainLabels: Record<string, string> = {
  attacks: "Trận",
  next: "Next",
  gold_seen: "Vàng nhận",
  elixir_seen: "Dầu nhận",
};

const builderLabels: Record<string, string> = {
  builder_attacks: "Trận",
  builder_gold: "Vàng nhận",
  builder_elixir: "Dầu nhận",
  builder_trophies: "Cúp nhận",
  builder_damage: "Tổng phá hủy",
};

export function StatGrid({ stats, mode = "main" }: { stats: StatsPayload | null; mode?: "main" | "builder" }) {
  const current = stats?.current_session ?? {};
  const labels = mode === "builder" ? builderLabels : mainLabels;
  return (
    <div className={`grid grid-cols-2 gap-3 ${mode === "builder" ? "xl:grid-cols-5" : "xl:grid-cols-4"}`}>
      {Object.entries(labels).map(([key, label]) => (
        <div key={key} className="min-w-0 rounded-lg border border-white/10 bg-ink-900 p-4">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</p>
          <p className="mt-2 truncate text-xl font-bold tabular-nums text-white" title={Number(current[key] ?? 0).toLocaleString("vi-VN")}>
            {Number(current[key] ?? 0).toLocaleString("vi-VN")}{mode === "builder" && key === "builder_damage" ? "%" : ""}
          </p>
        </div>
      ))}
    </div>
  );
}
