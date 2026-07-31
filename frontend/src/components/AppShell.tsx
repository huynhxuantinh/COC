import {
  Bot,
  Boxes,
  ChevronRight,
  Crosshair,
  FlaskConical,
  LayoutDashboard,
  ScanSearch,
  Settings,
  ShieldX,
  Swords,
} from "lucide-react";
import { NavLink, Outlet } from "react-router-dom";
import { useConfigEditor } from "../hooks/useConfigEditor";
import type { BotStatus } from "../services/types";
import { StatusBadge } from "./StatusBadge";

const navItems = [
  { to: "/", label: "Tổng quan", icon: LayoutDashboard },
  { to: "/farm", label: "Farm", icon: Swords },
  { to: "/combos", label: "Combo", icon: Boxes },
  { to: "/slots", label: "Nhận diện slot", icon: ScanSearch },
  { to: "/coordinates/troops", label: "Tọa độ thả lính", icon: Crosshair },
  { to: "/coordinates/spells", label: "Tọa độ thả thuốc", icon: FlaskConical },
  { to: "/surrender", label: "Đầu hàng", icon: ShieldX },
  { to: "/settings", label: "Cài đặt", icon: Settings },
];

export function AppShell({ status }: { status: BotStatus | null }) {
  const { config, isDirty } = useConfigEditor();
  const resolution = config?.game?.resolution ?? [1600, 900];
  const resolutionLabel = Array.isArray(resolution) && resolution.length >= 2 ? `${resolution[0]}x${resolution[1]}` : "1600x900";

  return (
    <div className="min-h-screen text-slate-100">
      <div className="mx-auto flex min-h-screen w-full max-w-[1680px] flex-col lg:flex-row">
        <aside className="z-30 border-b border-white/10 bg-ink-850/95 px-4 py-4 backdrop-blur lg:sticky lg:top-0 lg:h-screen lg:w-64 lg:shrink-0 lg:border-b-0 lg:border-r lg:px-4 lg:py-5">
          <div className="flex items-center justify-between gap-3 lg:px-2">
            <div className="flex min-w-0 items-center gap-3">
              <span className="grid h-10 w-10 shrink-0 place-items-center rounded-lg bg-sky-400 text-slate-950">
                <Bot className="h-5 w-5" />
              </span>
              <div className="min-w-0">
                <p className="truncate text-sm font-bold text-white">COC Auto Farm</p>
                <p className="truncate text-xs text-slate-500">LDPlayer · {resolutionLabel}</p>
              </div>
            </div>
            <div className="lg:hidden"><StatusBadge status={status} /></div>
          </div>

          <nav className="mt-4 flex gap-2 overflow-x-auto pb-1 lg:mt-6 lg:block lg:space-y-1 lg:overflow-visible" aria-label="Điều hướng chính">
            {navItems.map((item) => {
              const Icon = item.icon;
              return (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.to === "/"}
                  className={({ isActive }) =>
                    `group flex h-11 shrink-0 items-center gap-3 rounded-lg px-3 text-sm font-semibold transition lg:w-full ${
                      isActive
                        ? "bg-sky-400 text-slate-950"
                        : "text-slate-400 hover:bg-white/5 hover:text-white"
                    }`
                  }
                >
                  <Icon className="h-[18px] w-[18px] shrink-0" />
                  <span className="whitespace-nowrap">{item.label}</span>
                  <ChevronRight className="ml-auto hidden h-4 w-4 opacity-0 transition group-hover:opacity-60 lg:block" />
                </NavLink>
              );
            })}
          </nav>

          <div className="mt-5 hidden border-t border-white/10 pt-5 lg:block">
            <div className="flex items-center justify-between gap-3">
              <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">Bot</span>
              <StatusBadge status={status} />
            </div>
            {status?.active_devices?.length ? (
              <p className="mt-3 truncate font-mono text-xs text-slate-500" title={status.active_devices.join(", ")}>{status.active_devices.join(", ")}</p>
            ) : (
              <p className="mt-3 text-xs text-slate-600">Chưa chọn thiết bị</p>
            )}
            {isDirty ? <p className="mt-3 rounded-lg border border-amber-300/25 bg-amber-300/10 px-3 py-2 text-xs font-medium text-amber-100">Có thay đổi chưa lưu</p> : null}
          </div>
        </aside>

        <main className="min-w-0 flex-1 overflow-x-hidden px-4 py-5 sm:px-6 lg:h-screen lg:overflow-y-auto lg:px-8 lg:py-7">
          <div className="mx-auto w-full max-w-[1360px]"><Outlet /></div>
        </main>
      </div>
    </div>
  );
}
