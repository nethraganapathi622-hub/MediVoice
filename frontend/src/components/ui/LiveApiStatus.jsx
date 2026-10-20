import { useState, useEffect } from "react"
import { Activity, Database, CheckCircle2, AlertCircle, RefreshCw, X } from "lucide-react"

export default function LiveApiStatus({ className = "" }) {
  const [open, setOpen] = useState(false)
  const [health, setHealth] = useState(null)
  const [readiness, setReadiness] = useState(null)
  const [checking, setChecking] = useState(false)
  const [apiOnline, setApiOnline] = useState(false)

  const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000"

  const runProbes = async () => {
    setChecking(true)
    try {
      const hRes = await fetch(`${apiBaseUrl}/api/health`, { method: "GET" })
      if (hRes.ok) {
        const hData = await hRes.json()
        setHealth(hData)
        setApiOnline(true)
      } else {
        setHealth({ status: "error", code: hRes.status })
        setApiOnline(false)
      }
    } catch (err) {
      setHealth({ status: "offline", error: err.message })
      setApiOnline(false)
    }

    try {
      const rRes = await fetch(`${apiBaseUrl}/api/health/ready`, { method: "GET" })
      const rData = await rRes.json()
      setReadiness({ status: rRes.status, data: rData })
    } catch (err) {
      setReadiness({ status: 503, error: err.message })
    } finally {
      setChecking(false)
    }
  }

  useEffect(() => {
    let mounted = true
    const checkOnMount = async () => {
      try {
        const hRes = await fetch(`${apiBaseUrl}/api/health`)
        if (!mounted) return
        if (hRes.ok) {
          const hData = await hRes.json()
          setHealth(hData)
          setApiOnline(true)
        } else {
          setHealth({ status: "error", code: hRes.status })
          setApiOnline(false)
        }
      } catch (err) {
        if (!mounted) return
        setHealth({ status: "offline", error: err.message })
        setApiOnline(false)
      }

      try {
        const rRes = await fetch(`${apiBaseUrl}/api/health/ready`)
        if (!mounted) return
        const rData = await rRes.json()
        setReadiness({ status: rRes.status, data: rData })
      } catch (err) {
        if (!mounted) return
        setReadiness({ status: 503, error: err.message })
      }
    }

    checkOnMount()
    return () => {
      mounted = false
    }
  }, [apiBaseUrl])

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className={`inline-flex items-center gap-2 px-2.5 py-1 rounded-full text-xs font-mono transition border ${
          apiOnline
            ? "bg-teal-950/60 border-teal-800 text-teal-300 hover:bg-teal-900/80"
            : "bg-slate-900/80 border-slate-800 text-slate-400 hover:bg-slate-800"
        } ${className}`}
        title="Check Backend Health & DB Readiness"
      >
        <span
          className={`w-2 h-2 rounded-full ${
            apiOnline ? "bg-emerald-400 animate-pulse" : "bg-amber-400"
          }`}
        />
        <span>{apiOnline ? "Backend Connected" : "Local UI Mode"}</span>
      </button>

      {open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs">
          <div className="w-full max-w-md bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-2xl space-y-4 animate-in fade-in zoom-in-95">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2 text-white font-semibold">
                <Activity className="w-5 h-5 text-teal-400" />
                <span>Backend Engineering Probes</span>
              </div>
              <button
                onClick={() => setOpen(false)}
                className="text-slate-400 hover:text-white p-1 rounded-lg hover:bg-slate-800 transition"
                aria-label="Close"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="space-y-3 text-xs">
              {/* Liveness Probe */}
              <div className="p-3 rounded-xl bg-slate-950 border border-slate-800/80 space-y-1">
                <div className="flex items-center justify-between font-mono text-slate-400">
                  <span className="flex items-center gap-1.5">
                    <Activity className="w-3.5 h-3.5 text-cyan-400" />
                    GET /api/health
                  </span>
                  {health && health.status === "healthy" ? (
                    <span className="text-emerald-400 flex items-center gap-1">
                      <CheckCircle2 className="w-3 h-3" /> 200 OK
                    </span>
                  ) : (
                    <span className="text-amber-400 flex items-center gap-1">
                      <AlertCircle className="w-3 h-3" /> Offline / Standalone
                    </span>
                  )}
                </div>
                <pre className="text-[11px] text-slate-300 font-mono mt-1 overflow-x-auto">
                  {JSON.stringify(health || { note: "Not reachable or server offline" }, null, 2)}
                </pre>
              </div>

              {/* Readiness Probe */}
              <div className="p-3 rounded-xl bg-slate-950 border border-slate-800/80 space-y-1">
                <div className="flex items-center justify-between font-mono text-slate-400">
                  <span className="flex items-center gap-1.5">
                    <Database className="w-3.5 h-3.5 text-teal-400" />
                    GET /api/health/ready
                  </span>
                  {readiness && readiness.status === 200 ? (
                    <span className="text-emerald-400 flex items-center gap-1">
                      <CheckCircle2 className="w-3 h-3" /> 200 Ready
                    </span>
                  ) : (
                    <span className="text-amber-400 flex items-center gap-1">
                      <AlertCircle className="w-3 h-3" /> 503 (No Live DB)
                    </span>
                  )}
                </div>
                <pre className="text-[11px] text-slate-300 font-mono mt-1 overflow-x-auto">
                  {JSON.stringify(
                    readiness?.data || {
                      status: "not_ready",
                      database: { status: "disconnected", details: "Local PostgreSQL not started" },
                    },
                    null,
                    2
                  )}
                </pre>
              </div>

              <p className="text-[11px] text-slate-400 leading-relaxed">
                Probe targets live FastAPI server at <code className="text-teal-300">{apiBaseUrl}</code>.
                When the Python backend is running with a live PostgreSQL instance, readiness returns 200.
              </p>
            </div>

            <div className="flex justify-between items-center pt-2">
              <button
                onClick={runProbes}
                disabled={checking}
                className="inline-flex items-center gap-1.5 text-xs text-teal-400 hover:text-teal-300 font-medium cursor-pointer"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${checking ? "animate-spin" : ""}`} />
                Re-check Probes
              </button>
              <button
                onClick={() => setOpen(false)}
                className="px-4 py-1.5 text-xs font-semibold rounded-lg bg-slate-800 hover:bg-slate-700 text-white transition cursor-pointer"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
