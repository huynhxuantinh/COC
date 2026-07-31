import type { ReactNode } from "react";

export type SegmentOption = {
  value: string;
  label: string;
  icon?: ReactNode;
};

export function SegmentedControl({ value, options, onChange, columns = 4, disabled = false }: { value: string; options: SegmentOption[]; onChange: (value: string) => void; columns?: number; disabled?: boolean }) {
  return (
    <div className="grid gap-2" style={{ gridTemplateColumns: `repeat(${Math.min(columns, options.length || 1)}, minmax(0, 1fr))` }}>
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          disabled={disabled}
          aria-pressed={value === option.value}
          onClick={() => onChange(option.value)}
          className={`flex min-h-10 items-center justify-center gap-2 rounded-lg border px-3 py-2 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-40 ${
            value === option.value
              ? "border-sky-300 bg-sky-400 text-slate-950"
              : "border-white/10 bg-ink-900 text-slate-300 hover:border-sky-400/50 hover:text-white"
          }`}
        >
          {option.icon}
          <span className="truncate">{option.label}</span>
        </button>
      ))}
    </div>
  );
}
