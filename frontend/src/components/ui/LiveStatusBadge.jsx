import { useWebSocketStatus } from "../../hooks/useWebSocket"
import { Radio } from "lucide-react"

export default function LiveStatusBadge({ className = "" }) {
  const status = useWebSocketStatus()

  const config = {
    connected: {
      color: "bg-emerald-950 border-emerald-800 text-emerald-300",
      dot: "bg-emerald-400 animate-pulse",
      label: "Live Stream: Connected",
    },
    reconnecting: {
      color: "bg-amber-950 border-amber-800 text-amber-300",
      dot: "bg-amber-400 animate-ping",
      label: "Live Stream: Reconnecting...",
    },
    connecting: {
      color: "bg-cyan-950 border-cyan-800 text-cyan-300",
      dot: "bg-cyan-400 animate-pulse",
      label: "Live Stream: Connecting...",
    },
    offline: {
      color: "bg-slate-900 border-slate-800 text-slate-400",
      dot: "bg-slate-500",
      label: "Live Stream: Offline",
    },
  }[status] || {
    color: "bg-slate-900 border-slate-800 text-slate-400",
    dot: "bg-slate-500",
    label: "Live Stream: Offline",
  }

  return (
    <div
      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full border text-[11px] font-mono font-medium transition ${config.color} ${className}`}
      title="Real-Time WebSocket event connection status"
    >
      <Radio className="w-3 h-3 opacity-80" />
      <span className={`w-1.5 h-1.5 rounded-full ${config.dot}`} />
      <span>{config.label}</span>
    </div>
  )
}
