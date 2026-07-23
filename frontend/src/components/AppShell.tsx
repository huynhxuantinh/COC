import { NavLink, Outlet } from "react-router-dom";
import type { BotStatus } from "../services/types";
import { StatusBadge } from "./StatusBadge";

const navItems = [
  { to: "/", label: "Tổng quan" },
  { to: "/farm", label: "Farm" },
  { to: "/coordinates", label: "Tọa độ" },
  { to: "/surrender", label: "Đầu hàng" },
  { to: "/settings", label: "Cài đặt" },
];

export function AppShell({ status }: { status: BotStatus | null }) {
  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top_left,_rgba(56,189,248,0.14),_transparent_32%),linear-gradient(145deg,#090b10,#111827_55%,#0f131b)] text-slate-100">
      <div className="mx-auto flex min-h-screen w-full max-w-[1500px] flex-col gap-4 px-4 py-4 lg:flex-row lg:gap-6 lg:px-6">
        <aside className="rounded-2xl border border-white/10 bg-ink-850/90 p-4 shadow-panel lg:sticky lg:top-6 lg:h-[calc(100vh-48px)] lg:w-72">
          <div className="flex items-start justify-between gap-3 lg:block">
            <div>
              <p className="text-xs font-bold uppercase tracking-[0.2em] text-cobalt">COC Control</p>
              <h1 className="mt-2 text-2xl font-black text-white">Auto Farm</h1>
              <p className="mt-2 text-sm text-slate-400">LDPlayer 1600x900 qua ADB</p>
            </div>
            <StatusBadge status={status} />
          </div>
          <nav className="mt-5 grid grid-cols-2 gap-2 lg:grid-cols-1">
            {navItems.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  `rounded-xl px-4 py-3 text-sm font-semibold transition ${
                    isActive ? "bg-sky-400 text-slate-950" : "bg-ink-900 text-slate-300 hover:bg-ink-700"
                  }`
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
          <div className="mt-5 rounded-xl border border-white/10 bg-black/25 p-4 text-sm text-slate-300">
            <p className="font-semibold text-white">Trạng thái</p>
            <p className="mt-2 text-slate-400">{status?.status ?? "Đang kết nối backend..."}</p>
            {status?.active_devices?.length ? (
              <p className="mt-2 text-xs text-slate-500">Device: {status.active_devices.join(", ")}</p>
            ) : null}
          </div>
        </aside>
        <main className="min-w-0 flex-1 pb-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
