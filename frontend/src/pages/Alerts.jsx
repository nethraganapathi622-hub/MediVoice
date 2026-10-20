import { useState, useEffect, useCallback } from "react"
import { AlertTriangle, Bell, CheckCircle2, ArrowLeft, RefreshCw, AlertCircle } from "lucide-react"
import { Link } from "react-router-dom"
import Badge from "../components/ui/Badge"
import LiveStatusBadge from "../components/ui/LiveStatusBadge"
import { useWebSocketEvent } from "../hooks/useWebSocket"
import { getAlerts, acknowledgeAlert } from "../services/api"

export default function Alerts() {
  const [severityFilter, setSeverityFilter] = useState("all")
  const [alerts, setAlerts] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [toast, setToast] = useState(null)
  const [actionLoadingId, setActionLoadingId] = useState(null)

  const loadAlerts = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await getAlerts()
      setAlerts(data)
    } catch (err) {
      setError(err.message || "Failed to load triage alerts from hospital API.")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    let isMounted = true
    getAlerts()
      .then((data) => {
        if (isMounted) {
          setAlerts(data)
          setError(null)
        }
      })
      .catch((err) => {
        if (isMounted) setError(err.message || "Failed to load triage alerts from hospital API.")
      })
      .finally(() => {
        if (isMounted) setLoading(false)
      })
    return () => {
      isMounted = false
    }
  }, [])

  // Real-time synchronization
  useWebSocketEvent("alert.*", loadAlerts)
  useWebSocketEvent("reconnect", loadAlerts)

  const filtered = alerts.filter((a) => {
    if (severityFilter === "all") return true
    return a.priority.toLowerCase() === severityFilter.toLowerCase()
  })

  const handleAcknowledge = async (id) => {
    setActionLoadingId(id)
    try {
      const updated = await acknowledgeAlert(id, "STAFF-EMERG-01", "Nurse Supervisor", "TriageLead")
      setAlerts((prev) => prev.map((a) => (a.id === id ? updated : a)))
      setToast(`Alert #${id} acknowledged and logged with staff credentials.`)
      setTimeout(() => setToast(null), 3500)
    } catch (err) {
      setToast(`Error acknowledging alert: ${err.message}`)
      setTimeout(() => setToast(null), 4000)
    } finally {
      setActionLoadingId(null)
    }
  }

  const formatTime = (timeStr) => {
    if (!timeStr) return "--:--"
    const d = new Date(timeStr)
    return isNaN(d) ? timeStr : d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
  }

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-10 space-y-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-6">
        <div>
          <div className="flex items-center gap-2">
            <Link to="/staff" className="text-slate-400 hover:text-white transition">
              <ArrowLeft className="w-5 h-5" />
            </Link>
            <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
              Hospital Triage & System Alerts
            </h1>
            <span className="text-[10px] font-mono font-semibold px-2 py-0.5 rounded-full bg-teal-950 border border-teal-800 text-teal-300">
              PostgreSQL
            </span>
            <LiveStatusBadge />
          </div>
          <p className="text-xs sm:text-sm text-slate-400 mt-1">
            Clinical trauma warnings, department queue thresholds, and pharmacy advisories.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={loadAlerts}
            disabled={loading}
            className="p-2 rounded-xl bg-slate-900 border border-slate-800 text-slate-300 hover:text-white hover:border-slate-700 transition cursor-pointer"
            title="Refresh alerts"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin text-teal-400" : ""}`} />
          </button>

          {/* Severity Filter Tabs */}
          <div className="flex rounded-xl bg-slate-900 border border-slate-800 p-1 text-xs">
            {["all", "critical", "moderate", "advisory"].map((sev) => (
              <button
                key={sev}
                onClick={() => setSeverityFilter(sev)}
                className={`px-3 py-1.5 rounded-lg capitalize transition cursor-pointer ${
                  severityFilter === sev
                    ? "bg-teal-600 text-white font-semibold"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                {sev}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Connection Error Banner */}
      {error && (
        <div className="p-4 rounded-2xl bg-rose-950/40 border border-rose-800/80 text-rose-200 text-xs flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center gap-2.5">
            <AlertCircle className="w-5 h-5 text-rose-400 shrink-0" />
            <div>
              <p className="font-semibold text-rose-100">Live Hospital Alerts Connection Error</p>
              <p className="text-rose-300">{error}</p>
            </div>
          </div>
          <button
            onClick={loadAlerts}
            className="px-3 py-1.5 rounded-xl bg-rose-900 hover:bg-rose-800 border border-rose-700 text-white text-xs font-medium cursor-pointer transition shrink-0"
          >
            Retry Connection
          </button>
        </div>
      )}

      {/* Toast Notice */}
      {toast && (
        <div className="p-3.5 rounded-xl bg-teal-950/80 border border-teal-800 text-teal-200 text-xs flex items-center justify-between animate-in fade-in">
          <span className="flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-teal-400" />
            {toast}
          </span>
          <button
            onClick={() => setToast(null)}
            className="text-teal-400 hover:text-white font-mono text-xs cursor-pointer"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Alerts List */}
      <div className="space-y-4">
        {loading && alerts.length === 0 ? (
          <div className="py-16 text-center space-y-3 p-8 rounded-2xl bg-slate-900/30 border border-slate-800">
            <RefreshCw className="w-8 h-8 text-teal-400 animate-spin mx-auto" />
            <h3 className="text-base font-semibold text-white">Loading live alerts...</h3>
            <p className="text-xs text-slate-400">
              Querying hospital triage and clinical telemetry storage.
            </p>
          </div>
        ) : filtered.length > 0 ? (
          filtered.map((alert) => (
            <div
              key={alert.id}
              className={`p-5 rounded-2xl border transition space-y-3 ${
                alert.priority === "critical"
                  ? "bg-rose-950/20 border-rose-800/80 text-rose-200"
                  : alert.priority === "moderate"
                  ? "bg-amber-950/20 border-amber-800/70 text-amber-200"
                  : "bg-slate-900/60 border-slate-800 text-slate-300"
              }`}
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <Badge
                    variant={
                      alert.priority === "critical"
                        ? "rose"
                        : alert.priority === "moderate"
                        ? "amber"
                        : "default"
                    }
                    size="xs"
                    dot
                  >
                    {alert.priority.toUpperCase()}
                  </Badge>
                  <span className="font-mono text-xs font-bold text-white">{alert.alert_type}</span>
                </div>
                <span className="text-xs text-slate-400 font-mono">{formatTime(alert.created_at)}</span>
              </div>

              <p className="text-sm text-slate-200 leading-relaxed font-medium">
                {alert.description}
              </p>

              <div className="flex flex-wrap items-center justify-between gap-4 pt-2 border-t border-slate-800/50 text-xs text-slate-400">
                <span className="font-mono">Location: {alert.location || "Hospital Facility"}</span>

                <div className="flex items-center gap-3">
                  {alert.acknowledged_at || alert.status === "acknowledged" ? (
                    <span className="text-emerald-400 flex items-center gap-1 font-medium">
                      <CheckCircle2 className="w-3.5 h-3.5" />
                      Acknowledged by {alert.acknowledged_by || "Staff"}
                    </span>
                  ) : (
                    <span className="text-rose-400 flex items-center gap-1 font-medium">
                      <AlertTriangle className="w-3.5 h-3.5" />
                      Awaiting Triage Review
                    </span>
                  )}

                  {!alert.acknowledged_at && alert.status !== "acknowledged" && (
                    <button
                      onClick={() => handleAcknowledge(alert.id)}
                      disabled={actionLoadingId === alert.id}
                      className="px-3 py-1 rounded-lg text-xs font-semibold bg-rose-900/80 hover:bg-rose-800 text-white border border-rose-700 transition cursor-pointer disabled:opacity-50"
                    >
                      {actionLoadingId === alert.id ? "Saving..." : "Acknowledge"}
                    </button>
                  )}
                </div>
              </div>
            </div>
          ))
        ) : (
          <div className="py-16 text-center space-y-3 p-8 rounded-2xl bg-slate-900/30 border border-slate-800">
            <Bell className="w-10 h-10 text-slate-600 mx-auto" />
            <h3 className="text-base font-semibold text-white">No alerts found</h3>
            <p className="text-xs text-slate-400">
              There are no hospital alerts matching the selected priority filter in the database.
            </p>
          </div>
        )}
      </div>
    </div>
  )
}
