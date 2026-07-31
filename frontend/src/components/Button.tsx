import type { ButtonHTMLAttributes, ReactNode } from "react";

type Variant = "primary" | "success" | "warning" | "danger" | "muted" | "ghost";
type Size = "sm" | "md";

const variantClass: Record<Variant, string> = {
  primary: "bg-sky-400 text-slate-950 hover:bg-sky-300",
  success: "bg-limewash text-slate-950 hover:bg-lime-300",
  warning: "bg-amber-400 text-slate-950 hover:bg-amber-300",
  danger: "bg-danger text-white hover:bg-rose-400",
  muted: "border border-white/10 bg-ink-700 text-slate-100 hover:border-white/20 hover:bg-slate-600",
  ghost: "bg-transparent text-slate-300 hover:bg-white/5 hover:text-white",
};

const sizeClass: Record<Size, string> = {
  sm: "h-9 px-3 text-xs",
  md: "h-10 px-4 text-sm",
};

type Props = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
  children: ReactNode;
};

export function Button({ variant = "muted", size = "md", loading = false, className = "", children, disabled, type = "button", ...props }: Props) {
  return (
    <button
      type={type}
      disabled={disabled || loading}
      className={`inline-flex shrink-0 items-center justify-center gap-2 rounded-lg font-semibold transition disabled:cursor-not-allowed disabled:opacity-40 ${sizeClass[size]} ${variantClass[variant]} ${className}`}
      {...props}
    >
      {loading ? <span className="h-4 w-4 animate-spin rounded-full border-2 border-current border-r-transparent" aria-hidden="true" /> : null}
      {children}
    </button>
  );
}
