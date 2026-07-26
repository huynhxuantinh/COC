import type { ReactNode } from "react";

type Props = {
  eyebrow?: string;
  title: string;
  subtitle?: string;
  action?: ReactNode;
};

export function PageHeader({ eyebrow, title, subtitle, action }: Props) {
  return (
    <header className="mb-5 flex flex-col gap-4 rounded-2xl border border-white/10 bg-ink-850/80 p-5 shadow-panel lg:flex-row lg:items-center lg:justify-between">
      <div>
        {eyebrow ? <p className="text-xs font-bold uppercase tracking-[0.22em] text-cobalt">{eyebrow}</p> : null}
        <h1 className="mt-1 text-2xl font-black text-white">{title}</h1>
        {subtitle ? <p className="mt-2 max-w-3xl text-sm text-slate-400">{subtitle}</p> : null}
      </div>
      {action ? <div className="shrink-0">{action}</div> : null}
    </header>
  );
}
