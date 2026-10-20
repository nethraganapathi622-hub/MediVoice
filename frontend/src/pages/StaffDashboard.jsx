import { useState, useEffect, useCallback } from "react"
import {
  Users,
  Calendar,
  AlertTriangle,
  Search,
  CheckCircle2,
  UserCheck,
  Activity,
  RefreshCw,
  AlertCircle,
} from "lucide-react"
import StaffSidebar from "../components/layout/StaffSidebar"
import Badge from "../components/ui/Badge"
import LiveStatusBadge from "../components/ui/LiveStatusBadge"
import { useWebSocketEvent } from "../hooks/useWebSocket"
import {
  getQueue,
  callQueuePatient,
  getAlerts,
  acknowledgeAlert,
  getDoctors,
  getDepartments,
  getAuthStaff,
  loginStaff,
} from "../services/api"
import ConsultationNoteModal from "../components/staff/ConsultationNoteModal"

export default function StaffDashboard() {
  const [filterDept, setFilterDept] = useState("all")
  const [filterStatus, setFilterStatus] = useState("all")
  const [searchQuery, setSearchQuery] = useState("")

  const [queueList, setQueueList] = useState([])
  const [alertsList, setAlertsList] = useState([])
  const [doctorsList, setDoctorsList] = useState([])
  const [departmentsList, setDepartmentsList] = useState([])

  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [actionNotice, setActionNotice] = useState(null)
  const [callingId, setCallingId] = useState(null)
  const [acknowledgingId, setAcknowledgingId] = useState(null)
  const [activeEhrAppointment, setActiveEhrAppointment] = useState(null)

  const loadData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [queueData, alertsData, docsData, deptsData] = await Promise.all([
        getQueue(),
        getAlerts(),
        getDoctors(),
        getDepartments(),
      ])
      setQueueList(queueData)
      setAlertsList(alertsData)
      setDoctorsList(docsData)
      setDepartmentsList(deptsData)
    } catch (err) {
      setError(err.message || "Failed to load hospital operations data.")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    let isMounted = true
    Promise.all([
      getQueue(),
      getAlerts(),
      getDoctors(),
      getDepartments(),
    ])
      .then(([queueData, alertsData, docsData, deptsData]) => {
        if (isMounted) {
          setQueueList(queueData)
          setAlertsList(alertsData)
          setDoctorsList(docsData)
          setDepartmentsList(deptsData)
          setError(null)
        }
      })
      .catch((err) => {
        if (isMounted) setError(err.message || "Failed to load hospital operations data.")
      })
      .finally(() => {
        if (isMounted) setLoading(false)
      })
    return () => {
      isMounted = false
    }
  }, [])

  // Subscribe to real-time database-backed events
  useWebSocketEvent("queue.*", loadData)
  useWebSocketEvent("alert.*", loadData)
  useWebSocketEvent("appointment.*", loadData)
  useWebSocketEvent("reconnect", loadData)

  // Ensure staff authentication token exists for staff-scoped WebSocket channel
  useEffect(() => {
    if (!getAuthStaff()) {
      loginStaff("EMP-4091", "hospital123").catch(() => {
        // development fallback
      })
    }
  }, [])

  // Filtered queue items
  const filteredQueue = queueList.filter((item) => {
    const deptName = item.appointment?.department?.name || ""
    const matchesDept =
      filterDept === "all" ||
      deptName.toLowerCase().includes(filterDept.toLowerCase())

    const matchesStatus =
      filterStatus === "all" ||
      item.status.toLowerCase() === filterStatus.toLowerCase()

    const patName = item.appointment?.patient?.display_name || ""
    const token = item.token || ""
    const patId = item.appointment?.patient_id ? String(item.appointment.patient_id) : ""

    const matchesSearch =
      patName.toLowerCase().includes(searchQuery.toLowerCase()) ||
      token.toLowerCase().includes(searchQuery.toLowerCase()) ||
      patId.includes(searchQuery.toLowerCase())

    return matchesDept && matchesStatus && matchesSearch
  })

  const handleAcknowledgeAlert = async (alertId) => {
    setAcknowledgingId(alertId)
    try {
      const updated = await acknowledgeAlert(
        alertId,
        "STAFF-4091",
        "Nurse Supervisor Jackson",
        "TriageLead"
      )
      setAlertsList((prev) =>
        prev.map((a) => (a.id === alertId ? updated : a))
      )
      setActionNotice(`Alert #${alertId} acknowledged. Clinical staff notified.`)
      setTimeout(() => setActionNotice(null), 3500)
    } catch (err) {
      setActionNotice(`Failed to acknowledge alert: ${err.message}`)
      setTimeout(() => setActionNotice(null), 4000)
    } finally {
      setAcknowledgingId(null)
    }
  }

  const handleCallPatient = async (queueId, token, patientName) => {
    setCallingId(queueId)
    try {
      const updated = await callQueuePatient(queueId)
      setQueueList((prev) =>
        prev.map((q) => (q.id === queueId ? updated : q))
      )
      setActionNotice(`Called token ${token} (${patientName}) to Consultation Desk.`)
      setTimeout(() => setActionNotice(null), 3500)
    } catch (err) {
      setActionNotice(`Failed to call patient: ${err.message}`)
      setTimeout(() => setActionNotice(null), 4000)
    } finally {
      setCallingId(null)
    }
  }

  const formatWaitTime = (checkInTimeStr) => {
    if (!checkInTimeStr) return "--"
    const diffMs = new Date() - new Date(checkInTimeStr)
    const mins = Math.max(0, Math.floor(diffMs / 60000))
    return `${mins}m`
  }

  const formatTime = (timeStr) => {
    if (!timeStr) return "--:--"
    const d = new Date(timeStr)
    return isNaN(d) ? timeStr : d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
  }

  // Calculate live summary stats
  const activeAlertsCount = alertsList.filter((a) => a.status === "active" && !a.acknowledged_at).length
  const waitingCount = queueList.filter((q) => q.status === "waiting").length
  const activeDoctorsCount = doctorsList.filter((d) => d.is_active).length

  return (
    <div className="flex min-h-[calc(100vh-4rem)]">
      {/* Staff Sidebar */}
      <StaffSidebar />

      {/* Main Staff Dashboard Content */}
      <div className="flex-1 p-4 sm:p-8 space-y-8 bg-slate-950 overflow-x-hidden">
        {/* Header with Title, Profile & Mode Notice */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800 pb-6">
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
                Hospital Command Center
              </h1>
              <span className="text-[10px] font-mono font-semibold px-2 py-0.5 rounded-full bg-teal-950 border border-teal-800 text-teal-300">
                PostgreSQL Live API
              </span>
            </div>
            <p className="text-xs text-slate-400 mt-1">
              Live patient queue coordination, doctor duty rosters, and department triage telemetry.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <LiveStatusBadge />
            <button
              onClick={loadData}
              disabled={loading}
              className="p-2 rounded-xl bg-slate-900 border border-slate-800 text-slate-300 hover:text-white hover:border-slate-700 transition cursor-pointer"
              title="Refresh Live Data"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin text-teal-400" : ""}`} />
            </button>
            <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-xl bg-slate-900 border border-slate-800 text-xs text-slate-300">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
              <span>Shift: General Morning (08:00 - 16:00)</span>
            </div>
            <div className="px-3 py-1.5 rounded-xl bg-slate-900 border border-slate-800 text-xs font-mono text-cyan-300">
              Terminal: OP-RECEPT-04
            </div>
          </div>
        </div>

        {/* Action Notice Toast */}
        {actionNotice && (
          <div className="p-3 rounded-xl bg-teal-950/80 border border-teal-800 text-teal-200 text-xs flex items-center justify-between animate-in fade-in">
            <span className="flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-teal-400" />
              {actionNotice}
            </span>
            <button
              onClick={() => setActionNotice(null)}
              className="text-teal-400 hover:text-white text-xs cursor-pointer"
            >
              Dismiss
            </button>
          </div>
        )}

        {/* Connection Error Banner */}
        {error && (
          <div className="p-4 rounded-2xl bg-rose-950/40 border border-rose-800/80 text-rose-200 text-xs flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div className="flex items-center gap-2.5">
              <AlertCircle className="w-5 h-5 text-rose-400 shrink-0" />
              <div>
                <p className="font-semibold text-rose-100">Live Hospital Database Error</p>
                <p className="text-rose-300">{error}</p>
              </div>
            </div>
            <button
              onClick={loadData}
              className="px-3 py-1.5 rounded-xl bg-rose-900 hover:bg-rose-800 border border-rose-700 text-white text-xs font-medium cursor-pointer transition shrink-0"
            >
              Retry Connection
            </button>
          </div>
        )}

        {/* Top KPI Metric Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {/* KPI 1: Queue Total */}
          <div className="p-5 rounded-2xl bg-slate-900/60 border border-slate-800 space-y-2">
            <div className="flex items-center justify-between text-slate-400">
              <span className="text-xs font-medium">Active Queue Tokens</span>
              <Calendar className="w-4 h-4 text-teal-400" />
            </div>
            <div className="flex items-baseline gap-2">
              <span className="text-2xl font-bold text-white">{queueList.length}</span>
              <span className="text-xs text-emerald-400 font-mono">Live registered</span>
            </div>
            <div className="text-[11px] text-slate-400 flex items-center justify-between pt-1 border-t border-slate-800/80">
              <span>{queueList.filter((q) => q.status === "completed").length} Completed</span>
              <span>{queueList.filter((q) => q.status !== "completed").length} Active</span>
            </div>
          </div>

          {/* KPI 2: Waiting Patients */}
          <div className="p-5 rounded-2xl bg-slate-900/60 border border-slate-800 space-y-2">
            <div className="flex items-center justify-between text-slate-400">
              <span className="text-xs font-medium">Waiting Queue</span>
              <Users className="w-4 h-4 text-cyan-400" />
            </div>
            <div className="flex items-baseline gap-2">
              <span className="text-2xl font-bold text-white">{waitingCount}</span>
              <span className="text-xs text-slate-400 font-mono">in triage & lounge</span>
            </div>
            <div className="text-[11px] text-slate-400 flex items-center justify-between pt-1 border-t border-slate-800/80">
              <span>Status: Synchronized</span>
              <span className="text-teal-400">Target &lt;20m</span>
            </div>
          </div>

          {/* KPI 3: Available Doctors */}
          <div className="p-5 rounded-2xl bg-slate-900/60 border border-slate-800 space-y-2">
            <div className="flex items-center justify-between text-slate-400">
              <span className="text-xs font-medium">Specialists On Duty</span>
              <UserCheck className="w-4 h-4 text-emerald-400" />
            </div>
            <div className="flex items-baseline gap-2">
              <span className="text-2xl font-bold text-white">{activeDoctorsCount}</span>
              <span className="text-xs text-slate-400 font-mono">of {doctorsList.length} active</span>
            </div>
            <div className="text-[11px] text-slate-400 flex items-center justify-between pt-1 border-t border-slate-800/80">
              <span>All OPD Wings</span>
              <span className="text-emerald-400">{departmentsList.length} Departments</span>
            </div>
          </div>

          {/* KPI 4: Pending Urgent Alerts */}
          <div className="p-5 rounded-2xl bg-slate-900/60 border border-slate-800 space-y-2">
            <div className="flex items-center justify-between text-slate-400">
              <span className="text-xs font-medium">Active Alerts</span>
              <AlertTriangle className="w-4 h-4 text-rose-400" />
            </div>
            <div className="flex items-baseline gap-2">
              <span className="text-2xl font-bold text-rose-400">
                {activeAlertsCount}
              </span>
              <span className="text-xs text-slate-400 font-mono">unacknowledged</span>
            </div>
            <div className="text-[11px] text-slate-400 flex items-center justify-between pt-1 border-t border-slate-800/80">
              <span className="text-rose-400 font-semibold">Triage Priority</span>
              <span>{alertsList.length} Total</span>
            </div>
          </div>
        </div>

        {/* Patient Queue Coordination Table */}
        <section id="queue" className="space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div>
              <h2 className="text-lg font-bold text-white tracking-tight flex items-center gap-2">
                <Activity className="w-5 h-5 text-teal-400" />
                Live Patient Intake Queue
              </h2>
              <p className="text-xs text-slate-400 mt-0.5">
                Real-time outpatient tokens, triage assignment, and room call status.
              </p>
            </div>

            {/* Filter and Search Bar */}
            <div className="flex flex-wrap items-center gap-2">
              <div className="relative">
                <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
                <input
                  type="text"
                  placeholder="Search token or patient..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-8 pr-3 py-1.5 rounded-xl bg-slate-900 border border-slate-800 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-teal-500 w-44 sm:w-56"
                />
              </div>

              <select
                value={filterDept}
                onChange={(e) => setFilterDept(e.target.value)}
                className="px-2.5 py-1.5 rounded-xl bg-slate-900 border border-slate-800 text-xs text-slate-300 focus:outline-none focus:border-teal-500 cursor-pointer"
              >
                <option value="all">All Departments</option>
                {departmentsList.map((d) => (
                  <option key={d.id} value={d.name}>
                    {d.name}
                  </option>
                ))}
              </select>

              <select
                value={filterStatus}
                onChange={(e) => setFilterStatus(e.target.value)}
                className="px-2.5 py-1.5 rounded-xl bg-slate-900 border border-slate-800 text-xs text-slate-300 focus:outline-none focus:border-teal-500 cursor-pointer"
              >
                <option value="all">All Statuses</option>
                <option value="waiting">Waiting</option>
                <option value="called">Called</option>
                <option value="in_consultation">In Consultation</option>
                <option value="completed">Completed</option>
              </select>
            </div>
          </div>

          {/* Table Container */}
          <div className="rounded-2xl border border-slate-800 bg-slate-900/40 overflow-hidden shadow-xl">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-900/90 text-slate-400 border-b border-slate-800 uppercase font-mono text-[10px] tracking-wider">
                  <tr>
                    <th className="py-3 px-4">Token</th>
                    <th className="py-3 px-4">Patient Identifier</th>
                    <th className="py-3 px-4">Department & Doctor</th>
                    <th className="py-3 px-4">Check-In</th>
                    <th className="py-3 px-4">Wait Time</th>
                    <th className="py-3 px-4">Triage Priority</th>
                    <th className="py-3 px-4">Status</th>
                    <th className="py-3 px-4 text-right">Coordination</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60 text-slate-300">
                  {loading && queueList.length === 0 ? (
                    <tr>
                      <td colSpan="8" className="py-12 text-center text-slate-400">
                        <RefreshCw className="w-5 h-5 animate-spin mx-auto text-teal-400 mb-2" />
                        Loading live queue from PostgreSQL database...
                      </td>
                    </tr>
                  ) : filteredQueue.length > 0 ? (
                    filteredQueue.map((item) => {
                      const patientName = item.appointment?.patient?.display_name || "Outpatient"
                      const patientContact = item.appointment?.patient?.phone || `Appt #${item.appointment?.booking_reference || item.appointment_id}`
                      const deptName = item.appointment?.department?.name || "General OPD"
                      const doctorName = item.appointment?.doctor?.name || "Specialist"

                      return (
                        <tr key={item.id} className="hover:bg-slate-800/40 transition">
                          <td className="py-3.5 px-4 font-mono font-bold text-teal-300">
                            {item.token}
                          </td>
                          <td className="py-3.5 px-4 font-medium text-white">
                            <div>{patientName}</div>
                            <span className="text-[10px] font-mono text-slate-500">
                              {patientContact}
                            </span>
                          </td>
                          <td className="py-3.5 px-4">
                            <div className="font-medium text-slate-200">{deptName}</div>
                            <div className="text-[11px] text-slate-400">{doctorName}</div>
                          </td>
                          <td className="py-3.5 px-4 font-mono text-slate-400">
                            {formatTime(item.check_in_time)}
                          </td>
                          <td className="py-3.5 px-4 font-mono text-slate-300">
                            {formatWaitTime(item.check_in_time)}
                          </td>
                          <td className="py-3.5 px-4">
                            <Badge
                              variant={
                                item.priority === "emergency"
                                  ? "rose"
                                  : item.priority === "urgent"
                                  ? "amber"
                                  : "default"
                              }
                              size="xs"
                            >
                              {item.priority}
                            </Badge>
                          </td>
                          <td className="py-3.5 px-4">
                            <Badge
                              variant={
                                item.status === "in_consultation"
                                  ? "teal"
                                  : item.status === "called"
                                  ? "amber"
                                  : item.status === "completed"
                                  ? "emerald"
                                  : "default"
                              }
                              size="sm"
                              dot
                            >
                              {item.status.replace("_", " ")}
                            </Badge>
                          </td>
                          <td className="py-3.5 px-4 text-right">
                            <div className="flex items-center justify-end gap-1.5">
                              {item.status !== "completed" && (
                                <button
                                  onClick={() => handleCallPatient(item.id, item.token, patientName)}
                                  disabled={callingId === item.id}
                                  className="px-2.5 py-1 rounded-lg bg-teal-950 hover:bg-teal-900 border border-teal-800 text-teal-300 hover:text-white transition font-medium cursor-pointer disabled:opacity-50 text-xs"
                                >
                                  {callingId === item.id ? "Calling..." : "Call Next"}
                                </button>
                              )}
                              {item.appointment && (
                                <button
                                  onClick={() => setActiveEhrAppointment(item.appointment)}
                                  className="px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-200 hover:text-white transition font-medium cursor-pointer text-xs flex items-center gap-1"
                                  title="Record or view clinical EHR consultation notes"
                                >
                                  <span>{item.status === "completed" ? "View EHR" : "EHR Note"}</span>
                                </button>
                              )}
                            </div>
                          </td>
                        </tr>
                      )
                    })
                  ) : (
                    <tr>
                      <td colSpan="8" className="py-8 text-center text-slate-500">
                        No active queue patients found matching the selected filter criteria.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </section>

        {/* Lower Grid: Urgent Alerts Panel & Doctor Availability Section */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Urgent Alerts Panel */}
          <div className="p-5 rounded-2xl bg-slate-900/50 border border-slate-800 space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 text-rose-400" />
                <h3 className="font-bold text-white text-sm tracking-tight">
                  Triage & Operational Alerts
                </h3>
              </div>
              <span className="text-[10px] font-mono text-slate-400">
                PostgreSQL Alert Store
              </span>
            </div>

            <div className="space-y-3">
              {alertsList.length > 0 ? (
                alertsList.map((alert) => (
                  <div
                    key={alert.id}
                    className={`p-3.5 rounded-xl border transition space-y-2 ${
                      alert.priority === "critical"
                        ? "bg-rose-950/30 border-rose-800/80 text-rose-200"
                        : alert.priority === "moderate"
                        ? "bg-amber-950/20 border-amber-800/60 text-amber-200"
                        : "bg-slate-900 border-slate-800 text-slate-300"
                    }`}
                  >
                    <div className="flex items-center justify-between text-xs">
                      <span className="font-mono font-bold">{alert.alert_type}</span>
                      <span className="text-[10px] opacity-75">{formatTime(alert.created_at)}</span>
                    </div>
                    <p className="text-xs leading-relaxed">{alert.description}</p>
                    <div className="flex items-center justify-between pt-1 border-t border-slate-800/50 text-[11px]">
                      <span className="opacity-80">{alert.location || "Hospital Facility"}</span>
                      {alert.acknowledged_at || alert.status === "acknowledged" ? (
                        <span className="text-emerald-400 font-mono flex items-center gap-1">
                          <CheckCircle2 className="w-3 h-3" /> Acknowledged ({alert.acknowledged_by || "Staff"})
                        </span>
                      ) : (
                        <button
                          onClick={() => handleAcknowledgeAlert(alert.id)}
                          disabled={acknowledgingId === alert.id}
                          className="px-2 py-0.5 rounded bg-rose-900/80 hover:bg-rose-800 text-rose-200 border border-rose-700 text-[10px] font-semibold cursor-pointer transition disabled:opacity-50"
                        >
                          {acknowledgingId === alert.id ? "Saving..." : "Acknowledge"}
                        </button>
                      )}
                    </div>
                  </div>
                ))
              ) : (
                <div className="py-6 text-center text-slate-500 text-xs">
                  No active triage alerts registered in database.
                </div>
              )}
            </div>
          </div>

          {/* Doctor Availability Section */}
          <div className="p-5 rounded-2xl bg-slate-900/50 border border-slate-800 space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <UserCheck className="w-4 h-4 text-teal-400" />
                <h3 className="font-bold text-white text-sm tracking-tight">
                  Specialist Roster & Room Status
                </h3>
              </div>
              <span className="text-[10px] font-mono text-slate-400">
                Wing OPD Allocation
              </span>
            </div>

            <div className="space-y-2.5">
              {doctorsList.slice(0, 5).map((doc) => (
                <div
                  key={doc.id}
                  className="p-3 rounded-xl bg-slate-950 border border-slate-800 flex items-center justify-between gap-3 text-xs"
                >
                  <div className="space-y-0.5">
                    <div className="font-semibold text-white">{doc.name}</div>
                    <div className="text-[11px] text-slate-400">
                      {doc.department?.name || doc.specialty} • <span className="text-teal-400">Room {doc.room_number}</span>
                    </div>
                  </div>

                  <Badge
                    variant={doc.is_active ? "emerald" : "amber"}
                    size="sm"
                    dot
                  >
                    {doc.is_active ? "On Duty" : "Off Duty"}
                  </Badge>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* EHR Clinical Consultation Note Modal */}
      {activeEhrAppointment && (
        <ConsultationNoteModal
          appointment={activeEhrAppointment}
          onClose={() => setActiveEhrAppointment(null)}
          onSaved={() => {
            setActionNotice("Consultation record and digital prescriptions successfully saved.")
            loadData()
          }}
        />
      )}
    </div>
  )
}
