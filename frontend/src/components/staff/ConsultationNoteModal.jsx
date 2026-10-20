import { useState, useEffect } from "react"
import {
  FileText,
  Pill,
  Plus,
  Trash2,
  Calendar,
  CheckCircle2,
  AlertCircle,
  X,
  Stethoscope,
  Activity,
} from "lucide-react"
import { createConsultationNote, getAppointmentConsultationNote } from "../../services/api"

export default function ConsultationNoteModal({ appointment, onClose, onSaved }) {
  const [existingNote, setExistingNote] = useState(null)
  const [loadingExisting, setLoadingExisting] = useState(true)

  const [chiefComplaint, setChiefComplaint] = useState("")
  const [diagnosis, setDiagnosis] = useState("")
  const [clinicalNotes, setClinicalNotes] = useState("")
  const [prescriptions, setPrescriptions] = useState([
    {
      medication_name: "",
      dosage: "500mg",
      frequency: "Twice daily after meals",
      duration_days: 7,
      instructions: "Take with full glass of water",
    },
  ])
  const [followUpDate, setFollowUpDate] = useState("")

  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState(null)

  // Check if note already exists for this appointment
  useEffect(() => {
    let mounted = true
    if (appointment?.id) {
      getAppointmentConsultationNote(appointment.id)
        .then((note) => {
          if (mounted && note) {
            setExistingNote(note)
            setChiefComplaint(note.chief_complaint || "")
            setDiagnosis(note.diagnosis || "")
            setClinicalNotes(note.clinical_notes || "")
            setPrescriptions(note.prescriptions || [])
            setFollowUpDate(note.follow_up_date || "")
          }
        })
        .catch(() => {
          // No existing note, prepare new draft
        })
        .finally(() => {
          if (mounted) setLoadingExisting(false)
        })
    }
    return () => {
      mounted = false
    }
  }, [appointment?.id])

  const handleAddMedication = () => {
    setPrescriptions([
      ...prescriptions,
      {
        medication_name: "",
        dosage: "250mg",
        frequency: "Once daily in morning",
        duration_days: 5,
        instructions: "Take after meals",
      },
    ])
  }

  const handleRemoveMedication = (index) => {
    setPrescriptions(prescriptions.filter((_, i) => i !== index))
  }

  const handleMedicationChange = (index, field, value) => {
    const updated = [...prescriptions]
    updated[index][field] = value
    setPrescriptions(updated)
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!chiefComplaint.trim() || !diagnosis.trim()) {
      setError("Please specify both Chief Complaint and Diagnosis.")
      return
    }

    // Filter valid prescriptions
    const validPrescriptions = prescriptions
      .filter((p) => p.medication_name && p.medication_name.trim().length > 0)
      .map((p) => ({
        ...p,
        duration_days: parseInt(p.duration_days, 10) || 7,
      }))

    setSubmitting(true)
    setError(null)
    try {
      const payload = {
        appointment_id: appointment.id,
        chief_complaint: chiefComplaint.trim(),
        diagnosis: diagnosis.trim(),
        clinical_notes: clinicalNotes.trim() || undefined,
        prescriptions: validPrescriptions,
        follow_up_date: followUpDate || undefined,
      }
      const saved = await createConsultationNote(payload)
      if (onSaved) onSaved(saved)
      onClose()
    } catch (err) {
      setError(err.message || "Failed to record consultation note.")
    } finally {
      setSubmitting(false)
    }
  }

  const patientName = appointment?.patient?.display_name || "Outpatient"
  const bookingRef = appointment?.booking_reference || `ID #${appointment?.id}`
  const isViewOnly = !!existingNote

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm animate-in fade-in">
      <div className="w-full max-w-3xl max-h-[90vh] bg-slate-900 border border-slate-800 rounded-3xl shadow-2xl flex flex-col overflow-hidden">
        {/* Modal Header */}
        <div className="px-6 py-4 border-b border-slate-800 flex items-center justify-between bg-slate-900/90">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-teal-500/20 text-teal-400 flex items-center justify-center border border-teal-500/30">
              <Stethoscope className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base font-bold text-white flex items-center gap-2">
                <span>{isViewOnly ? "View Electronic Health Record (EHR)" : "Record Clinical Consultation & Prescriptions"}</span>
                {isViewOnly && (
                  <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
                    Completed Consultation
                  </span>
                )}
              </h2>
              <p className="text-xs text-slate-400">
                Patient: <span className="text-slate-200 font-semibold">{patientName}</span> • Ref:{" "}
                <span className="font-mono text-teal-300">{bookingRef}</span>
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-xl text-slate-400 hover:text-white hover:bg-slate-800 transition cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {error && (
            <div className="p-3.5 rounded-xl bg-rose-950/60 border border-rose-800 text-rose-300 text-xs flex items-center gap-2">
              <AlertCircle className="w-4 h-4 text-rose-400 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {loadingExisting ? (
            <div className="py-12 text-center text-xs text-slate-400 flex items-center justify-center gap-2">
              <Activity className="w-4 h-4 text-teal-400 animate-spin" />
              <span>Loading EHR records...</span>
            </div>
          ) : (
            <form id="ehr-form" onSubmit={handleSubmit} className="space-y-6">
              {/* Chief Complaint */}
              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-slate-300 block">
                  Chief Complaint & Presenting Symptoms <span className="text-rose-400">*</span>
                </label>
                <textarea
                  rows={2}
                  value={chiefComplaint}
                  onChange={(e) => setChiefComplaint(e.target.value)}
                  disabled={isViewOnly}
                  placeholder="e.g. Mild retrosternal chest pain and shortness of breath for past 2 days"
                  className="w-full px-3.5 py-2.5 rounded-xl bg-slate-950 border border-slate-800 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-teal-500 disabled:opacity-75"
                />
              </div>

              {/* Diagnosis */}
              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-slate-300 block">
                  Clinical Diagnosis (ICD Assessment) <span className="text-rose-400">*</span>
                </label>
                <input
                  type="text"
                  value={diagnosis}
                  onChange={(e) => setDiagnosis(e.target.value)}
                  disabled={isViewOnly}
                  placeholder="e.g. Atypical chest pain / Stable angina / Acute bronchitis"
                  className="w-full px-3.5 py-2.5 rounded-xl bg-slate-950 border border-slate-800 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-teal-500 disabled:opacity-75"
                />
              </div>

              {/* Clinical Examination Notes & Vitals */}
              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-slate-300 block">
                  Examination Findings, Vitals & Observations
                </label>
                <textarea
                  rows={3}
                  value={clinicalNotes}
                  onChange={(e) => setClinicalNotes(e.target.value)}
                  disabled={isViewOnly}
                  placeholder="e.g. BP: 120/80 mmHg, Pulse: 74 bpm, SpO2: 99% on room air. Lungs clear to auscultation bilaterally."
                  className="w-full px-3.5 py-2.5 rounded-xl bg-slate-950 border border-slate-800 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-teal-500 disabled:opacity-75 font-mono"
                />
              </div>

              {/* Digital Prescriptions Section */}
              <div className="space-y-3 pt-2 border-t border-slate-800">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Pill className="w-4 h-4 text-teal-400" />
                    <span className="text-xs font-bold text-white uppercase tracking-wider">
                      Digital Prescriptions / Rx
                    </span>
                  </div>
                  {!isViewOnly && (
                    <button
                      type="button"
                      onClick={handleAddMedication}
                      className="px-2.5 py-1 rounded-lg bg-teal-500/10 hover:bg-teal-500/20 border border-teal-500/30 text-teal-300 text-xs font-semibold transition flex items-center gap-1 cursor-pointer"
                    >
                      <Plus className="w-3.5 h-3.5" />
                      <span>Add Medicine</span>
                    </button>
                  )}
                </div>

                <div className="space-y-2">
                  {prescriptions.map((rx, idx) => (
                    <div
                      key={idx}
                      className="p-3.5 rounded-2xl bg-slate-950/70 border border-slate-800 space-y-2.5"
                    >
                      <div className="grid grid-cols-1 sm:grid-cols-12 gap-2">
                        <div className="sm:col-span-4">
                          <label className="text-[10px] text-slate-400 block mb-1">Medication Name</label>
                          <input
                            type="text"
                            value={rx.medication_name}
                            onChange={(e) => handleMedicationChange(idx, "medication_name", e.target.value)}
                            disabled={isViewOnly}
                            placeholder="e.g. Amoxicillin"
                            className="w-full px-2.5 py-1.5 rounded-lg bg-slate-900 border border-slate-800 text-xs text-white focus:outline-none focus:border-teal-500 disabled:opacity-75"
                          />
                        </div>
                        <div className="sm:col-span-2">
                          <label className="text-[10px] text-slate-400 block mb-1">Dosage</label>
                          <input
                            type="text"
                            value={rx.dosage}
                            onChange={(e) => handleMedicationChange(idx, "dosage", e.target.value)}
                            disabled={isViewOnly}
                            placeholder="500mg"
                            className="w-full px-2.5 py-1.5 rounded-lg bg-slate-900 border border-slate-800 text-xs text-white focus:outline-none focus:border-teal-500 disabled:opacity-75"
                          />
                        </div>
                        <div className="sm:col-span-3">
                          <label className="text-[10px] text-slate-400 block mb-1">Frequency</label>
                          <input
                            type="text"
                            value={rx.frequency}
                            onChange={(e) => handleMedicationChange(idx, "frequency", e.target.value)}
                            disabled={isViewOnly}
                            placeholder="Twice daily"
                            className="w-full px-2.5 py-1.5 rounded-lg bg-slate-900 border border-slate-800 text-xs text-white focus:outline-none focus:border-teal-500 disabled:opacity-75"
                          />
                        </div>
                        <div className="sm:col-span-2">
                          <label className="text-[10px] text-slate-400 block mb-1">Days</label>
                          <input
                            type="number"
                            value={rx.duration_days}
                            onChange={(e) => handleMedicationChange(idx, "duration_days", e.target.value)}
                            disabled={isViewOnly}
                            min={1}
                            max={365}
                            className="w-full px-2.5 py-1.5 rounded-lg bg-slate-900 border border-slate-800 text-xs text-white focus:outline-none focus:border-teal-500 disabled:opacity-75"
                          />
                        </div>
                        {!isViewOnly && prescriptions.length > 1 && (
                          <div className="sm:col-span-1 flex items-end justify-center pb-1">
                            <button
                              type="button"
                              onClick={() => handleRemoveMedication(idx)}
                              className="text-slate-500 hover:text-rose-400 p-1.5 rounded-lg transition cursor-pointer"
                              title="Remove medication"
                            >
                              <Trash2 className="w-4 h-4" />
                            </button>
                          </div>
                        )}
                      </div>
                      <div>
                        <input
                          type="text"
                          value={rx.instructions || ""}
                          onChange={(e) => handleMedicationChange(idx, "instructions", e.target.value)}
                          disabled={isViewOnly}
                          placeholder="Special instructions (e.g. Take after food with warm water)"
                          className="w-full px-2.5 py-1 rounded-lg bg-slate-900/60 border border-slate-800 text-[11px] text-slate-300 focus:outline-none focus:border-teal-500 disabled:opacity-75"
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Follow-up Date */}
              <div className="space-y-1.5 pt-2 border-t border-slate-800">
                <label className="text-xs font-semibold text-slate-300 flex items-center gap-1.5">
                  <Calendar className="w-3.5 h-3.5 text-teal-400" />
                  <span>Recommended Clinical Follow-up Date (Optional)</span>
                </label>
                <input
                  type="date"
                  value={followUpDate}
                  onChange={(e) => setFollowUpDate(e.target.value)}
                  disabled={isViewOnly}
                  className="px-3.5 py-2 rounded-xl bg-slate-950 border border-slate-800 text-xs text-white focus:outline-none focus:border-teal-500 disabled:opacity-75"
                />
              </div>
            </form>
          )}
        </div>

        {/* Modal Footer */}
        <div className="px-6 py-4 border-t border-slate-800 bg-slate-900/90 flex items-center justify-between">
          <div className="text-[11px] text-slate-500 flex items-center gap-1.5">
            <CheckCircle2 className="w-3.5 h-3.5 text-teal-400" />
            <span>Consultation record is cryptographically signed under doctor session.</span>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded-xl border border-slate-700 bg-slate-800 text-slate-300 hover:bg-slate-700 text-xs font-semibold transition cursor-pointer"
            >
              Close
            </button>
            {!isViewOnly && (
              <button
                type="submit"
                form="ehr-form"
                disabled={submitting}
                className="px-5 py-2 rounded-xl bg-teal-600 hover:bg-teal-500 text-white text-xs font-bold transition shadow-lg shadow-teal-600/20 disabled:opacity-50 cursor-pointer flex items-center gap-1.5"
              >
                {submitting ? (
                  <>
                    <Activity className="w-3.5 h-3.5 animate-spin" />
                    <span>Saving EHR Note...</span>
                  </>
                ) : (
                  <>
                    <FileText className="w-3.5 h-3.5" />
                    <span>Save & Complete Consultation</span>
                  </>
                )}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
