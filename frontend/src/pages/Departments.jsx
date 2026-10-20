import { useState, useEffect, useCallback } from "react"
import { Search, MapPin, Clock, Building2, RefreshCw, AlertCircle } from "lucide-react"
import LiveStatusBadge from "../components/ui/LiveStatusBadge"
import { useWebSocketEvent } from "../hooks/useWebSocket"
import { getDepartments } from "../services/api"

export default function Departments() {
  const [departments, setDepartments] = useState([])
  const [search, setSearch] = useState("")
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const loadDepartments = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await getDepartments({ search })
      setDepartments(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [search])

  useEffect(() => {
    const timer = setTimeout(() => {
      loadDepartments()
    }, 250)
    return () => clearTimeout(timer)
  }, [loadDepartments])

  useWebSocketEvent("reconnect", loadDepartments)

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10 space-y-8">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800 pb-6">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl sm:text-4xl font-extrabold text-white tracking-tight">
              Hospital Departments & Wings
            </h1>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-teal-950 border border-teal-800 text-teal-300">
              Live Database
            </span>
            <LiveStatusBadge />
          </div>
          <p className="text-xs sm:text-sm text-slate-400 mt-1">
            Locate specialized clinical units, diagnostic imaging labs, waiting lounges, and extension desks.
          </p>
        </div>

        {/* Search */}
        <div className="relative">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Search departments or wings..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9 pr-4 py-2 rounded-xl bg-slate-900 border border-slate-800 text-xs sm:text-sm text-white placeholder-slate-500 focus:outline-none focus:border-teal-500 w-64 sm:w-80"
          />
        </div>
      </div>

      {/* Error State */}
      {error && (
        <div className="p-4 rounded-2xl bg-rose-950/40 border border-rose-800/80 text-rose-300 text-xs flex flex-col sm:flex-row sm:items-center justify-between gap-3 animate-in fade-in">
          <div className="flex items-center gap-2">
            <AlertCircle className="w-4 h-4 text-rose-400 shrink-0" />
            <span>{error}</span>
          </div>
          <button
            onClick={loadDepartments}
            className="px-3 py-1.5 rounded-lg bg-rose-900/80 hover:bg-rose-800 text-rose-100 font-medium transition cursor-pointer flex items-center justify-center gap-1.5 shrink-0"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            <span>Retry Connection</span>
          </button>
        </div>
      )}

      {/* Loading Skeleton */}
      {loading && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="p-6 rounded-2xl bg-slate-900/40 border border-slate-800 space-y-4 animate-pulse">
              <div className="h-6 w-1/3 bg-slate-800 rounded"></div>
              <div className="h-4 w-full bg-slate-800/60 rounded"></div>
              <div className="h-4 w-2/3 bg-slate-800/60 rounded"></div>
            </div>
          ))}
        </div>
      )}

      {/* Departments Grid */}
      {!loading && !error && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {departments.length > 0 ? (
            departments.map((dept) => (
              <div
                key={dept.id}
                className="p-6 rounded-2xl bg-slate-900/60 border border-slate-800 hover:border-slate-700 transition space-y-4 flex flex-col justify-between"
              >
                <div className="space-y-3">
                  {/* Title & Code */}
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2.5">
                      <span className="w-9 h-9 rounded-xl bg-teal-950 border border-teal-800 text-teal-400 font-mono font-bold text-xs flex items-center justify-center">
                        {dept.code}
                      </span>
                      <h3 className="font-bold text-white text-lg tracking-tight">
                        {dept.name}
                      </h3>
                    </div>

                    <span className="text-xs text-slate-400 flex items-center gap-1 font-mono">
                      <Clock className="w-3.5 h-3.5 text-teal-400" />
                      Floor: {dept.floor}
                    </span>
                  </div>

                  <p className="text-xs text-slate-300 leading-relaxed">
                    {dept.description || "General hospital outpatient service and consultation wing."}
                  </p>
                </div>

                {/* Footer Specs: Location & Extension */}
                <div className="pt-4 border-t border-slate-800/80 flex items-center justify-between text-xs text-slate-400">
                  <span className="flex items-center gap-1.5 text-slate-300">
                    <MapPin className="w-3.5 h-3.5 text-teal-400" />
                    {dept.location}
                  </span>
                  <span className="font-mono text-teal-400">{dept.extension || "Ext. Main"}</span>
                </div>
              </div>
            ))
          ) : (
            <div className="col-span-full py-16 text-center space-y-3 p-8 rounded-2xl bg-slate-900/30 border border-slate-800">
              <Building2 className="w-10 h-10 text-slate-600 mx-auto" />
              <h3 className="text-base font-semibold text-white">No departments found</h3>
              <p className="text-xs text-slate-400">
                Try searching with another clinical term or wing name.
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
