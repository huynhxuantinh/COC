import type { ButtonHTMLAttributes, ReactNode } from "react";

type Variant = "primary" | "success" | "danger" | "muted";

const variantClass: Record<Variant, string> = {
  primary: "bg-sky-400 text-slate-950 hover:bg-sky-300",
  success: "bg-limewash text-slate-950 hover:bg-lime-300",
  danger: "bg-danger text-white hover:bg-rose-400",
  muted: "bg-ink-700 text-slate-100 hover:bg-slate-600",
};

type Props = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: Variant;
  children: ReactNode;
};

export function Button({ variant = "muted", className = "", children, ...props }: Props) {
  return (
    <button
      className={`inline-flex items-center justify-center rounded-lg px-4 py-2.5 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-45 ${variantClass[variant]} ${className}`}
      {...props}
    >
      {children}
    </button>
  );
}
