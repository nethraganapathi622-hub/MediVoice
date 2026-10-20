// Centralized Hospital API Client for MediVoice

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000"

export function getAuthStaff() {
  try {
    const raw = localStorage.getItem("medivoice_staff_auth")
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

export function setAuthStaff(data) {
  try {
    localStorage.setItem("medivoice_staff_auth", JSON.stringify(data))
  } catch (e) {
    console.error("Failed saving staff auth:", e)
  }
}

export function clearAuthStaff() {
  localStorage.removeItem("medivoice_staff_auth")
}

export function getAuthPatient() {
  try {
    const raw = localStorage.getItem("medivoice_patient_auth")
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

export function setAuthPatient(data) {
  try {
    localStorage.setItem("medivoice_patient_auth", JSON.stringify(data))
  } catch (e) {
    console.error("Failed saving patient auth:", e)
  }
}

export function clearAuthPatient() {
  localStorage.removeItem("medivoice_patient_auth")
}

async function apiRequest(endpoint, options = {}) {
  const url = `${API_BASE}${endpoint}`
  const staffAuth = getAuthStaff()
  const patientAuth = getAuthPatient()
  const activeToken = options.token || patientAuth?.access_token || staffAuth?.access_token

  const authHeaders = activeToken
    ? { Authorization: `Bearer ${activeToken}` }
    : {}

  const headers = {
    "Content-Type": "application/json",
    ...authHeaders,
    ...options.headers,
  }

  try {
    const res = await fetch(url, { ...options, headers })
    if (!res.ok) {
      let errorMsg = `Server error ${res.status}`
      try {
        const data = await res.json()
        errorMsg = data.detail || data.message || errorMsg
      } catch {
        // use fallback string
      }
      const error = new Error(errorMsg)
      error.status = res.status
      throw error
    }
    return await res.json()
  } catch (err) {
    if (err.name === "TypeError" && err.message.includes("fetch")) {
      const connErr = new Error(
        `Unable to reach MediVoice hospital API at ${API_BASE}. Ensure backend server is running.`
      )
      connErr.status = 503
      throw connErr
    }
    throw err
  }
}

// -----------------------------------------------------------------------------
// Departments
// -----------------------------------------------------------------------------
export async function getDepartments(params = {}) {
  const query = new URLSearchParams()
  if (params.search) query.append("search", params.search)
  if (params.active_only !== undefined) query.append("active_only", params.active_only)
  const qs = query.toString() ? `?${query.toString()}` : ""
  return apiRequest(`/api/departments${qs}`)
}

export async function getDepartmentById(id) {
  return apiRequest(`/api/departments/${id}`)
}

// -----------------------------------------------------------------------------
// Doctors & Availability
// -----------------------------------------------------------------------------
export async function getDoctors(params = {}) {
  const query = new URLSearchParams()
  if (params.department_id) query.append("department_id", params.department_id)
  if (params.specialty) query.append("specialty", params.specialty)
  if (params.search) query.append("search", params.search)
  const qs = query.toString() ? `?${query.toString()}` : ""
  return apiRequest(`/api/doctors${qs}`)
}

export async function getDoctorById(id) {
  return apiRequest(`/api/doctors/${id}`)
}

export async function getDoctorAvailability(doctorId, dateStr) {
  const query = dateStr ? `?date=${dateStr}` : ""
  return apiRequest(`/api/doctors/${doctorId}/availability${query}`)
}

// -----------------------------------------------------------------------------
// Appointments
// -----------------------------------------------------------------------------
export async function getAppointments(params = {}) {
  const query = new URLSearchParams()
  if (params.status && params.status !== "all") query.append("status", params.status)
  if (params.doctor_id) query.append("doctor_id", params.doctor_id)
  if (params.search) query.append("search", params.search)
  const qs = query.toString() ? `?${query.toString()}` : ""
  return apiRequest(`/api/appointments${qs}`)
}

export async function getAppointmentById(id) {
  return apiRequest(`/api/appointments/${id}`)
}

export async function createAppointment(payload) {
  return apiRequest(`/api/appointments`, {
    method: "POST",
    body: JSON.stringify(payload),
  })
}

export async function rescheduleAppointment(id, newDate, newStartTime) {
  return apiRequest(`/api/appointments/${id}/reschedule`, {
    method: "PATCH",
    body: JSON.stringify({ new_date: newDate, new_start_time: newStartTime }),
  })
}

export async function cancelAppointment(id, reason = null) {
  return apiRequest(`/api/appointments/${id}/cancel`, {
    method: "POST",
    body: JSON.stringify({ reason }),
  })
}

// -----------------------------------------------------------------------------
// Patient Queue
// -----------------------------------------------------------------------------
export async function getQueue(params = {}) {
  const query = new URLSearchParams()
  if (params.status && params.status !== "all") query.append("status", params.status)
  if (params.department_id) query.append("department_id", params.department_id)
  if (params.priority) query.append("priority", params.priority)
  const qs = query.toString() ? `?${query.toString()}` : ""
  return apiRequest(`/api/queue${qs}`)
}

export async function queueCheckIn(payload) {
  return apiRequest(`/api/queue/check-in`, {
    method: "POST",
    body: JSON.stringify(payload),
  })
}

export async function callQueuePatient(queueId) {
  return apiRequest(`/api/queue/${queueId}/call`, {
    method: "POST",
  })
}

export async function completeQueuePatient(queueId) {
  return apiRequest(`/api/queue/${queueId}/complete`, {
    method: "POST",
  })
}

// -----------------------------------------------------------------------------
// Triage Alerts
// -----------------------------------------------------------------------------
export async function getAlerts(params = {}) {
  const query = new URLSearchParams()
  if (params.priority && params.priority !== "all") query.append("priority", params.priority)
  if (params.status && params.status !== "all") query.append("status", params.status)
  const qs = query.toString() ? `?${query.toString()}` : ""
  return apiRequest(`/api/alerts${qs}`)
}

export async function acknowledgeAlert(alertId, staffId, staffName, staffRole = "TriageLead") {
  return apiRequest(`/api/alerts/${alertId}/acknowledge`, {
    method: "POST",
    headers: {
      "X-Staff-Role": staffRole,
    },
    body: JSON.stringify({
      staff_id: staffId,
      staff_name: staffName,
    }),
  })
}

// -----------------------------------------------------------------------------
// Staff Authentication
// -----------------------------------------------------------------------------
export async function loginStaff(staffId, passcode) {
  const data = await apiRequest("/api/auth/staff-token", {
    method: "POST",
    body: JSON.stringify({ staff_id: staffId, passcode }),
  })
  setAuthStaff(data)
  return data
}

// -----------------------------------------------------------------------------
// Multilingual AI Voice Assistant
// -----------------------------------------------------------------------------
export async function sendAssistantChat(payload) {
  return apiRequest("/api/assistant/chat", {
    method: "POST",
    body: JSON.stringify(payload),
  })
}

export async function dispatchEmergencyAlert(payload) {
  return apiRequest("/api/assistant/emergency", {
    method: "POST",
    body: JSON.stringify(payload),
  })
}

export async function getAssistantConfig() {
  return apiRequest("/api/assistant/config")
}

// -----------------------------------------------------------------------------
// Patient Self-Service Portal
// -----------------------------------------------------------------------------
export async function requestPatientOtp(phone, displayName = "") {
  return apiRequest("/api/patient/auth/request-otp", {
    method: "POST",
    body: JSON.stringify({ phone, display_name: displayName }),
  })
}

export async function verifyPatientOtp(phone, otpCode) {
  const data = await apiRequest("/api/patient/auth/verify-otp", {
    method: "POST",
    body: JSON.stringify({ phone, otp_code: otpCode }),
  })
  setAuthPatient(data)
  return data
}

export async function getVerifiedPatientAppointments() {
  return apiRequest("/api/patient/appointments")
}

export async function lookupPatientAppointment(bookingReference, phone) {
  return apiRequest("/api/patient/appointments/lookup", {
    method: "POST",
    body: JSON.stringify({ booking_reference: bookingReference, phone }),
  })
}

export async function patientSelfReschedule(appointmentId, newDate, newStartTime, reason) {
  return apiRequest(`/api/patient/appointments/${appointmentId}/reschedule`, {
    method: "POST",
    body: JSON.stringify({ new_date: newDate, new_start_time: newStartTime, reason }),
  })
}

export async function patientSelfCancel(appointmentId, reason) {
  return apiRequest(`/api/patient/appointments/${appointmentId}/cancel`, {
    method: "POST",
    body: JSON.stringify({ reason }),
  })
}

export async function patientSelfCheckIn(appointmentId) {
  return apiRequest(`/api/patient/appointments/${appointmentId}/check-in`, {
    method: "POST",
  })
}

// -----------------------------------------------------------------------------
// Clinical Staff EHR & Consultations
// -----------------------------------------------------------------------------
export async function createConsultationNote(payload) {
  return apiRequest("/api/consultations", {
    method: "POST",
    body: JSON.stringify(payload),
  })
}

export async function getAppointmentConsultationNote(appointmentId) {
  return apiRequest(`/api/consultations/appointment/${appointmentId}`)
}

export async function getPatientConsultationHistory(patientId) {
  return apiRequest(`/api/consultations/patient/${patientId}`)
}

export async function updateConsultationNote(noteId, payload) {
  return apiRequest(`/api/consultations/${noteId}`, {
    method: "PUT",
    body: JSON.stringify(payload),
  })
}

// -----------------------------------------------------------------------------
// Hospital Notifications
// -----------------------------------------------------------------------------
export async function getRecentNotifications(limit = 50) {
  return apiRequest(`/api/notifications/recent?limit=${limit}`)
}


