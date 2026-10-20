import { useState, useEffect, useCallback } from "react"
import { Search, MapPin, Clock, Calendar, CheckCircle2, User, RefreshCw, AlertCircle, X } from "lucide-react"
import Badge from "../components/ui/Badge"
import LiveStatusBadge from "../components/ui/LiveStatusBadge"
import { useWebSocketEvent } from "../hooks/useWebSocket"
import { getDoctors, getDepartments, getDoctorAvailability, createAppointment } from "../services/api"

export default function Doctors() {
  const [doctors, setDoctors] = useState([])
  const [departments, setDepartments] = useState([])
  const [search, setSearch] = useState("")
  const [selectedDept, setSelectedDept] = useState("all")
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  // Booking Modal State
  const [bookingDoc, setBookingDoc] = useState(null)
  const [bookingDate, setBookingDate] = useState(() => {
    const d = new Date()
    return d.toISOString().split("T")[0]
  })
  const [availability, setAvailability] = useState(null)
  const [loadingSlots, setLoadingSlots] = useState(false)
  const [selectedSlot, setSelectedSlot] = useState(null)
  const [patientName, setPatientName] = useState("")
  const [patientPhone, setPatientPhone] = useState("")
  const [bookingSubmitting, setBookingSubmitting] = useState(false)
  const [bookingResult, setBookingResult] = useState(null)
  const [bookingError, setBookingError] = useState(null)

  const loadData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [docsData, deptsData] = await Promise.all([
        getDoctors({
          search: search || undefined,
          department_id: selectedDept !== "all" ? selectedDept : undefined,
        }),
        getDepartments(),
      ])
      setDoctors(docsData)
      setDepartments(deptsData)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [search, selectedDept])

  useEffect(() => {
    const timer = setTimeout(() => {
      loadData()
    }, 250)
    return () => clearTimeout(timer)
  }, [loadData])

  // Slot availability loader
  const loadSlots = useCallback(async (docId, dateStr) => {
    setLoadingSlots(true)
    setBookingError(null)
    try {
      const data = await getDoctorAvailability(docId, dateStr)
      setAvailability(data)
    } catch (err) {
      setBookingError(err.message)
    } finally {
      setLoadingSlots(false)
    }
  }, [])

  // Real-time slot availability invalidation
  useWebSocketEvent("appointment.*", () => {
    if (bookingDoc && bookingDate) {
      loadSlots(bookingDoc.id, bookingDate)
    }
  })
  useWebSocketEvent("reconnect", () => {
    loadData()
    if (bookingDoc && bookingDate) {
      loadSlots(bookingDoc.id, bookingDate)
    }
  })

  const handleOpenBooking = (doc) => {
    setBookingDoc(doc)
    setSelectedSlot(null)
    setBookingResult(null)
    setBookingError(null)
    loadSlots(doc.id, bookingDate)
  }

  const handleDateChange = (newDate) => {
    setBookingDate(newDate)
    setSelectedSlot(null)
    if (bookingDoc) {
      loadSlots(bookingDoc.id, newDate)
    }
  }

  const handleConfirmBooking = async (e) => {
    e.preventDefault()
    if (!selectedSlot || !patientName.trim()) {
      setBookingError("Please select an available time slot and provide patient name.")
      return
    }

    setBookingSubmitting(true)
    setBookingError(null)
    try {
      const res = await createAppointment({
        doctor_id: bookingDoc.id,
        department_id: bookingDoc.department_id,
        appointment_date: bookingDate,
        start_time: selectedSlot.start_time + ":00",
        patient_name: patientName.trim(),
        patient_phone: patientPhone.trim() || undefined,
      })
      setBookingResult(res)
    } catch (err) {
      setBookingError(err.message)
    } finally {
      setBookingSubmitting(false)
    }
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10 space-y-8">
      {/* Page Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800 pb-6">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl sm:text-4xl font-extrabold text-white tracking-tight">
              Hospital Doctors Directory
            </h1>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-teal-950 border border-teal-800 text-teal-300">
              Live Database
            </span>
            <LiveStatusBadge />
          </div>
          <p className="text-xs sm:text-sm text-slate-400 mt-1">
            Browse verified clinical specialists, OPD timings, consultation rooms, and live schedule slots.
          </p>
        </div>

        {/* Search & Department Filter */}
        <div className="flex flex-wrap items-center gap-2.5">
          <div className="relative">
            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Search by doctor name or specialty..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-9 pr-4 py-2 rounded-xl bg-slate-900 border border-slate-800 text-xs sm:text-sm text-white placeholder-slate-500 focus:outline-none focus:border-teal-500 w-60 sm:w-72"
            />
          </div>

          <select
            value={selectedDept}
            onChange={(e) => setSelectedDept(e.target.value)}
            className="px-3 py-2 rounded-xl bg-slate-900 border border-slate-800 text-xs sm:text-sm text-slate-300 focus:outline-none focus:border-teal-500 cursor-pointer"
          >
            <option value="all">All Specialties</option>
            {departments.map((dept) => (
              <option key={dept.id} value={dept.id}>
                {dept.name}
              </option>
            ))}
          </select>
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
            onClick={loadData}
            className="px-3 py-1.5 rounded-lg bg-rose-900/80 hover:bg-rose-800 text-rose-100 font-medium transition cursor-pointer flex items-center justify-center gap-1.5 shrink-0"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            <span>Retry Connection</span>
          </button>
        </div>
      )}

      {/* Loading Skeleton */}
      {loading && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {[1, 2, 3].map((i) => (
            <div key={i} className="p-6 rounded-2xl bg-slate-900/40 border border-slate-800 space-y-4 animate-pulse">
              <div className="h-6 w-1/2 bg-slate-800 rounded"></div>
              <div className="h-4 w-1/3 bg-slate-800/60 rounded"></div>
              <div className="h-20 bg-slate-950 rounded"></div>
            </div>
          ))}
        </div>
      )}

      {/* Doctors Grid */}
      {!loading && !error && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {doctors.length > 0 ? (
            doctors.map((doc) => (
              <div
                key={doc.id}
                className="rounded-2xl bg-slate-900/60 border border-slate-800 p-5 space-y-4 hover:border-slate-700 transition flex flex-col justify-between"
              >
                <div className="space-y-3">
                  {/* Header: Name, Specialty & Status */}
                  <div className="flex items-start justify-between gap-2">
                    <div className="space-y-0.5">
                      <h3 className="font-bold text-white text-base leading-snug">{doc.name}</h3>
                      <p className="text-xs text-teal-400 font-medium">{doc.specialty}</p>
                      <p className="text-[11px] text-slate-400">{doc.qualifications}</p>
                    </div>
                    <Badge variant={doc.is_active ? "emerald" : "default"} size="xs" dot>
                      {doc.is_active ? "On Duty" : "Off Duty"}
                    </Badge>
                  </div>

                  {/* Details Pill Box */}
                  <div className="p-3 rounded-xl bg-slate-950 border border-slate-800/80 space-y-2 text-xs text-slate-300">
                    <div className="flex items-center justify-between">
                      <span className="text-slate-400 flex items-center gap-1.5">
                        <MapPin className="w-3.5 h-3.5 text-slate-500" />
                        Room / Wing:
                      </span>
                      <span className="font-semibold text-white">{doc.room_number}</span>
                    </div>

                    <div className="flex items-center justify-between">
                      <span className="text-slate-400 flex items-center gap-1.5">
                        <Clock className="w-3.5 h-3.5 text-slate-500" />
                        Department:
                      </span>
                      <span className="text-slate-200">{doc.department?.name || "Outpatient Desk"}</span>
                    </div>

                    <div className="flex items-center justify-between">
                      <span className="text-slate-400 flex items-center gap-1.5">
                        <Calendar className="w-3.5 h-3.5 text-slate-500" />
                        Experience:
                      </span>
                      <span className="font-medium text-emerald-400">{doc.experience}</span>
                    </div>
                  </div>

                  {/* Consultation Fee */}
                  <div className="flex items-center justify-between text-xs text-slate-400 pt-1">
                    <span>Consultation Fee:</span>
                    <strong className="text-teal-300 font-mono">₹{doc.consultation_fee}</strong>
                  </div>
                </div>

                {/* Action Button */}
                <div className="pt-3 border-t border-slate-800/80">
                  <button
                    onClick={() => handleOpenBooking(doc)}
                    className="w-full py-2 px-3 rounded-xl text-xs font-semibold bg-teal-600 hover:bg-teal-500 text-white transition shadow-sm cursor-pointer flex items-center justify-center gap-2"
                  >
                    <Calendar className="w-3.5 h-3.5" />
                    <span>Check Live Slots & Book</span>
                  </button>
                </div>
              </div>
            ))
          ) : (
            <div className="col-span-full py-16 text-center space-y-3 p-8 rounded-2xl bg-slate-900/30 border border-slate-800">
              <User className="w-10 h-10 text-slate-600 mx-auto" />
              <h3 className="text-base font-semibold text-white">No doctors found</h3>
              <p className="text-xs text-slate-400">
                Try adjusting your specialty filter or search term.
              </p>
            </div>
          )}
        </div>
      )}

      {/* Live Booking Modal */}
      {bookingDoc && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs">
          <div className="w-full max-w-lg bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-2xl space-y-4 max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div>
                <h3 className="text-base font-bold text-white">
                  Book Slot with {bookingDoc.name}
                </h3>
                <p className="text-xs text-teal-400">{bookingDoc.specialty} • {bookingDoc.room_number}</p>
              </div>
              <button
                onClick={() => setBookingDoc(null)}
                className="text-slate-400 hover:text-white p-1 rounded-lg hover:bg-slate-800"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {bookingResult ? (
              <div className="p-4 rounded-xl bg-teal-950/60 border border-teal-800 text-teal-200 text-xs space-y-3 animate-in fade-in">
                <div className="flex items-center gap-2 font-bold text-sm text-teal-300">
                  <CheckCircle2 className="w-5 h-5 text-teal-400" />
                  <span>Consultation Slot Confirmed!</span>
                </div>
                <div className="p-3 bg-slate-950 rounded-lg font-mono space-y-1 text-slate-300">
                  <div>Booking Ref: <strong className="text-white">{bookingResult.booking_reference}</strong></div>
                  <div>Date & Time: <span className="text-teal-400">{bookingResult.appointment_date} at {bookingResult.start_time}</span></div>
                  <div>Patient: {bookingResult.patient?.display_name}</div>
                  {bookingResult.queue_token && (
                    <div className="text-emerald-400 font-bold">Queue Token: {bookingResult.queue_token}</div>
                  )}
                </div>
                <button
                  onClick={() => setBookingDoc(null)}
                  className="w-full py-2 bg-teal-600 hover:bg-teal-500 text-white rounded-lg font-semibold"
                >
                  Done
                </button>
              </div>
            ) : (
              <form onSubmit={handleConfirmBooking} className="space-y-4">
                {bookingError && (
                  <div className="p-3 rounded-lg bg-rose-950/60 border border-rose-800 text-rose-300 text-xs flex items-center gap-2">
                    <AlertCircle className="w-4 h-4 shrink-0" />
                    <span>{bookingError}</span>
                  </div>
                )}

                {/* Date Picker */}
                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1">
                    Select Consultation Date:
                  </label>
                  <input
                    type="date"
                    min={new Date().toISOString().split("T")[0]}
                    value={bookingDate}
                    onChange={(e) => handleDateChange(e.target.value)}
                    className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-xs text-white focus:outline-none focus:border-teal-500"
                  />
                </div>

                {/* Slot Selector */}
                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1">
                    Available Working Slots:
                  </label>
                  {loadingSlots ? (
                    <div className="text-xs text-slate-500 italic py-2 flex items-center gap-2">
                      <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                      Loading doctor&apos;s live schedule...
                    </div>
                  ) : availability && availability.available_slots.length > 0 ? (
                    <div className="grid grid-cols-3 gap-2 max-h-36 overflow-y-auto p-1">
                      {availability.available_slots.map((s) => (
                        <button
                          key={s.start_time}
                          type="button"
                          disabled={!s.is_available}
                          onClick={() => setSelectedSlot(s)}
                          className={`py-1.5 px-2 rounded-lg text-xs font-mono transition text-center cursor-pointer ${
                            !s.is_available
                              ? "bg-slate-950/40 text-slate-600 border border-slate-900 cursor-not-allowed line-through"
                              : selectedSlot?.start_time === s.start_time
                              ? "bg-teal-600 text-white font-bold ring-2 ring-teal-400"
                              : "bg-slate-950 text-slate-200 border border-slate-800 hover:border-teal-600"
                          }`}
                        >
                          {s.start_time}
                        </button>
                      ))}
                    </div>
                  ) : (
                    <div className="text-xs text-amber-400 bg-amber-950/30 p-2.5 rounded-lg border border-amber-900/60">
                      No working slots scheduled for this specialist on the selected date.
                    </div>
                  )}
                </div>

                {/* Patient Information Form */}
                <div className="space-y-2 pt-2 border-t border-slate-800">
                  <div>
                    <label className="block text-xs font-medium text-slate-300 mb-1">
                      Patient Full Name:
                    </label>
                    <input
                      type="text"
                      required
                      placeholder="e.g. Ramesh Kumar"
                      value={patientName}
                      onChange={(e) => setPatientName(e.target.value)}
                      className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-xs text-white focus:outline-none focus:border-teal-500"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-slate-300 mb-1">
                      Mobile Contact (Optional):
                    </label>
                    <input
                      type="tel"
                      placeholder="+91 98765 43210"
                      value={patientPhone}
                      onChange={(e) => setPatientPhone(e.target.value)}
                      className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-xs text-white focus:outline-none focus:border-teal-500"
                    />
                  </div>
                </div>

                {/* Submit */}
                <div className="flex justify-end gap-2 pt-2 border-t border-slate-800">
                  <button
                    type="button"
                    onClick={() => setBookingDoc(null)}
                    className="px-4 py-2 text-xs font-semibold rounded-xl bg-slate-800 text-slate-300 hover:bg-slate-700"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={bookingSubmitting || !selectedSlot}
                    className="px-5 py-2 text-xs font-semibold rounded-xl bg-teal-600 hover:bg-teal-500 disabled:opacity-50 text-white"
                  >
                    {bookingSubmitting ? "Persisting Booking..." : "Confirm Consultation"}
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
