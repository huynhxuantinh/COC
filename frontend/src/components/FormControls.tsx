import type { InputHTMLAttributes, SelectHTMLAttributes } from "react";
import type { SelectOption } from "../services/types";

type InputProps = InputHTMLAttributes<HTMLInputElement> & {
  label: string;
  hint?: string;
  suffix?: string;
  error?: string;
};

export function TextInput({ label, hint, suffix, error, className = "", ...props }: InputProps) {
  return (
    <label className="block min-w-0">
      {label ? <span className="block text-sm font-medium text-slate-300">{label}</span> : null}
      <span className={`relative block ${label ? "mt-2" : ""}`}>
        <input
          className={`h-10 w-full rounded-lg border bg-ink-950 px-3 text-sm text-white outline-none transition placeholder:text-slate-600 disabled:cursor-not-allowed disabled:bg-ink-900 disabled:text-slate-500 ${suffix ? "pr-12" : ""} ${error ? "border-danger/70" : "border-white/10 focus:border-sky-400"} ${className}`}
          {...props}
        />
        {suffix ? <span className="pointer-events-none absolute inset-y-0 right-3 flex items-center text-xs font-semibold text-slate-500">{suffix}</span> : null}
      </span>
      {error ? <span className="mt-1 block text-xs text-rose-300">{error}</span> : hint ? <span className="mt-1 block text-xs leading-5 text-slate-500">{hint}</span> : null}
    </label>
  );
}

type SelectProps = SelectHTMLAttributes<HTMLSelectElement> & {
  label: string;
  options: SelectOption[];
  hint?: string;
};

export function SelectInput({ label, options, hint, className = "", ...props }: SelectProps) {
  return (
    <label className="block min-w-0">
      {label ? <span className="block text-sm font-medium text-slate-300">{label}</span> : null}
      <select
        className={`${label ? "mt-2" : ""} h-10 w-full truncate rounded-lg border border-white/10 bg-ink-950 px-3 text-sm text-white outline-none transition focus:border-sky-400 disabled:cursor-not-allowed disabled:bg-ink-900 disabled:text-slate-500 ${className}`}
        {...props}
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
      {hint ? <span className="mt-1 block text-xs leading-5 text-slate-500">{hint}</span> : null}
    </label>
  );
}

type ToggleProps = {
  label: string;
  hint?: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
  disabled?: boolean;
};

export function Toggle({ label, hint, checked, onChange, disabled = false }: ToggleProps) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={() => onChange(!checked)}
      aria-pressed={checked}
      className="flex min-h-14 w-full items-center justify-between gap-4 rounded-lg border border-white/10 bg-ink-900 px-4 py-3 text-left text-sm text-slate-200 transition hover:border-sky-400/40 disabled:cursor-not-allowed disabled:opacity-45"
    >
      <span>
        <span className="block">{label}</span>
        {hint ? <span className="mt-1 block text-xs font-normal text-slate-500">{hint}</span> : null}
      </span>
      <span className={`h-6 w-11 shrink-0 rounded-full p-1 transition ${checked ? "bg-limewash" : "bg-slate-700"}`}>
        <span className={`block h-4 w-4 rounded-full bg-slate-950 transition-transform ${checked ? "translate-x-5" : ""}`} />
      </span>
    </button>
  );
}
