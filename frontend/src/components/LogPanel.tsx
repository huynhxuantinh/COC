import { useEffect, useMemo, useRef, useState } from "react";
import type { LogEntry } from "../services/types";
import { Button } from "./Button";

type Props = {
  logs: LogEntry[];
  onClear: () => void;
};

function isCompactLog(message: string): boolean {
  if (message.includes("[ERROR]") || message.includes("[WARN]") || message.includes("[DEBUG]")) {
    return true;
  }
  if (/\[BATTLE\]\s+\d+s\s+\|\s+damage=/.test(message)) {
    return false;
  }
  if (/\[SEARCH\]\s+OCR could not read loot \(\d+s\), wait\./.test(message)) {
    return false;
  }
  if (message.includes("[SPELL] Cast ")) {
    return false;
  }
  if (message.includes("[CAMERA] ")) {
    return false;
  }
  return true;
}

export function LogPanel({ logs, onClear }: Props) {
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const [showDetails, setShowDetails] = useState(false);
  const visibleLogs = useMemo(() => (showDetails ? logs : logs.filter((item) => isCompactLog(item.message))), [logs, showDetails]);
  const hiddenCount = logs.length - visibleLogs.length;

  useEffect(() => {
    const element = scrollRef.current;
    if (!element) {
      return;
    }
    element.scrollTop = element.scrollHeight;
  }, [visibleLogs.length]);

  return (
    <div className="rounded-xl border border-white/10 bg-black/35">
      <div className="flex items-center justify-between gap-3 border-b border-white/10 px-4 py-3">
        <div>
          <p className="text-sm font-semibold text-white">Logs</p>
          <p className="text-xs text-slate-500">
            {showDetails ? "Đang hiện toàn bộ log." : hiddenCount > 0 ? `Đang ẩn ${hiddenCount} dòng log chi tiết.` : "Đang hiện log cần thiết."}
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="muted" onClick={() => setShowDetails((value) => !value)}>
            {showDetails ? "Gọn" : "Chi tiết"}
          </Button>
          <Button variant="muted" onClick={onClear}>
            Xóa
          </Button>
        </div>
      </div>
      <div ref={scrollRef} className="h-[360px] overflow-auto p-4 font-mono text-xs leading-6 text-slate-200">
        {visibleLogs.length === 0 ? (
          <p className="text-slate-500">Chưa có log.</p>
        ) : (
          visibleLogs.map((item) => (
            <div key={item.id} className="whitespace-pre-wrap border-b border-white/5 py-1 last:border-0">
              {item.message}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
