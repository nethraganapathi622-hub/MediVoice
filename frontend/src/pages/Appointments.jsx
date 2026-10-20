import { useState, useEffect, useCallback } from "react"
import {
  Calendar,
  Search,
  Clock,
  MapPin,
  CheckCircle2,
  FileText,
  RefreshCw,
  AlertCircle,
  X,
  Phone,
  ShieldCheck,
  QrCode,
  LogOut,
  Sparkles,
  User,
  ArrowRight,
  KeyRound,
} from "lucide-react"
import Badge from "../components/ui/Badge"
import LiveStatusBadge from "../components/ui/LiveStatusBadge"
import { useWebSocketEvent } from "../hooks/useWebSocket"
import {
  getAppointments,
  cancelAppointment,
  rescheduleAppointment,
  queueCheckIn,
  getAuthPatient,
  clearAuthPatient,
  requestPatientOtp,
  verifyPatientOtp,
  getVerifiedPatientAppointments,
  lookupPatientAppointment,
  patientSelfReschedule,
  patientSelfCancel,
  patientSelfCheckIn,
} from "../services/api"

export default function Appointments() {
  const [activeTab, setActiveTab] = useState("my_passes") // 'my_passes', 'lookup', 'all'
  const [patientAuth, setPatientAuth] = useState(getAuthPatient())

  // OTP login state
  const [phoneInput, setPhoneInput] = useState("")
  const [otpInput, setOtpInput] = useState("")
  const [otpSent, setOtpSent] = useState(false)
  const [otpLoading, setOtpLoading] = useState(false)
  const [otpNotice, setOtpNotice] = useState(null)
  const [otpError, setOtpError] = useState(null)

  // Single Lookup State
  const [lookupRef, setLookupRef] = useState("")
  const [lookupPhone, setLookupPhone] = useState("")
  const [lookupResult, setLookupResult] = useState(null)
  const [lookupLoading, setLookupLoading] = useState(false)
  const [lookupError, setLookupError] = useState(null)

  // Appointments List State
  const [appointments, setAppointments] = useState([])
  const [statusFilter, setStatusFilter] = useState("all")
  const [search, setSearch] = useState("")
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [notice, setNotice] = useState(null)

  // Reschedule Modal State
  const [rescheduleApt, setRescheduleApt] = useState(null)
  const [rescheduleDate, setRescheduleDate] = useState("")
  const [rescheduleTime, setRescheduleTime] = useState("10:00")
  const [rescheduleLoading, setRescheduleLoading] = useState(false)
  const [rescheduleError, setRescheduleError] = useState(null)

  const loadAppointments = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      if (activeTab === "my_passes") {
        if (patientAuth?.access_token) {
          const data = await getVerifiedPatientAppointments()
          setAppointments(data)
        } else {
          setAppointments([])
        }
      } else if (activeTab === "all") {
        const data = await getAppointments({
          status: statusFilter,
          search: search || undefined,
        })
        setAppointments(data)
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [activeTab, patientAuth, statusFilter, search])

  useEffect(() => {
    const timer = setTimeout(() => {
      loadAppointments()
    }, 200)
    return () => clearTimeout(timer)
  }, [loadAppointments])

  // Real-time synchronization
  useWebSocketEvent("appointment.*", loadAppointments)
  useWebSocketEvent("queue.*", loadAppointments)
  useWebSocketEvent("reconnect", loadAppointments)

  // Request OTP handler
  const handleRequestOtp = async (e) => {
    e.preventDefault()
    if (!phoneInput.trim() || phoneInput.length < 8) {
      setOtpError("Please enter a valid mobile number with country code.")
      return
    }
    setOtpLoading(true)
    setOtpError(null)
    try {
      const res = await requestPatientOtp(phoneInput.trim())
      setOtpSent(true)
      setOtpInput(res.demo_otp || "123456")
      setOtpNotice(res.message || `Code sent to ${phoneInput}`)
    } catch (err) {
      setOtpError(err.message || "Failed to send verification code.")
    } finally {
      setOtpLoading(false)
    }
  }

  // Verify OTP handler
  const handleVerifyOtp = async (e) => {
    e.preventDefault()
    if (!otpInput.trim()) {
      setOtpError("Please enter the verification code.")
      return
    }
    setOtpLoading(true)
    setOtpError(null)
    try {
      const authData = await verifyPatientOtp(phoneInput.trim(), otpInput.trim())
      setPatientAuth(authData)
      setOtpSent(false)
      setNotice(`Welcome, ${authData.display_name}! Your consultation passes have loaded.`)
      setTimeout(() => setNotice(null), 4000)
    } catch (err) {
      setOtpError(err.message || "Invalid verification code.")
    } finally {
      setOtpLoading(false)
    }
  }

  const handleLogoutPatient = () => {
    clearAuthPatient()
    setPatientAuth(null)
    setAppointments([])
    setNotice("Signed out of patient session.")
    setTimeout(() => setNotice(null), 3000)
  }

  // Single Lookup Handler
  const handleLookupSubmit = async (e) => {
    e.preventDefault()
    if (!lookupRef.trim() || !lookupPhone.trim()) {
      setLookupError("Please enter both the booking reference and patient phone number.")
      return
    }
    setLookupLoading(true)
    setLookupError(null)
    setLookupResult(null)
    try {
      const pass = await lookupPatientAppointment(lookupRef.trim(), lookupPhone.trim())
      setLookupResult(pass)
    } catch (err) {
      setLookupError(err.message || "Appointment not found or phone number does not match.")
    } finally {
      setLookupLoading(false)
    }
  }

  // Self-Cancel Handler
  const handleCancel = async (aptId) => {
    try {
      let updated
      if (patientAuth?.access_token) {
        updated = await patientSelfCancel(aptId, "Cancelled from patient self-service portal")
      } else {
        updated = await cancelAppointment(aptId, "Cancelled from patient consultation portal")
      }
      setAppointments((prev) => prev.map((a) => (a.id === aptId ? updated : a)))
      if (lookupResult && lookupResult.id === aptId) {
        setLookupResult(updated)
      }
      setNotice(`Appointment ${updated.booking_reference} successfully cancelled and slot freed.`)
      setTimeout(() => setNotice(null), 4000)
    } catch (err) {
      setError(`Failed to cancel appointment: ${err.message}`)
    }
  }

  // Self-CheckIn Handler
  const handleCheckIn = async (apt) => {
    try {
      let qEntry
      if (patientAuth?.access_token) {
        qEntry = await patientSelfCheckIn(apt.id)
      } else {
        qEntry = await queueCheckIn({ appointment_id: apt.id })
      }
      setNotice(`Checked in! Queue token ${qEntry.token} issued for today's OPD consultation.`)
      loadAppointments()
      if (lookupResult && lookupResult.id === apt.id) {
        setLookupResult({ ...lookupResult, queue_token: qEntry.token, status: "checked-in" })
      }
      setTimeout(() => setNotice(null), 4000)
    } catch (err) {
      setError(`Check-in failed: ${err.message}`)
    }
  }

  // Reschedule Submit Handler
  const handleRescheduleSubmit = async (e) => {
    e.preventDefault()
    if (!rescheduleDate || !rescheduleTime) {
      setRescheduleError("Please specify a valid date and start time.")
      return
    }

    setRescheduleLoading(true)
    setRescheduleError(null)
    try {
      let updated
      if (patientAuth?.access_token) {
        updated = await patientSelfReschedule(
          rescheduleApt.id,
          rescheduleDate,
          rescheduleTime + ":00"
        )
      } else {
        updated = await rescheduleAppointment(
          rescheduleApt.id,
          rescheduleDate,
          rescheduleTime + ":00"
        )
      }
      setAppointments((prev) => prev.map((a) => (a.id === updated.id ? updated : a)))
      if (lookupResult && lookupResult.id === updated.id) {
        setLookupResult(updated)
      }
      setNotice(
        `Appointment ${updated.booking_reference} successfully rescheduled to ${updated.appointment_date} at ${updated.start_time}.`
      )
      setRescheduleApt(null)
      setTimeout(() => setNotice(null), 4000)
    } catch (err) {
      setRescheduleError(err.message)
    } finally {
      setRescheduleLoading(false)
    }
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10 space-y-8">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800 pb-6">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl sm:text-4xl font-extrabold text-white tracking-tight">
              Patient Consultations & Digital Passes
            </h1>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-teal-950 border border-teal-800 text-teal-300">
              Live Database
            </span>
            <LiveStatusBadge />
          </div>
          <p className="text-xs sm:text-sm text-slate-400 mt-1">
            Access your verified outpatient consultation slips, OPD queue tokens, and appointment self-service.
          </p>
        </div>

        {/* Portal View Switcher Tabs */}
        <div className="flex rounded-2xl bg-slate-900 border border-slate-800 p-1 text-xs font-semibold self-start md:self-auto">
          <button
            onClick={() => setActiveTab("my_passes")}
            className={`px-4 py-2 rounded-xl transition cursor-pointer flex items-center gap-1.5 ${
              activeTab === "my_passes"
                ? "bg-teal-600 text-white shadow-md shadow-teal-600/20"
                : "text-slate-400 hover:text-white"
            }`}
          >
            <ShieldCheck className="w-3.5 h-3.5" />
            <span>My Passes</span>
          </button>
          <button
            onClick={() => setActiveTab("lookup")}
            className={`px-4 py-2 rounded-xl transition cursor-pointer flex items-center gap-1.5 ${
              activeTab === "lookup"
                ? "bg-teal-600 text-white shadow-md shadow-teal-600/20"
                : "text-slate-400 hover:text-white"
            }`}
          >
            <Search className="w-3.5 h-3.5" />
            <span>Pass Lookup</span>
          </button>
          <button
            onClick={() => setActiveTab("all")}
            className={`px-4 py-2 rounded-xl transition cursor-pointer flex items-center gap-1.5 ${
              activeTab === "all"
                ? "bg-teal-600 text-white shadow-md shadow-teal-600/20"
                : "text-slate-400 hover:text-white"
            }`}
          >
            <FileText className="w-3.5 h-3.5" />
            <span>All Directory</span>
          </button>
        </div>
      </div>

      {/* Notice Toast */}
      {notice && (
        <div className="p-3.5 rounded-xl bg-teal-950/80 border border-teal-800 text-teal-200 text-xs flex items-center justify-between animate-in fade-in">
          <span className="flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-teal-400" />
            {notice}
          </span>
          <button
            onClick={() => setNotice(null)}
            className="text-teal-400 hover:text-white font-mono text-xs cursor-pointer"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Error Alert */}
      {error && (
        <div className="p-4 rounded-2xl bg-rose-950/40 border border-rose-800/80 text-rose-300 text-xs flex flex-col sm:flex-row sm:items-center justify-between gap-3 animate-in fade-in">
          <div className="flex items-center gap-2">
            <AlertCircle className="w-4 h-4 text-rose-400 shrink-0" />
            <span>{error}</span>
          </div>
          <button
            onClick={loadAppointments}
            className="px-3 py-1.5 rounded-lg bg-rose-900/80 hover:bg-rose-800 text-rose-100 font-medium transition cursor-pointer flex items-center justify-center gap-1.5 shrink-0"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            <span>Retry</span>
          </button>
        </div>
      )}

      {/* TAB 1: MY PASSES (PATIENT VERIFIED PORTAL) */}
      {activeTab === "my_passes" && (
        <div className="space-y-6">
          {!patientAuth ? (
            /* OTP Login Card */
            <div className="max-w-md mx-auto p-8 rounded-3xl bg-slate-900/90 border border-slate-800 shadow-2xl text-center space-y-6">
              <div className="w-12 h-12 rounded-2xl bg-teal-500/20 text-teal-400 flex items-center justify-center mx-auto border border-teal-500/30">
                <ShieldCheck className="w-6 h-6" />
              </div>

              <div>
                <h2 className="text-xl font-bold text-white tracking-tight">Patient Portal Verification</h2>
                <p className="text-xs text-slate-400 mt-1">
                  Enter your mobile number to view your consultation passes and check in for queue tokens.
                </p>
              </div>

              {otpError && (
                <div className="p-3 rounded-xl bg-rose-950/60 border border-rose-800 text-rose-300 text-xs">
                  {otpError}
                </div>
              )}
              {otpNotice && (
                <div className="p-3 rounded-xl bg-teal-950/60 border border-teal-800 text-teal-300 text-xs">
                  {otpNotice}
                </div>
              )}

              {!otpSent ? (
                <form onSubmit={handleRequestOtp} className="space-y-4">
                  <div className="space-y-1 text-left">
                    <label className="text-xs font-semibold text-slate-300">Registered Phone Number</label>
                    <div className="relative">
                      <Phone className="w-4 h-4 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
                      <input
                        type="text"
                        value={phoneInput}
                        onChange={(e) => setPhoneInput(e.target.value)}
                        placeholder="+91 98400 12345"
                        className="w-full pl-9 pr-3.5 py-2.5 rounded-xl bg-slate-950 border border-slate-800 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-teal-500 font-mono"
                        required
                      />
                    </div>
                  </div>

                  <button
                    type="submit"
                    disabled={otpLoading}
                    className="w-full py-2.5 rounded-xl bg-teal-600 hover:bg-teal-500 text-white text-xs font-bold transition shadow-lg shadow-teal-600/20 disabled:opacity-50 cursor-pointer flex items-center justify-center gap-2"
                  >
                    {otpLoading ? "Sending OTP..." : "Request 6-Digit OTP"}
                    <ArrowRight className="w-4 h-4" />
                  </button>
                </form>
              ) : (
                <form onSubmit={handleVerifyOtp} className="space-y-4">
                  <div className="space-y-1 text-left">
                    <label className="text-xs font-semibold text-slate-300">Enter Verification Code</label>
                    <div className="relative">
                      <KeyRound className="w-4 h-4 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
                      <input
                        type="text"
                        value={otpInput}
                        onChange={(e) => setOtpInput(e.target.value)}
                        placeholder="123456"
                        maxLength={8}
                        className="w-full pl-9 pr-3.5 py-2.5 rounded-xl bg-slate-950 border border-slate-800 text-base text-white text-center font-mono tracking-widest focus:outline-none focus:border-teal-500"
                        required
                      />
                    </div>
                    <span className="text-[10px] text-slate-500 block pt-1">
                      Demo test code is <span className="font-mono text-teal-400">123456</span>.
                    </span>
                  </div>

                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={() => setOtpSent(false)}
                      className="w-1/3 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold transition cursor-pointer"
                    >
                      Change Phone
                    </button>
                    <button
                      type="submit"
                      disabled={otpLoading}
                      className="w-2/3 py-2.5 rounded-xl bg-teal-600 hover:bg-teal-500 text-white text-xs font-bold transition shadow-lg shadow-teal-600/20 disabled:opacity-50 cursor-pointer"
                    >
                      {otpLoading ? "Verifying..." : "Verify & Access Passes"}
                    </button>
                  </div>
                </form>
              )}
            </div>
          ) : (
            /* Verified Patient Workspace */
            <div className="space-y-6">
              {/* Patient Profile Bar */}
              <div className="p-4 rounded-2xl bg-slate-900 border border-slate-800 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-teal-500/20 text-teal-400 flex items-center justify-center font-bold text-sm border border-teal-500/30">
                    <User className="w-5 h-5" />
                  </div>
                  <div>
                    <div className="text-sm font-bold text-white flex items-center gap-2">
                      <span>{patientAuth.display_name}</span>
                      <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-teal-500/20 text-teal-300 border border-teal-500/30">
                        Verified Patient
                      </span>
                    </div>
                    <div className="text-xs text-slate-400 font-mono">{patientAuth.phone}</div>
                  </div>
                </div>

                <button
                  onClick={handleLogoutPatient}
                  className="px-3 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-300 text-xs font-semibold transition flex items-center gap-1.5 self-start sm:self-auto cursor-pointer"
                >
                  <LogOut className="w-3.5 h-3.5 text-slate-400" />
                  <span>Sign Out</span>
                </button>
              </div>

              {/* Patient Appointment Passes */}
              {loading ? (
                <div className="py-12 text-center text-xs text-slate-400">Loading consultation passes...</div>
              ) : appointments.length > 0 ? (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  {appointments.map((apt) => renderPassCard(apt))}
                </div>
              ) : (
                <div className="p-12 rounded-3xl bg-slate-900/60 border border-slate-800 text-center space-y-3">
                  <Calendar className="w-8 h-8 text-slate-600 mx-auto" />
                  <p className="text-sm font-semibold text-slate-300">No appointments found for your phone number.</p>
                  <p className="text-xs text-slate-500">
                    You can book a new specialist consultation via the Voice Assistant.
                  </p>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* TAB 2: SINGLE PASS LOOKUP */}
      {activeTab === "lookup" && (
        <div className="max-w-2xl mx-auto space-y-6">
          <div className="p-6 rounded-3xl bg-slate-900/90 border border-slate-800 shadow-xl space-y-4">
            <div>
              <h2 className="text-lg font-bold text-white tracking-tight">Lookup Specific Appointment Pass</h2>
              <p className="text-xs text-slate-400 mt-0.5">
                For privacy protection, both the unique Booking Reference and matching phone number are required.
              </p>
            </div>

            {lookupError && (
              <div className="p-3.5 rounded-xl bg-rose-950/60 border border-rose-800 text-rose-300 text-xs">
                {lookupError}
              </div>
            )}

            <form onSubmit={handleLookupSubmit} className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div className="space-y-1">
                  <label className="text-xs font-semibold text-slate-300">Booking Reference</label>
                  <input
                    type="text"
                    value={lookupRef}
                    onChange={(e) => setLookupRef(e.target.value.toUpperCase())}
                    placeholder="e.g. APT-20261020-A1B2C3"
                    className="w-full px-3.5 py-2.5 rounded-xl bg-slate-950 border border-slate-800 text-xs text-white placeholder-slate-500 font-mono focus:outline-none focus:border-teal-500"
                    required
                  />
                </div>

                <div className="space-y-1">
                  <label className="text-xs font-semibold text-slate-300">Verified Phone Number</label>
                  <input
                    type="text"
                    value={lookupPhone}
                    onChange={(e) => setLookupPhone(e.target.value)}
                    placeholder="+91 98400 12345"
                    className="w-full px-3.5 py-2.5 rounded-xl bg-slate-950 border border-slate-800 text-xs text-white placeholder-slate-500 font-mono focus:outline-none focus:border-teal-500"
                    required
                  />
                </div>
              </div>

              <button
                type="submit"
                disabled={lookupLoading}
                className="w-full py-2.5 rounded-xl bg-teal-600 hover:bg-teal-500 text-white text-xs font-bold transition shadow-lg shadow-teal-600/20 disabled:opacity-50 cursor-pointer flex items-center justify-center gap-2"
              >
                {lookupLoading ? "Verifying Records..." : "Locate Outpatient Pass"}
                <Search className="w-4 h-4" />
              </button>
            </form>
          </div>

          {lookupResult && (
            <div className="animate-in fade-in">
              <h3 className="text-sm font-bold text-white mb-3">Found Consultation Pass</h3>
              {renderPassCard(lookupResult)}
            </div>
          )}
        </div>
      )}

      {/* TAB 3: ALL APPOINTMENTS DIRECTORY */}
      {activeTab === "all" && (
        <div className="space-y-6">
          {/* Filter Bar */}
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="relative">
              <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                placeholder="Search reference, patient, doctor..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pl-9 pr-4 py-2 rounded-xl bg-slate-900 border border-slate-800 text-xs sm:text-sm text-white placeholder-slate-500 focus:outline-none focus:border-teal-500 w-60 sm:w-72"
              />
            </div>

            <div className="flex rounded-xl bg-slate-900 border border-slate-800 p-1 text-xs">
              {["all", "booked", "confirmed", "checked-in", "completed", "cancelled"].map((st) => (
                <button
                  key={st}
                  onClick={() => setStatusFilter(st)}
                  className={`px-3 py-1.5 rounded-lg capitalize transition cursor-pointer ${
                    statusFilter === st
                      ? "bg-teal-600 text-white font-semibold"
                      : "text-slate-400 hover:text-white"
                  }`}
                >
                  {st}
                </button>
              ))}
            </div>
          </div>

          {loading ? (
            <div className="space-y-4">
              {[1, 2, 3].map((i) => (
                <div key={i} className="p-6 rounded-2xl bg-slate-900/40 border border-slate-800 space-y-3 animate-pulse">
                  <div className="h-5 w-1/4 bg-slate-800 rounded"></div>
                  <div className="h-4 w-1/2 bg-slate-800/60 rounded"></div>
                </div>
              ))}
            </div>
          ) : appointments.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {appointments.map((apt) => renderPassCard(apt))}
            </div>
          ) : (
            <div className="text-center py-12 text-slate-500 text-sm">
              No appointments found matching your filter criteria.
            </div>
          )}
        </div>
      )}

      {/* Reschedule Modal */}
      {rescheduleApt && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm animate-in fade-in">
          <div className="w-full max-w-md bg-slate-900 border border-slate-800 rounded-3xl p-6 shadow-2xl space-y-6">
            <div className="flex items-center justify-between border-b border-slate-800 pb-4">
              <div>
                <h3 className="text-base font-bold text-white">Reschedule Appointment</h3>
                <p className="text-xs text-slate-400 font-mono">{rescheduleApt.booking_reference}</p>
              </div>
              <button
                onClick={() => setRescheduleApt(null)}
                className="p-1.5 text-slate-400 hover:text-white rounded-lg transition"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {rescheduleError && (
              <div className="p-3 rounded-xl bg-rose-950/60 border border-rose-800 text-rose-300 text-xs">
                {rescheduleError}
              </div>
            )}

            <form onSubmit={handleRescheduleSubmit} className="space-y-4">
              <div className="space-y-1">
                <label className="text-xs font-semibold text-slate-300">New Consultation Date</label>
                <input
                  type="date"
                  value={rescheduleDate}
                  min={new Date().toISOString().split("T")[0]}
                  onChange={(e) => setRescheduleDate(e.target.value)}
                  className="w-full px-3.5 py-2.5 rounded-xl bg-slate-950 border border-slate-800 text-xs text-white focus:outline-none focus:border-teal-500"
                  required
                />
              </div>

              <div className="space-y-1">
                <label className="text-xs font-semibold text-slate-300">New Start Time</label>
                <select
                  value={rescheduleTime}
                  onChange={(e) => setRescheduleTime(e.target.value)}
                  className="w-full px-3.5 py-2.5 rounded-xl bg-slate-950 border border-slate-800 text-xs text-white focus:outline-none focus:border-teal-500"
                >
                  {["09:00", "09:30", "10:00", "10:30", "11:00", "11:30", "12:00", "12:30", "14:00", "14:30", "15:00", "15:30", "16:00"].map(
                    (slot) => (
                      <option key={slot} value={slot}>
                        {slot}
                      </option>
                    )
                  )}
                </select>
              </div>

              <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => setRescheduleApt(null)}
                  className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={rescheduleLoading}
                  className="px-5 py-2 rounded-xl bg-teal-600 hover:bg-teal-500 text-white text-xs font-bold transition shadow-md shadow-teal-600/20 disabled:opacity-50"
                >
                  {rescheduleLoading ? "Saving..." : "Confirm Reschedule"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )

  // Reusable Digital Outpatient Pass Card
  function renderPassCard(apt) {
    const isCancelled = apt.status === "cancelled"
    const isCompleted = apt.status === "completed"
    const isCheckedIn = apt.status === "checked-in" || !!apt.queue_token
    const isToday = apt.appointment_date === new Date().toISOString().split("T")[0]

    return (
      <div
        key={apt.id}
        className="rounded-3xl bg-slate-900/90 border border-slate-800 hover:border-slate-700/80 transition p-6 shadow-xl flex flex-col justify-between relative overflow-hidden group"
      >
        {/* Top Header Strip */}
        <div className="flex items-center justify-between pb-4 border-b border-slate-800/80">
          <div className="flex items-center gap-2">
            <span className="font-mono text-sm font-bold text-teal-300 tracking-wide">
              {apt.booking_reference}
            </span>
            <Badge
              variant={
                isCompleted
                  ? "emerald"
                  : isCancelled
                  ? "rose"
                  : isCheckedIn
                  ? "teal"
                  : "default"
              }
              size="xs"
              dot
            >
              {apt.status}
            </Badge>
          </div>

          {apt.queue_token && (
            <div className="px-3 py-1 rounded-xl bg-teal-500/20 text-teal-300 font-mono font-bold text-xs border border-teal-500/30">
              Token: {apt.queue_token}
            </div>
          )}
        </div>

        {/* Doctor & Patient Information */}
        <div className="py-4 space-y-3">
          <div className="flex items-start justify-between">
            <div>
              <div className="text-xs text-slate-400">Consulting Specialist</div>
              <div className="text-base font-bold text-white flex items-center gap-1.5 mt-0.5">
                <User className="w-4 h-4 text-teal-400 shrink-0" />
                <span>{apt.doctor?.name || "Specialist"}</span>
              </div>
              <div className="text-xs text-slate-400 mt-0.5">{apt.doctor?.specialty}</div>
            </div>

            <div className="text-right">
              <div className="text-xs text-slate-400">Patient</div>
              <div className="text-sm font-semibold text-slate-200 mt-0.5">
                {apt.patient?.display_name || "Outpatient"}
              </div>
              <div className="text-[11px] font-mono text-slate-500">{apt.patient?.phone}</div>
            </div>
          </div>

          {/* Schedule & Location Chips */}
          <div className="grid grid-cols-2 gap-2 pt-2 text-xs">
            <div className="p-2.5 rounded-xl bg-slate-950/70 border border-slate-800 flex items-center gap-2">
              <Clock className="w-3.5 h-3.5 text-teal-400 shrink-0" />
              <div>
                <span className="text-[10px] text-slate-500 block uppercase">Schedule</span>
                <span className="text-slate-300 font-mono">
                  {apt.appointment_date} at {apt.start_time?.slice(0, 5)}
                </span>
              </div>
            </div>

            <div className="p-2.5 rounded-xl bg-slate-950/70 border border-slate-800 flex items-center gap-2">
              <MapPin className="w-3.5 h-3.5 text-cyan-400 shrink-0" />
              <div>
                <span className="text-[10px] text-slate-500 block uppercase">Room Location</span>
                <span className="text-slate-300 truncate">
                  {apt.doctor?.room_number || "OPD Desk"}
                </span>
              </div>
            </div>
          </div>

          {/* Simulated Digital Pass Barcode Strip */}
          <div className="pt-2 flex items-center justify-between text-slate-600 font-mono text-[10px] border-t border-slate-800/60">
            <div className="flex items-center gap-1.5">
              <QrCode className="w-4 h-4 text-slate-500" />
              <span className="tracking-widest">||| | |||| | ||| |||| |</span>
            </div>
            <span>MediVoice Outpatient Pass</span>
          </div>
        </div>

        {/* Action Buttons */}
        {!isCancelled && !isCompleted && (
          <div className="pt-4 border-t border-slate-800 flex items-center justify-between gap-2">
            {!isCheckedIn && isToday ? (
              <button
                onClick={() => handleCheckIn(apt)}
                className="px-3.5 py-1.5 rounded-xl bg-teal-600 hover:bg-teal-500 text-white text-xs font-bold transition shadow-sm cursor-pointer flex items-center gap-1.5"
              >
                <Sparkles className="w-3.5 h-3.5" />
                <span>Check In for OPD</span>
              </button>
            ) : (
              <span className="text-[11px] text-slate-500 font-mono">
                {isCheckedIn ? "Token Issued" : "Advance Booking"}
              </span>
            )}

            <div className="flex items-center gap-2">
              <button
                onClick={() => {
                  setRescheduleApt(apt)
                  setRescheduleDate(apt.appointment_date)
                  setRescheduleTime(apt.start_time?.slice(0, 5) || "10:00")
                }}
                className="px-3 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-300 text-xs font-semibold transition cursor-pointer"
              >
                Reschedule
              </button>

              <button
                onClick={() => handleCancel(apt.id)}
                className="px-3 py-1.5 rounded-xl bg-rose-950/50 hover:bg-rose-900 border border-rose-800/60 text-rose-300 text-xs font-semibold transition cursor-pointer"
              >
                Cancel
              </button>
            </div>
          </div>
        )}
      </div>
    )
  }
}
