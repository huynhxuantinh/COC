import { AlertCircle, CheckCircle2, Info, TriangleAlert } from "lucide-react";
import type { ReactNode } from "react";

type Tone = "info" | "success" | "warning" | "error";

const styles: Record<Tone, string> = {
  info: "border-sky-400/30 bg-sky-400/10 text-sky-100",
  success: "border-limewash/30 bg-limewash/10 text-lime-100",
  warning: "border-amber-400/30 bg-amber-400/10 text-amber-100",
  error: "border-danger/35 bg-danger/10 text-rose-100",
};

const icons = {
  info: Info,
  success: CheckCircle2,
  warning: TriangleAlert,
  error: AlertCircle,
};

export function Feedback({ tone = "info", children, className = "" }: { tone?: Tone; children: ReactNode; className?: string }) {
  const Icon = icons[tone];
  return (
    <div role={tone === "error" ? "alert" : "status"} className={`flex items-start gap-3 rounded-lg border px-4 py-3 text-sm ${styles[tone]} ${className}`}>
      <Icon className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
      <div className="min-w-0 flex-1">{children}</div>
    </div>
  );
}

export function LoadingState({ label = "Đang tải dữ liệu..." }: { label?: string }) {
  return (
    <div className="flex min-h-40 items-center justify-center gap-3 rounded-lg border border-white/10 bg-ink-850 text-sm text-slate-400">
      <span className="h-5 w-5 animate-spin rounded-full border-2 border-sky-400 border-r-transparent" />
      {label}
    </div>
  );
}

export function EmptyState({ title, description }: { title: string; description?: string }) {
  return (
    <div className="rounded-lg border border-dashed border-white/15 bg-black/15 px-5 py-8 text-center">
      <p className="text-sm font-semibold text-slate-200">{title}</p>
      {description ? <p className="mt-1 text-xs text-slate-500">{description}</p> : null}
    </div>
  );
}
