import { ArrowDown, ListFilter, Trash2 } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import type { LogEntry } from "../services/types";
import { Button } from "./Button";
import { EmptyState } from "./Feedback";

type Props = {
  logs: LogEntry[];
  onClear: () => void;
};

function isCompactLog(message: string): boolean {
  if (message.includes("[ERROR]") || message.includes("[WARN]") || message.includes("[INFO]")) return true;
  if (/\[BATTLE\]\s+\d+s\s+\|\s+damage=/.test(message)) return false;
  if (/\[SEARCH\]\s+OCR could not read loot/.test(message)) return false;
  if (message.includes("[SPELL] Cast ") || message.includes("[CAMERA] ")) return false;
  return true;
}

export function LogPanel({ logs, onClear }: Props) {
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const [showDetails, setShowDetails] = useState(false);
  const [followTail, setFollowTail] = useState(true);
  const visibleLogs = useMemo(() => {
    const filtered = showDetails ? logs : logs.filter((item) => isCompactLog(item.message));
    return filtered.slice(-800);
  }, [logs, showDetails]);
  const hiddenCount = Math.max(0, logs.length - visibleLogs.length);

  function scrollToBottom() {
    const element = scrollRef.current;
    if (!element) return;
    element.scrollTop = element.scrollHeight;
    setFollowTail(true);
  }

  useEffect(() => {
    if (followTail) scrollToBottom();
  }, [followTail, visibleLogs.length]);

  function handleScroll() {
    const element = scrollRef.current;
    if (!element) return;
    const nearBottom = element.scrollHeight - element.scrollTop - element.clientHeight < 48;
    setFollowTail(nearBottom);
  }

  return (
    <div className="overflow-hidden rounded-lg border border-white/10 bg-black/30">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/10 px-4 py-3">
        <div className="min-w-0">
          <p className="text-sm font-semibold text-white">Log thời gian thực</p>
          <p className="mt-0.5 text-xs text-slate-500">
            {showDetails ? "Hiển thị log chi tiết" : hiddenCount ? `Đã ẩn ${hiddenCount} dòng ít quan trọng` : "Chỉ hiển thị log cần thiết"}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {!followTail ? (
            <Button size="sm" variant="primary" onClick={scrollToBottom}><ArrowDown className="h-4 w-4" />Log mới</Button>
          ) : null}
          <Button size="sm" variant="muted" onClick={() => setShowDetails((value) => !value)}><ListFilter className="h-4 w-4" />{showDetails ? "Thu gọn" : "Chi tiết"}</Button>
          <Button size="sm" variant="ghost" onClick={onClear}><Trash2 className="h-4 w-4" />Xóa</Button>
        </div>
      </div>
      <div ref={scrollRef} onScroll={handleScroll} className="h-[360px] overflow-auto overscroll-contain p-4 font-mono text-xs leading-6 text-slate-300">
        {visibleLogs.length === 0 ? (
          <EmptyState title="Chưa có log" description="Log ADB, OCR và trận đấu sẽ xuất hiện tại đây." />
        ) : (
          visibleLogs.map((item) => (
            <div key={item.id} className="break-words border-b border-white/5 py-1.5 last:border-0">{item.message}</div>
          ))
        )}
      </div>
    </div>
  );
}
