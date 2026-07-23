import type { LogEntry } from "../services/types";
import { Button } from "./Button";

type Props = {
  logs: LogEntry[];
  onClear: () => void;
};

export function LogPanel({ logs, onClear }: Props) {
  return (
    <div className="rounded-xl border border-white/10 bg-black/35">
      <div className="flex items-center justify-between border-b border-white/10 px-4 py-3">
        <div>
          <p className="text-sm font-semibold text-white">Logs</p>
          <p className="text-xs text-slate-500">ADB, OCR, tìm trận, thả quân, đầu hàng</p>
        </div>
        <Button variant="muted" onClick={onClear}>
          Xóa
        </Button>
      </div>
      <div className="h-[360px] overflow-auto p-4 font-mono text-xs leading-6 text-slate-200">
        {logs.length === 0 ? (
          <p className="text-slate-500">Chưa có log.</p>
        ) : (
          logs.map((item) => (
            <div key={item.id} className="whitespace-pre-wrap border-b border-white/5 py-1 last:border-0">
              {item.message}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
