import { useState, useEffect, useRef } from "react"
import { useNavigate } from "react-router-dom"
import {
  Mic,
  MicOff,
  Sparkles,
  Calendar,
  Users,
  Building2,
  Clock,
  ArrowRight,
  Lock,
  Volume2,
  VolumeX,
  RefreshCw,
  PhoneCall,
  CheckCircle2,
  AlertTriangle,
  Send,
  HelpCircle,
  ShieldAlert,
} from "lucide-react"
import Badge from "../components/ui/Badge"
import AudioWaveform from "../components/ui/AudioWaveform"
import { translations } from "../services/i18n"
import {
  getDepartments,
  sendAssistantChat,
  dispatchEmergencyAlert,
  getAssistantConfig,
} from "../services/api"
import { speechAdapter } from "../services/speechAdapter"

const VOICE_PROMPT_SUGGESTIONS = {
  en: [
    { id: "q1", text: "Book an appointment with a cardiologist tomorrow" },
    { id: "q2", text: "Which doctors are available in Neurology today?" },
    { id: "q3", text: "Where is the Radiology department located?" },
    { id: "q4", text: "Check appointment status for booking reference" },
  ],
  ta: [
    { id: "q1", text: "நாளை இதய மருத்துவரிடம் முன்பதிவு செய்ய வேண்டும்" },
    { id: "q2", text: "நரம்பியல் துறையில் இன்று இருக்கும் மருத்துவர்கள் யார்?" },
    { id: "q3", text: "எக்ஸ்ரே மற்றும் ஸ்கேன் பிரிவு எங்கே உள்ளது?" },
    { id: "q4", text: "எனது முன்பதிவு நிலையை சரிபார்க்கவும்" },
  ],
  hi: [
    { id: "q1", text: "कल के लिए हृदय रोग विशेषज्ञ से अपॉइंटमेंट बुक करें" },
    { id: "q2", text: "आज न्यूरोलॉजी विभाग में कौन से डॉक्टर उपलब्ध हैं?" },
    { id: "q3", text: "रेडियोलॉजी और स्कैन विभाग कहाँ स्थित है?" },
    { id: "q4", text: "मेरी अपॉइंटमेंट की स्थिति की जाँच करें" },
  ],
}

let messageSequence = 0

function createChatMessage(sender, text, extra = {}) {
  messageSequence += 1
  return {
    id: `${sender}-${messageSequence}`,
    sender,
    text,
    timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    ...extra,
  }
}

function getWelcomeText(language) {
  if (language === "ta") {
    return "வணக்கம்! நான் MediVoice மருத்துவமனை உதவியாளர். மருத்துவர் ஆலோசனை, முன்பதிவு அல்லது துறை வழிகாட்டுதலுக்கு மைக்கை அழுத்தி பேசவும் அல்லது கீழே தட்டச்சு செய்யவும்."
  }
  if (language === "hi") {
    return "नमस्ते! मैं MediVoice अस्पताल सहायक हूँ। डॉक्टर परामर्श, अपॉइंटमेंट या विभाग की जानकारी के लिए माइक दबाकर बोलें या नीचे टाइप करें।"
  }
  return "Hello! I am MediVoice, your virtual hospital receptionist. Speak naturally into your microphone or type below to find specialists, check slots, or get department directions."
}

export default function PatientAssistant({ lang = "en" }) {
  const navigate = useNavigate()
  const t = translations[lang] || translations.en

  // Conversation & Interaction State
  // voiceState: "idle" | "requesting_permission" | "listening" | "transcribing" | "processing" | "speaking" | "error"
  const [voiceState, setVoiceState] = useState("idle")
  const [errorMessage, setErrorMessage] = useState(null)
  const [typedInput, setTypedInput] = useState("")
  const [liveTranscript, setLiveTranscript] = useState("")
  const [conversationId, setConversationId] = useState(null)
  const [isMuted, setIsMuted] = useState(false)

  // Chat message timeline: [{ id, sender: 'user'|'assistant', text, intent, actionResult, pendingAction, timestamp }]
  const [messages, setMessages] = useState([])
  const [departments, setDepartments] = useState([])
  const [assistantConfig, setAssistantConfig] = useState(null)

  const messagesEndRef = useRef(null)
  const isSpeechSupported = speechAdapter.isRecognitionSupported()

  // Scroll to bottom of messages smoothly
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages, liveTranscript, voiceState])

  // Initial data load: departments and assistant config
  useEffect(() => {
    let isMounted = true
    getDepartments()
      .then((data) => {
        if (isMounted && Array.isArray(data)) setDepartments(data)
      })
      .catch(() => {})

    getAssistantConfig()
      .then((cfg) => {
        if (isMounted) setAssistantConfig(cfg)
      })
      .catch(() => {})

    return () => {
      isMounted = false
      speechAdapter.abortListening()
      speechAdapter.stopSpeaking()
    }
  }, [])

  // Handle sending a user query (from voice, typed text, or sample click)
  const handleSendMessage = async (text, confirmedActionPayload = null) => {
    const cleanText = text.trim()
    if (!cleanText && !confirmedActionPayload) return

    setErrorMessage(null)
    setVoiceState("processing")

    // Add user bubble
    const userMsg = createChatMessage(
      "user",
      cleanText || (confirmedActionPayload ? "Confirmed Appointment" : "")
    )
    setMessages((prev) => [...prev, userMsg])
    setTypedInput("")
    setLiveTranscript("")

    try {
      const response = await sendAssistantChat({
        conversation_id: conversationId,
        message: cleanText || "Confirm",
        language: lang,
        confirmed_action: confirmedActionPayload,
      })

      if (response.conversation_id && !conversationId) {
        setConversationId(response.conversation_id)
      }

      // Add assistant response bubble
      const assistantMsg = createChatMessage("assistant", response.assistant_text, {
        speechText: response.speech_text,
        intent: response.intent,
        actionResult: response.action_result,
        pendingAction: response.pending_action,
        aiProvider: response.ai_provider_used,
      })
      setMessages((prev) => [...prev, assistantMsg])

      // Speak response if not muted and browser supports TTS
      if (!isMuted && response.speech_text && speechAdapter.isSynthesisSupported()) {
        setVoiceState("speaking")
        speechAdapter.speak(response.speech_text, lang, {
          onEnd: () => setVoiceState("idle"),
          onError: () => setVoiceState("idle"),
        })
      } else {
        setVoiceState("idle")
      }
    } catch (err) {
      console.error("Assistant API Error:", err)
      const errorText =
        err.message || "Unable to reach hospital AI assistant service. Please check your backend connection."
      setErrorMessage(errorText)
      setVoiceState("error")

      setMessages((prev) => [
        ...prev,
        createChatMessage("assistant", errorText, { isError: true }),
      ])
    }
  }


  // Real Speech Recognition Trigger
  const handleStartVoiceRecording = async () => {
    // Stop any active speech synthesis first
    speechAdapter.stopSpeaking()
    setErrorMessage(null)
    setLiveTranscript("")
    setVoiceState("requesting_permission")

    try {
      await speechAdapter.requestMicrophonePermission()
    } catch {
      setErrorMessage("Microphone permission was denied. Please allow microphone access to use voice input.")
      setVoiceState("error")
      return
    }

    setVoiceState("listening")

    speechAdapter.startListening({
      language: lang,
      onStart: () => {
        setVoiceState("listening")
      },
      onInterim: (interim) => {
        setVoiceState("transcribing")
        setLiveTranscript(interim)
      },
      onFinal: (finalText) => {
        setLiveTranscript(finalText)
      },
      onEnd: (finalTranscript) => {
        const queryToProcess = finalTranscript || liveTranscript
        if (queryToProcess && queryToProcess.trim()) {
          handleSendMessage(queryToProcess)
        } else {
          setVoiceState("idle")
          setLiveTranscript("")
        }
      },
      onError: (err) => {
        console.warn("Speech recognition error:", err)
        setErrorMessage(err.message)
        setVoiceState("error")
      },
    })
  }

  const handleStopVoiceRecording = () => {
    speechAdapter.stopListening()
  }

  const handleStopSpeaking = () => {
    speechAdapter.stopSpeaking()
    setVoiceState("idle")
  }

  const handleResetConversation = () => {
    speechAdapter.abortListening()
    speechAdapter.stopSpeaking()
    setVoiceState("idle")
    setLiveTranscript("")
    setErrorMessage(null)
    setConversationId(null)
    setMessages([])
  }

  // Direct Emergency Escalation Trigger
  const handleImmediateEmergency = async () => {
    try {
      const emergencySymptoms = "Urgent Casualty Assistance Requested via Patient Reception Interface"
      const res = await dispatchEmergencyAlert({
        symptoms: emergencySymptoms,
        language: lang,
      })

      setMessages((prev) => [
        ...prev,
        createChatMessage("assistant", res.guidance, {
          speechText: res.speech_guidance,
          intent: "emergency",
          actionResult: {
            emergency: true,
            alert_id: res.alert_id,
            alert_status: res.status,
            emergency_phone: res.emergency_phone,
            ambulance_number: res.ambulance_number,
            trauma_wing: res.wing,
          },
        }),
      ])

      if (!isMuted && speechAdapter.isSynthesisSupported()) {
        speechAdapter.speak(res.speech_guidance, lang)
      }
    } catch (err) {
      console.error("Emergency dispatch error:", err)
    }
  }


  return (
    <div className="space-y-16 pb-16">
      {/* Hero & Centerpiece */}
      <section className="relative pt-6 sm:pt-10">
        <div className="max-w-4xl mx-auto text-center space-y-4">
          <Badge variant="teal" size="md" dot>
            {t.hero.badge}
          </Badge>

          <h1 className="text-3xl sm:text-5xl font-extrabold tracking-tight text-white leading-tight">
            {t.hero.title}
          </h1>

          <p className="text-base sm:text-lg text-slate-400 max-w-2xl mx-auto leading-relaxed">
            {t.hero.subtitle}
          </p>
        </div>

        {/* Central Voice & Multi-Turn Conversation Terminal */}
        <div className="max-w-3xl mx-auto mt-8">
          <div className="relative rounded-3xl bg-slate-900/90 border border-slate-800 shadow-2xl shadow-teal-950/30 overflow-hidden flex flex-col">
            {/* Top State Glow Indicator Bar */}
            <div
              className={`h-1.5 w-full transition-all duration-500 ${
                voiceState === "listening" || voiceState === "transcribing"
                  ? "bg-gradient-to-r from-teal-400 via-cyan-400 to-blue-500 animate-pulse"
                  : voiceState === "processing"
                  ? "bg-gradient-to-r from-amber-400 to-teal-400 animate-pulse"
                  : voiceState === "speaking"
                  ? "bg-gradient-to-r from-emerald-400 to-teal-400"
                  : voiceState === "error"
                  ? "bg-rose-500"
                  : "bg-slate-800"
              }`}
            />

            {/* Conversation Header Bar */}
            <div className="px-6 py-4 border-b border-slate-800 flex items-center justify-between text-xs">
              <div className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full bg-teal-400 animate-pulse" />
                <span className="font-semibold text-slate-200 uppercase tracking-wider font-mono">
                  MediVoice Multilingual Console
                </span>
                <span className="text-slate-500">|</span>
                <span className="font-mono text-teal-400 uppercase">{lang}</span>
              </div>

              <div className="flex items-center gap-3">
                {/* Mute Spoken Responses Toggle */}
                <button
                  onClick={() => setIsMuted(!isMuted)}
                  className={`p-1.5 rounded-lg border text-xs transition cursor-pointer flex items-center gap-1 ${
                    isMuted
                      ? "bg-slate-800 border-slate-700 text-slate-400"
                      : "bg-teal-950/60 border-teal-800 text-teal-300"
                  }`}
                  title={isMuted ? "Audio muted" : "Audio responses enabled"}
                >
                  {isMuted ? <VolumeX className="w-3.5 h-3.5" /> : <Volume2 className="w-3.5 h-3.5" />}
                  <span className="hidden sm:inline">{isMuted ? "Muted" : "Voice On"}</span>
                </button>

                {/* Reset Conversation */}
                <button
                  onClick={handleResetConversation}
                  className="text-slate-400 hover:text-slate-200 transition font-mono flex items-center gap-1 cursor-pointer"
                  title="Clear conversation history"
                >
                  <RefreshCw className="w-3.5 h-3.5" />
                  <span className="hidden sm:inline">Reset</span>
                </button>
              </div>
            </div>

            {/* Message Stream Area */}
            <div className="p-6 space-y-4 max-h-[460px] min-h-[280px] overflow-y-auto scrollbar-thin scrollbar-thumb-slate-700">
              {/* Persistent Welcoming Reception Message */}
              <div className="flex flex-col items-start space-y-2 animate-in fade-in">
                <div className="flex items-center gap-2 text-[10px] text-slate-400 font-mono">
                  <span>MediVoice AI</span>
                  <span>•</span>
                  <span className="px-1.5 py-0.5 rounded bg-slate-800 text-teal-300 border border-slate-700">
                    reception
                  </span>
                </div>
                <div className="max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-relaxed bg-slate-950 border border-slate-800 text-slate-200 rounded-bl-none shadow-md">
                  <p>{getWelcomeText(lang)}</p>
                </div>
              </div>

              {messages.map((msg) => (
                <div
                  key={msg.id}
                  className={`flex flex-col ${
                    msg.sender === "user" ? "items-end" : "items-start"
                  } space-y-2 animate-in fade-in`}
                >
                  <div className="flex items-center gap-2 text-[10px] text-slate-400 font-mono">
                    <span>{msg.sender === "user" ? "You" : "MediVoice AI"}</span>
                    <span>•</span>
                    <span>{msg.timestamp}</span>
                    {msg.intent && (
                      <span className="px-1.5 py-0.5 rounded bg-slate-800 text-teal-300 border border-slate-700">
                        {msg.intent}
                      </span>
                    )}
                  </div>

                  <div
                    className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${
                      msg.sender === "user"
                        ? "bg-teal-600 text-white rounded-br-none shadow-md shadow-teal-900/20"
                        : msg.isError
                        ? "bg-rose-950/60 border border-rose-800 text-rose-200 rounded-bl-none"
                        : "bg-slate-950 border border-slate-800 text-slate-200 rounded-bl-none shadow-md"
                    }`}
                  >
                    <p>{msg.text}</p>

                    {/* Action Card: Doctors List */}
                    {msg.actionResult?.doctors && (
                      <div className="mt-3 pt-3 border-t border-slate-800/80 space-y-2">
                        <span className="text-xs font-semibold text-teal-300 block">
                          Available Specialists:
                        </span>
                        <div className="grid grid-cols-1 gap-2">
                          {msg.actionResult.doctors.map((doc) => (
                            <div
                              key={doc.id}
                              className="p-2.5 rounded-xl bg-slate-900 border border-slate-800 flex items-center justify-between gap-2"
                            >
                              <div>
                                <h4 className="font-semibold text-white text-xs">{doc.name}</h4>
                                <p className="text-[11px] text-slate-400">
                                  {doc.specialty} • Room {doc.room_number} • Fee: ₹{doc.consultation_fee}
                                </p>
                              </div>
                              <button
                                onClick={() =>
                                  handleSendMessage(`Check availability for ${doc.name} tomorrow`)
                                }
                                className="px-2.5 py-1 rounded-lg bg-teal-700 hover:bg-teal-600 text-white text-[11px] font-medium transition cursor-pointer shrink-0"
                              >
                                View Slots
                              </button>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Action Card: Available Slots */}
                    {msg.actionResult?.available_slots && msg.actionResult.available_slots.length > 0 && (
                      <div className="mt-3 pt-3 border-t border-slate-800/80 space-y-2">
                        <span className="text-xs font-semibold text-teal-300 block">
                          Select Consultation Slot ({msg.actionResult.date}):
                        </span>
                        <div className="flex flex-wrap gap-1.5">
                          {msg.actionResult.available_slots.map((slot) => (
                            <button
                              key={slot}
                              onClick={() => handleSendMessage(`Book ${slot}`)}
                              className="px-2.5 py-1 rounded-lg bg-slate-900 hover:bg-teal-700 border border-slate-700 hover:border-teal-500 text-teal-300 hover:text-white text-xs font-mono transition cursor-pointer"
                            >
                              {slot}
                            </button>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Action Card: Pending Confirmation Dialog */}
                    {msg.pendingAction && (
                      <div className="mt-3 p-3 rounded-xl bg-amber-950/40 border border-amber-800/80 space-y-2.5">
                        <div className="flex items-center gap-2 text-amber-300 font-semibold text-xs">
                          <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
                          <span>Appointment Confirmation Required</span>
                        </div>
                        <div className="text-xs text-slate-300 font-mono space-y-0.5">
                          <p>Doctor: {msg.pendingAction.doctor_name}</p>
                          <p>
                            Date & Time: {msg.pendingAction.date} at {msg.pendingAction.time}
                          </p>
                        </div>
                        <div className="flex items-center gap-2 pt-1">
                          <button
                            onClick={() => handleSendMessage("", msg.pendingAction)}
                            className="px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold transition flex items-center gap-1.5 cursor-pointer shadow-md"
                          >
                            <CheckCircle2 className="w-3.5 h-3.5" />
                            <span>Confirm Booking</span>
                          </button>
                          <button
                            onClick={() => {
                              handleSendMessage("I want to change the slot")
                            }}
                            className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium transition cursor-pointer"
                          >
                            Change Slot
                          </button>
                        </div>
                      </div>
                    )}

                    {/* Action Card: Confirmed Appointment Pass */}
                    {msg.actionResult?.booking_reference && msg.actionResult?.status === "booked" && (
                      <div className="mt-3 p-3.5 rounded-xl bg-emerald-950/40 border-2 border-emerald-700/80 space-y-2">
                        <div className="flex items-center justify-between text-xs text-emerald-300 font-semibold">
                          <span className="flex items-center gap-1.5">
                            <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                            Confirmed Outpatient Pass
                          </span>
                          <span className="font-mono bg-emerald-900/60 px-2 py-0.5 rounded border border-emerald-600">
                            {msg.actionResult.booking_reference}
                          </span>
                        </div>
                        <div className="grid grid-cols-2 gap-2 text-[11px] text-slate-300 font-mono pt-1">
                          <div>
                            <span className="text-slate-400 block">Doctor</span>
                            <span>{msg.actionResult.doctor_name}</span>
                          </div>
                          <div>
                            <span className="text-slate-400 block">Slot</span>
                            <span>
                              {msg.actionResult.appointment_date} @ {msg.actionResult.start_time}
                            </span>
                          </div>
                          <div>
                            <span className="text-slate-400 block">Queue Token</span>
                            <span className="text-emerald-300 font-bold">
                              {msg.actionResult.queue_token || "OPD Check-in"}
                            </span>
                          </div>
                          <div>
                            <span className="text-slate-400 block">Department</span>
                            <span>{msg.actionResult.department_name}</span>
                          </div>
                        </div>
                        <button
                          onClick={() => navigate("/appointments")}
                          className="w-full mt-2 py-1.5 rounded-lg bg-emerald-800 hover:bg-emerald-700 text-white text-xs font-semibold flex items-center justify-center gap-1 cursor-pointer transition"
                        >
                          <span>View in My Appointments</span>
                          <ArrowRight className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    )}

                    {/* Action Card: Emergency Escalation Banner */}
                    {msg.actionResult?.emergency && (
                      <div className="mt-3 p-3 rounded-xl bg-rose-950/60 border-2 border-rose-700 text-xs space-y-2">
                        <div className="flex items-center gap-1.5 font-bold text-rose-300 uppercase tracking-wider">
                          <ShieldAlert className="w-4 h-4 text-rose-400 animate-pulse" />
                          <span>Emergency Notification Dispatched</span>
                        </div>
                        <p className="text-slate-300">
                          A priority clinical triage alert has been sent to the on-duty hospital triage team.
                        </p>
                        <div className="pt-1 flex flex-wrap gap-2">
                          <a
                            href={`tel:${msg.actionResult.ambulance_number || 108}`}
                            className="px-3 py-1.5 rounded-lg bg-rose-600 hover:bg-rose-500 text-white font-bold flex items-center gap-1.5 transition shadow"
                          >
                            <PhoneCall className="w-3.5 h-3.5" />
                            <span>Call {msg.actionResult.ambulance_number || 108}</span>
                          </a>
                          <a
                            href={`tel:${msg.actionResult.emergency_phone || ""}`}
                            className="px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-700 text-slate-200 hover:text-white flex items-center gap-1.5 transition"
                          >
                            <span>Casualty Desk</span>
                          </a>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              ))}

              {/* Live Transcribing Bubble */}
              {liveTranscript && (
                <div className="flex flex-col items-end space-y-1 animate-pulse">
                  <div className="text-[10px] text-teal-400 font-mono">Recognizing speech...</div>
                  <div className="max-w-[85%] rounded-2xl rounded-br-none px-4 py-2.5 bg-teal-900/40 border border-teal-700/60 text-teal-200 text-sm">
                    {liveTranscript}
                  </div>
                </div>
              )}

              {/* Speaking Indicator */}
              {voiceState === "speaking" && (
                <div className="flex items-center justify-between p-2 rounded-xl bg-emerald-950/40 border border-emerald-800 text-emerald-300 text-xs">
                  <div className="flex items-center gap-2">
                    <Volume2 className="w-4 h-4 animate-bounce" />
                    <span>MediVoice is speaking response...</span>
                  </div>
                  <button
                    onClick={handleStopSpeaking}
                    className="px-2 py-0.5 rounded bg-emerald-900 hover:bg-emerald-800 text-white text-[11px] font-mono cursor-pointer"
                  >
                    Stop Audio
                  </button>
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>

            {/* Error Notification Banner */}
            {errorMessage && (
              <div className="mx-6 mb-2 p-3 rounded-xl bg-rose-950/70 border border-rose-800 text-xs text-rose-300 flex items-start gap-2">
                <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
                <span className="leading-tight">{errorMessage}</span>
              </div>
            )}

            {/* Central Controls: Animated Audio Waveform & Speech Button */}
            <div className="p-6 bg-slate-950/80 border-t border-slate-800 space-y-5">
              <div className="flex flex-col items-center space-y-3">
                {/* Waveform Visualization */}
                <div className="w-full max-w-xs h-10 flex items-center justify-center">
                  <AudioWaveform
                    active={
                      voiceState === "listening" ||
                      voiceState === "transcribing" ||
                      voiceState === "speaking"
                    }
                    barCount={20}
                  />
                </div>

                {/* Primary Mic Action Button */}
                <div className="relative">
                  {(voiceState === "listening" || voiceState === "transcribing") && (
                    <div className="absolute inset-0 rounded-full bg-teal-500/20 animate-ping" />
                  )}
                  <button
                    onClick={() => {
                      if (voiceState === "listening" || voiceState === "transcribing") {
                        handleStopVoiceRecording()
                      } else if (voiceState === "speaking") {
                        handleStopSpeaking()
                      } else {
                        handleStartVoiceRecording()
                      }
                    }}
                    disabled={voiceState === "processing"}
                    className={`relative w-20 h-20 rounded-full flex flex-col items-center justify-center transition-all duration-300 shadow-xl cursor-pointer ${
                      voiceState === "listening" || voiceState === "transcribing"
                        ? "bg-gradient-to-tr from-teal-500 to-cyan-500 text-white ring-4 ring-teal-400/30 scale-105"
                        : voiceState === "processing"
                        ? "bg-amber-600 text-white opacity-80 cursor-wait"
                        : voiceState === "speaking"
                        ? "bg-emerald-600 hover:bg-emerald-500 text-white ring-4 ring-emerald-500/20"
                        : "bg-slate-800 hover:bg-teal-700 text-teal-400 hover:text-white border border-slate-700 hover:border-teal-500"
                    }`}
                    aria-label={
                      voiceState === "listening"
                        ? "Stop listening"
                        : voiceState === "speaking"
                        ? "Stop audio playback"
                        : "Start microphone voice recording"
                    }
                  >
                    {voiceState === "listening" || voiceState === "transcribing" ? (
                      <MicOff className="w-8 h-8" />
                    ) : voiceState === "processing" ? (
                      <RefreshCw className="w-7 h-7 animate-spin" />
                    ) : voiceState === "speaking" ? (
                      <VolumeX className="w-8 h-8" />
                    ) : (
                      <Mic className="w-8 h-8" />
                    )}
                    <span className="text-[10px] font-mono tracking-tight font-semibold mt-0.5">
                      {voiceState === "listening" || voiceState === "transcribing"
                        ? "STOP"
                        : voiceState === "processing"
                        ? "WAIT"
                        : voiceState === "speaking"
                        ? "MUTE"
                        : "SPEAK"}
                    </span>
                  </button>
                </div>

                <div className="text-center text-xs text-slate-400 font-medium">
                  {voiceState === "listening"
                    ? "Listening... Speak clearly into your microphone"
                    : voiceState === "transcribing"
                    ? "Transcribing your voice query..."
                    : voiceState === "processing"
                    ? "Matching clinical directories & checking schedules..."
                    : voiceState === "speaking"
                    ? "Speaking response... Tap MUTE to cancel speech"
                    : isSpeechSupported
                    ? `Tap to speak in ${lang === "ta" ? "Tamil" : lang === "hi" ? "Hindi" : "English"}`
                    : "Browser speech recognition unavailable. Use typed input below."}
                </div>
              </div>

              {/* Typed Input Alternative */}
              <form
                onSubmit={(e) => {
                  e.preventDefault()
                  if (typedInput.trim()) {
                    handleSendMessage(typedInput)
                  }
                }}
                className="flex items-center gap-2"
              >
                <input
                  type="text"
                  value={typedInput}
                  onChange={(e) => setTypedInput(e.target.value)}
                  placeholder={
                    lang === "ta"
                      ? "அல்லது உங்கள் கேள்வியை இங்கே தட்டச்சு செய்யவும் (எ.கா. இதய மருத்துவர்)..."
                      : lang === "hi"
                      ? "या अपना प्रश्न यहाँ लिखें (उदा. हृदय रोग विशेषज्ञ)..."
                      : "Or type your request here (e.g., 'Book Dr. Sharma tomorrow at 10:00')..."
                  }
                  className="flex-1 px-4 py-2.5 rounded-xl bg-slate-900 border border-slate-800 focus:border-teal-500 focus:ring-1 focus:ring-teal-500 text-sm text-slate-200 placeholder-slate-500 outline-none transition"
                />
                <button
                  type="submit"
                  disabled={!typedInput.trim() || voiceState === "processing"}
                  className="px-4 py-2.5 rounded-xl bg-teal-600 hover:bg-teal-500 disabled:opacity-40 disabled:cursor-not-allowed text-white text-xs font-semibold flex items-center gap-1.5 transition cursor-pointer shadow"
                >
                  <span>Send</span>
                  <Send className="w-3.5 h-3.5" />
                </button>
              </form>

              {/* Sample Quick Demo Queries */}
              <div className="space-y-2 pt-2 border-t border-slate-800/80">
                <span className="text-xs text-slate-400 block font-medium">
                  {t.voice.sampleQueriesLabel}
                </span>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-left">
                  {(VOICE_PROMPT_SUGGESTIONS[lang] || VOICE_PROMPT_SUGGESTIONS.en).map((q) => (
                    <button
                      key={q.id}
                      onClick={() => handleSendMessage(q.text)}
                      className="px-3 py-2 rounded-xl bg-slate-900/90 hover:bg-slate-800 border border-slate-800 hover:border-teal-700/60 text-xs text-slate-300 hover:text-white transition flex items-center justify-between gap-2 text-left cursor-pointer group"
                    >
                      <span className="truncate">&ldquo;{q.text}&rdquo;</span>
                      <Sparkles className="w-3.5 h-3.5 text-teal-400 shrink-0 opacity-70 group-hover:opacity-100" />
                    </button>
                  ))}
                </div>
              </div>

              {/* Privacy Notice & Capabilities */}
              <div className="flex flex-col sm:flex-row items-center justify-between gap-2 text-[11px] text-slate-500 pt-1">
                <div className="flex items-center gap-1.5">
                  <Lock className="w-3 h-3 text-teal-500 shrink-0" />
                  <span>Microphone audio is processed on-demand and never stored.</span>
                </div>
                <div className="flex items-center gap-1 text-slate-400">
                  <HelpCircle className="w-3 h-3" />
                  <span>
                    Mode:{" "}
                    {assistantConfig?.gemini_available
                      ? "Gemini AI Connected"
                      : "Clinical Fallback Engine"}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Quick Action Reception Cards */}
      <section className="max-w-6xl mx-auto px-4 sm:px-6">
        <div className="mb-6">
          <h2 className="text-xl font-bold text-white tracking-tight">
            {t.quickActions.title}
          </h2>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {/* Card 1: Book Consultation */}
          <div
            onClick={() => navigate("/doctors")}
            className="group p-5 rounded-2xl bg-slate-900/60 border border-slate-800 hover:border-teal-700/70 hover:bg-slate-900 transition-all cursor-pointer flex flex-col justify-between space-y-4"
          >
            <div className="space-y-3">
              <div className="w-10 h-10 rounded-xl bg-teal-950 border border-teal-800 flex items-center justify-center text-teal-400 group-hover:scale-110 transition">
                <Calendar className="w-5 h-5" />
              </div>
              <h3 className="font-semibold text-white text-base group-hover:text-teal-300 transition">
                {t.quickActions.bookAppointment}
              </h3>
              <p className="text-xs text-slate-400 leading-relaxed">
                {t.quickActions.bookDesc}
              </p>
            </div>
            <div className="flex items-center text-xs text-teal-400 font-medium gap-1">
              <span>View On-Duty Doctors</span>
              <ArrowRight className="w-3.5 h-3.5 group-hover:translate-x-1 transition" />
            </div>
          </div>

          {/* Card 2: Find a Doctor */}
          <div
            onClick={() => navigate("/doctors")}
            className="group p-5 rounded-2xl bg-slate-900/60 border border-slate-800 hover:border-blue-700/70 hover:bg-slate-900 transition-all cursor-pointer flex flex-col justify-between space-y-4"
          >
            <div className="space-y-3">
              <div className="w-10 h-10 rounded-xl bg-blue-950 border border-blue-800 flex items-center justify-center text-blue-400 group-hover:scale-110 transition">
                <Users className="w-5 h-5" />
              </div>
              <h3 className="font-semibold text-white text-base group-hover:text-blue-300 transition">
                {t.quickActions.findDoctor}
              </h3>
              <p className="text-xs text-slate-400 leading-relaxed">
                {t.quickActions.findDesc}
              </p>
            </div>
            <div className="flex items-center text-xs text-blue-400 font-medium gap-1">
              <span>Search Directory</span>
              <ArrowRight className="w-3.5 h-3.5 group-hover:translate-x-1 transition" />
            </div>
          </div>

          {/* Card 3: Hospital Departments */}
          <div
            onClick={() => navigate("/departments")}
            className="group p-5 rounded-2xl bg-slate-900/60 border border-slate-800 hover:border-cyan-700/70 hover:bg-slate-900 transition-all cursor-pointer flex flex-col justify-between space-y-4"
          >
            <div className="space-y-3">
              <div className="w-10 h-10 rounded-xl bg-cyan-950 border border-cyan-800 flex items-center justify-center text-cyan-400 group-hover:scale-110 transition">
                <Building2 className="w-5 h-5" />
              </div>
              <h3 className="font-semibold text-white text-base group-hover:text-cyan-300 transition">
                {t.quickActions.departments}
              </h3>
              <p className="text-xs text-slate-400 leading-relaxed">
                {t.quickActions.departmentsDesc}
              </p>
            </div>
            <div className="flex items-center text-xs text-cyan-400 font-medium gap-1">
              <span>Hospital Wayfinding</span>
              <ArrowRight className="w-3.5 h-3.5 group-hover:translate-x-1 transition" />
            </div>
          </div>

          {/* Card 4: My Appointments */}
          <div
            onClick={() => navigate("/appointments")}
            className="group p-5 rounded-2xl bg-slate-900/60 border border-slate-800 hover:border-emerald-700/70 hover:bg-slate-900 transition-all cursor-pointer flex flex-col justify-between space-y-4"
          >
            <div className="space-y-3">
              <div className="w-10 h-10 rounded-xl bg-emerald-950 border border-emerald-800 flex items-center justify-center text-emerald-400 group-hover:scale-110 transition">
                <Clock className="w-5 h-5" />
              </div>
              <h3 className="font-semibold text-white text-base group-hover:text-emerald-300 transition">
                {t.quickActions.myAppointments}
              </h3>
              <p className="text-xs text-slate-400 leading-relaxed">
                {t.quickActions.myAppointmentsDesc}
              </p>
            </div>
            <div className="flex items-center text-xs text-emerald-400 font-medium gap-1">
              <span>Check Queue & Token</span>
              <ArrowRight className="w-3.5 h-3.5 group-hover:translate-x-1 transition" />
            </div>
          </div>
        </div>
      </section>

      {/* Specialty Departments Preview */}
      <section className="max-w-6xl mx-auto px-4 sm:px-6">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 mb-6">
          <div>
            <h2 className="text-xl font-bold text-white tracking-tight">
              {t.departmentsSection.title}
            </h2>
            <p className="text-xs text-slate-400 mt-0.5">
              {t.departmentsSection.subtitle}
            </p>
          </div>
          <button
            onClick={() => navigate("/departments")}
            className="text-xs font-semibold text-teal-400 hover:text-teal-300 flex items-center gap-1 cursor-pointer"
          >
            <span>{t.departmentsSection.viewAll}</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {departments.slice(0, 6).map((dept) => (
            <div
              key={dept.id}
              className="p-5 rounded-2xl bg-slate-900/40 border border-slate-800 hover:border-slate-700 transition space-y-3"
            >
              <div className="flex items-center justify-between">
                <span className="font-mono text-xs px-2 py-0.5 rounded bg-slate-800 text-teal-300 border border-slate-700">
                  {dept.code}
                </span>
                <span className="text-xs text-slate-400 flex items-center gap-1">
                  <Clock className="w-3 h-3 text-slate-500" />
                  Floor {dept.floor}
                </span>
              </div>
              <h3 className="font-semibold text-white text-base">{dept.name}</h3>
              <p className="text-xs text-slate-400 line-clamp-2 leading-relaxed">
                {dept.description}
              </p>
              <div className="pt-2 border-t border-slate-800/80 flex items-center justify-between text-[11px] text-slate-400">
                <span>{dept.location}</span>
                <span className="text-teal-400 font-mono">Ext: {dept.extension}</span>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Clearly Differentiated Emergency Assistance Panel */}
      <section className="max-w-6xl mx-auto px-4 sm:px-6">
        <div className="relative rounded-3xl bg-rose-950/30 border-2 border-rose-800/80 p-6 sm:p-8 overflow-hidden shadow-xl shadow-rose-950/20">
          <div className="absolute top-0 right-0 w-64 h-64 bg-rose-500/5 rounded-full blur-3xl pointer-events-none" />

          <div className="relative flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
            <div className="space-y-3 max-w-2xl">
              <Badge variant="rose" size="sm" dot>
                {t.emergency.badge}
              </Badge>
              <h2 className="text-2xl font-bold text-white tracking-tight">
                {t.emergency.title}
              </h2>
              <p className="text-xs sm:text-sm text-slate-300 leading-relaxed">
                {t.emergency.description}
              </p>
              <div className="flex flex-wrap gap-4 text-xs font-mono text-rose-300 pt-1">
                <span>{t.emergency.wing}</span>
                <span>•</span>
                <span>{t.emergency.casualtyLine}</span>
              </div>
            </div>

            <div className="flex flex-col sm:flex-row md:flex-col gap-3 w-full sm:w-auto shrink-0">
              <a
                href="tel:108"
                onClick={handleImmediateEmergency}
                className="px-6 py-3 rounded-xl bg-rose-600 hover:bg-rose-500 text-white font-bold text-xs uppercase tracking-wider flex items-center justify-center gap-2 shadow-lg shadow-rose-600/30 transition cursor-pointer"
              >
                <PhoneCall className="w-4 h-4" />
                <span>{t.emergency.callEmergency}</span>
              </a>
              <button
                onClick={() => navigate("/departments")}
                className="px-5 py-2.5 rounded-xl bg-slate-900/80 hover:bg-slate-800 text-slate-200 border border-slate-700 text-xs font-semibold flex items-center justify-center gap-2 transition cursor-pointer"
              >
                <span>Casualty Wayfinding Map</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        </div>
      </section>
    </div>
  )
}
