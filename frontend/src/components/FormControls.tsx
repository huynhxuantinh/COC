import type { InputHTMLAttributes, SelectHTMLAttributes } from "react";
import type { SelectOption } from "../services/types";

type InputProps = InputHTMLAttributes<HTMLInputElement> & {
  label: string;
  hint?: string;
};

export function TextInput({ label, hint, className = "", ...props }: InputProps) {
  return (
    <label className="block">
      <span className="text-sm font-medium text-slate-300">{label}</span>
      <input
        className={`mt-2 w-full rounded-lg border border-white/10 bg-ink-950 px-3 py-2.5 text-sm text-white outline-none transition placeholder:text-slate-600 focus:border-sky-400 ${className}`}
        {...props}
      />
      {hint && <span className="mt-1 block text-xs text-slate-500">{hint}</span>}
    </label>
  );
}

type SelectProps = SelectHTMLAttributes<HTMLSelectElement> & {
  label: string;
  options: SelectOption[];
};

export function SelectInput({ label, options, className = "", ...props }: SelectProps) {
  return (
    <label className="block">
      <span className="text-sm font-medium text-slate-300">{label}</span>
      <select
        className={`mt-2 w-full rounded-lg border border-white/10 bg-ink-950 px-3 py-2.5 text-sm text-white outline-none transition focus:border-sky-400 ${className}`}
        {...props}
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
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
      className="flex w-full items-center justify-between gap-3 rounded-xl border border-white/10 bg-ink-900 px-3 py-3 text-left text-sm text-slate-200 transition hover:border-sky-400/40 disabled:opacity-50"
    >
      <span>
        <span className="block">{label}</span>
        {hint ? <span className="mt-1 block text-xs font-normal text-slate-500">{hint}</span> : null}
      </span>
      <span className={`h-6 w-11 rounded-full p-1 transition ${checked ? "bg-limewash" : "bg-slate-700"}`}>
        <span className={`block h-4 w-4 rounded-full bg-slate-950 transition ${checked ? "translate-x-5" : ""}`} />
      </span>
    </button>
  );
}
