import { Link, useLocation } from "react-router-dom"
import {
  LayoutDashboard,
  Users,
  Calendar,
  Building2,
  Bell,
  ArrowLeft,
  Activity,
} from "lucide-react"

export default function StaffSidebar() {
  const location = useLocation()

  const links = [
    { name: "Command Center", path: "/staff", icon: LayoutDashboard },
    { name: "Patient Queue & Triage", path: "/staff#queue", icon: Activity },
    { name: "Doctor Availability", path: "/doctors", icon: Users },
    { name: "Daily Appointments", path: "/appointments", icon: Calendar },
    { name: "Hospital Departments", path: "/departments", icon: Building2 },
    { name: "Urgent Alerts", path: "/alerts", icon: Bell },
  ]

  const isActive = (path) => {
    if (path === "/staff" && location.pathname === "/staff") return true
    if (path !== "/staff" && location.pathname === path) return true
    return false
  }

  return (
    <aside className="w-64 shrink-0 bg-slate-950 border-r border-slate-800/80 flex flex-col justify-between hidden md:flex min-h-[calc(100vh-4rem)]">
      <div className="p-4 space-y-6">
        {/* Portal Identifier */}
        <div className="px-2 py-3 rounded-xl bg-slate-900 border border-slate-800 space-y-1">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse" />
            <span className="text-xs font-semibold uppercase tracking-wider text-cyan-400 font-mono">
              Staff Portal
            </span>
          </div>
          <p className="text-[11px] text-slate-400">
            Hospital Triage & Command Center
          </p>
        </div>

        {/* Navigation */}
        <nav className="space-y-1">
          {links.map((link) => {
            const Icon = link.icon
            const active = isActive(link.path)
            return (
              <Link
                key={link.name}
                to={link.path}
                className={`flex items-center gap-3 px-3 py-2.5 rounded-xl text-xs font-medium transition ${
                  active
                    ? "bg-cyan-950/70 border border-cyan-800/80 text-cyan-300 font-semibold"
                    : "text-slate-400 hover:text-white hover:bg-slate-900"
                }`}
              >
                <Icon className={`w-4 h-4 ${active ? "text-cyan-400" : "text-slate-500"}`} />
                <span>{link.name}</span>
              </Link>
            )
          })}
        </nav>
      </div>

      {/* Staff Profile Placeholder & Switch to Patient Assistant */}
      <div className="p-4 border-t border-slate-800/80 space-y-3">
        <div className="flex items-center gap-3 px-2 py-2 rounded-xl bg-slate-900/50 border border-slate-800">
          <div className="w-8 h-8 rounded-full bg-teal-800 flex items-center justify-center text-teal-200 text-xs font-bold">
            RN
          </div>
          <div className="flex flex-col text-xs leading-tight">
            <span className="font-semibold text-slate-200">Radha Nair, RN</span>
            <span className="text-[10px] text-slate-400 font-mono">Chief Triage Officer</span>
          </div>
        </div>

        <Link
          to="/"
          className="flex items-center justify-center gap-2 w-full py-2 px-3 rounded-xl text-xs font-medium text-slate-300 bg-slate-900 hover:bg-slate-800 hover:text-white border border-slate-700 transition"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          <span>Patient Assistant</span>
        </Link>
      </div>
    </aside>
  )
}
