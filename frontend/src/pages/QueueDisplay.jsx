import { useState, useEffect, useCallback, useRef } from "react"
import {
  Volume2,
  VolumeX,
  Maximize2,
  Minimize2,
  Clock,
  Building2,
  User,
  Radio,
  ArrowRight,
  Sparkles,
  Layers,
  Activity,
} from "lucide-react"
import { getQueue, getDepartments } from "../services/api"
import { useWebSocketEvent } from "../hooks/useWebSocket"

// Web Audio API soft hospital alert chime
function playChime() {
  try {
    const AudioContext = window.AudioContext || window.webkitAudioContext
    if (!AudioContext) return
    const ctx = new AudioContext()
    const now = ctx.currentTime

    // Two-tone chime (F5 -> A5)
    const osc1 = ctx.createOscillator()
    const osc2 = ctx.createOscillator()
    const gain = ctx.createGain()

    osc1.type = "sine"
    osc1.frequency.setValueAtTime(698.46, now) // F5
    osc1.frequency.exponentialRampToValueAtTime(880.0, now + 0.25) // A5

    osc2.type = "triangle"
    osc2.frequency.setValueAtTime(880.0, now + 0.25)

    gain.gain.setValueAtTime(0.3, now)
    gain.gain.exponentialRampToValueAtTime(0.001, now + 0.8)

    osc1.connect(gain)
    osc2.connect(gain)
    gain.connect(ctx.destination)

    osc1.start(now)
    osc1.stop(now + 0.8)
    osc2.start(now + 0.25)
    osc2.stop(now + 0.8)
  } catch (err) {
    console.debug("Audio chime suppressed:", err)
  }
}

export default function QueueDisplay() {
  const [queue, setQueue] = useState([])
  const [departments, setDepartments] = useState([])
  const [selectedDept, setSelectedDept] = useState("all")
  const [nowCalling, setNowCalling] = useState(null)
  const [audioEnabled, setAudioEnabled] = useState(true)
  const [audioLang, setAudioLang] = useState("all") // 'en', 'ta', 'hi', or 'all'
  const [isFullscreen, setIsFullscreen] = useState(false)
  const [currentTime, setCurrentTime] = useState(new Date())

  const speechQueueRef = useRef([])
  const isSpeakingRef = useRef(false)

  // Live digital clock
  useEffect(() => {
    const timer = setInterval(() => setCurrentTime(new Date()), 1000)
    return () => clearInterval(timer)
  }, [])

  // Load initial queue & departments
  const loadData = useCallback(async () => {
    try {
      const [qData, dData] = await Promise.all([
        getQueue(),
        getDepartments().catch(() => []),
      ])
      setQueue(qData)
      setDepartments(dData)

      // Find the most recently called token
      const called = qData
        .filter((entry) => entry.status === "called")
        .sort((a, b) => new Date(b.called_time || 0) - new Date(a.called_time || 0))[0]

      if (called) {
        setNowCalling({
          token: called.token,
          doctorName: called.appointment?.doctor?.name || "Attending Specialist",
          roomNumber: called.appointment?.doctor?.room_number || "OPD Room",
          departmentName: called.appointment?.department?.name || "General OPD",
          calledTime: called.called_time,
        })
      }
    } catch (err) {
      console.error("Failed to load kiosk queue data:", err)
    }
  }, [])

  useEffect(() => {
    const timer = setTimeout(() => {
      loadData()
    }, 150)
    return () => clearTimeout(timer)
  }, [loadData])

  // Speech announcement queue processor
  const processNextRef = useRef(null)

  const processSpeechQueue = useCallback(() => {
    if (!audioEnabled || !("speechSynthesis" in window)) return
    if (isSpeakingRef.current || speechQueueRef.current.length === 0) return

    const item = speechQueueRef.current.shift()
    isSpeakingRef.current = true

    playChime()

    setTimeout(() => {
      const u = new SpeechSynthesisUtterance(item.text)
      u.lang = item.lang
      u.rate = 0.95
      u.pitch = 1.05

      u.onend = () => {
        isSpeakingRef.current = false
        if (processNextRef.current) {
          setTimeout(processNextRef.current, 400)
        }
      }
      u.onerror = () => {
        isSpeakingRef.current = false
        if (processNextRef.current) {
          setTimeout(processNextRef.current, 300)
        }
      }

      window.speechSynthesis.speak(u)
    }, 450)
  }, [audioEnabled])

  useEffect(() => {
    processNextRef.current = processSpeechQueue
  }, [processSpeechQueue])

  const announceToken = useCallback(
    (token, roomNumber, doctorName, departmentName) => {
      if (!audioEnabled || !("speechSynthesis" in window)) return

      const deptSuffix = departmentName ? ` for ${departmentName}` : ""
      const docSuffix = doctorName ? ` with ${doctorName}` : ""

      // English announcement
      const enText = `Token ${token.split("-").join(" ")}, please proceed to ${roomNumber || "the consultation room"}${deptSuffix}${docSuffix}.`

      // Tamil announcement
      const taText = `டோக்கன் ${token}, தயவுசெய்து அறை எண் ${roomNumber || "ஆலோசனை அறைக்கு"} செல்லவும்.`

      // Hindi announcement
      const hiText = `टोकन ${token}, कृपया कमरा नंबर ${roomNumber || "परामर्श कक्ष"} में जाएं।`

      speechQueueRef.current = [] // Prioritize newest token
      window.speechSynthesis.cancel()

      if (audioLang === "en") {
        speechQueueRef.current.push({ text: enText, lang: "en-US" })
      } else if (audioLang === "ta") {
        speechQueueRef.current.push({ text: taText, lang: "ta-IN" })
      } else if (audioLang === "hi") {
        speechQueueRef.current.push({ text: hiText, lang: "hi-IN" })
      } else {
        // Multilingual cycling: English followed by Tamil
        speechQueueRef.current.push({ text: enText, lang: "en-US" })
        speechQueueRef.current.push({ text: taText, lang: "ta-IN" })
      }

      processSpeechQueue()
    },
    [audioEnabled, audioLang, processSpeechQueue]
  )

  // Real-time WebSocket handlers
  useWebSocketEvent("queue.patient_called", (payload) => {
    loadData()
    setNowCalling({
      token: payload.token,
      doctorName: payload.doctor_name || "Attending Specialist",
      roomNumber: payload.room_number || "OPD Room",
      departmentName: payload.department_name || "General OPD",
      calledTime: payload.called_time || new Date().toISOString(),
    })

    announceToken(
      payload.token,
      payload.room_number,
      payload.doctor_name,
      payload.department_name
    )
  })

  useWebSocketEvent("queue.checked_in", () => loadData())
  useWebSocketEvent("queue.completed", () => loadData())

  const toggleFullscreen = () => {
    if (!document.fullscreenElement) {
      document.documentElement.requestFullscreen().then(() => setIsFullscreen(true)).catch(() => {})
    } else {
      document.exitFullscreen().then(() => setIsFullscreen(false)).catch(() => {})
    }
  }

  // Filtered lists
  const filteredQueue = queue.filter((entry) => {
    if (selectedDept !== "all" && entry.appointment?.department_id !== parseInt(selectedDept, 10)) {
      return false
    }
    return true
  })

  const waitingTokens = filteredQueue.filter((e) => e.status === "waiting")
  const recentCalled = filteredQueue
    .filter((e) => e.status === "called" || e.status === "in-progress")
    .sort((a, b) => new Date(b.called_time || 0) - new Date(a.called_time || 0))
    .slice(0, 6)

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans selection:bg-teal-500/30">
      {/* Top Header Bar */}
      <header className="px-6 py-4 bg-slate-900/90 border-b border-slate-800 flex items-center justify-between backdrop-blur-md sticky top-0 z-20">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-teal-500 to-cyan-600 flex items-center justify-center shadow-lg shadow-teal-500/20">
              <Radio className="w-5 h-5 text-white animate-pulse" />
            </div>
            <div>
              <h1 className="text-xl font-bold tracking-tight text-white flex items-center gap-2">
                <span>MediVoice OPD Token Display</span>
                <span className="px-2 py-0.5 rounded-full text-[10px] uppercase font-semibold tracking-wider bg-teal-500/20 text-teal-300 border border-teal-500/30">
                  Live Kiosk
                </span>
              </h1>
              <p className="text-xs text-slate-400">Outpatient Consultation Waiting Room Kiosk</p>
            </div>
          </div>
        </div>

        {/* Controls: Department filter, Audio toggle, Language, Fullscreen, Clock */}
        <div className="flex items-center gap-3">
          {/* Department Filter */}
          <select
            value={selectedDept}
            onChange={(e) => setSelectedDept(e.target.value)}
            className="bg-slate-800 border border-slate-700 text-xs text-slate-200 rounded-lg px-3 py-2 focus:outline-none focus:border-teal-500"
          >
            <option value="all">All Departments</option>
            {departments.map((d) => (
              <option key={d.id} value={d.id}>
                {d.name}
              </option>
            ))}
          </select>

          {/* Announcement Language */}
          <select
            value={audioLang}
            onChange={(e) => setAudioLang(e.target.value)}
            className="bg-slate-800 border border-slate-700 text-xs text-slate-200 rounded-lg px-3 py-2 focus:outline-none focus:border-teal-500"
          >
            <option value="all">Voice: Multi (EN+TA)</option>
            <option value="en">Voice: English</option>
            <option value="ta">Voice: தமிழ் (Tamil)</option>
            <option value="hi">Voice: हिन्दी (Hindi)</option>
          </select>

          {/* Audio Chime Toggle */}
          <button
            onClick={() => setAudioEnabled(!audioEnabled)}
            className={`p-2.5 rounded-lg border transition flex items-center justify-center cursor-pointer ${
              audioEnabled
                ? "bg-teal-500/20 border-teal-500/40 text-teal-300 hover:bg-teal-500/30"
                : "bg-slate-800 border-slate-700 text-slate-400 hover:bg-slate-700"
            }`}
            title={audioEnabled ? "Mute audio announcements" : "Enable audio announcements"}
          >
            {audioEnabled ? <Volume2 className="w-4 h-4" /> : <VolumeX className="w-4 h-4" />}
          </button>

          {/* Fullscreen Button */}
          <button
            onClick={toggleFullscreen}
            className="p-2.5 rounded-lg border border-slate-700 bg-slate-800 text-slate-300 hover:bg-slate-700 transition cursor-pointer"
            title="Toggle Fullscreen"
          >
            {isFullscreen ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
          </button>

          {/* Digital Clock */}
          <div className="flex items-center gap-2 pl-3 border-l border-slate-800 text-right">
            <Clock className="w-4 h-4 text-teal-400" />
            <div>
              <div className="text-sm font-semibold text-white tracking-wide">
                {currentTime.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })}
              </div>
              <div className="text-[10px] text-slate-400">
                {currentTime.toLocaleDateString([], { weekday: "short", month: "short", day: "numeric" })}
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* Main Kiosk Content */}
      <main className="flex-1 p-6 grid grid-cols-1 lg:grid-cols-12 gap-6 max-w-[1920px] mx-auto w-full">
        {/* Left Column: Now Calling Hero Stage (7 cols) */}
        <section className="lg:col-span-7 flex flex-col gap-6">
          <div className="bg-gradient-to-br from-slate-900 via-slate-900/95 to-teal-950/40 rounded-3xl p-8 border border-teal-500/30 shadow-2xl relative overflow-hidden flex-1 flex flex-col justify-between">
            {/* Ambient background glow */}
            <div className="absolute -top-32 -right-32 w-96 h-96 bg-teal-500/10 rounded-full blur-3xl pointer-events-none" />
            <div className="absolute -bottom-32 -left-32 w-96 h-96 bg-cyan-500/10 rounded-full blur-3xl pointer-events-none" />

            {/* Header Badge */}
            <div className="flex items-center justify-between relative z-10">
              <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-teal-500/20 border border-teal-500/40 text-teal-300 font-semibold text-sm uppercase tracking-wider">
                <span className="w-2.5 h-2.5 rounded-full bg-teal-400 animate-ping" />
                <span>Now Calling / தற்போது அழைக்கப்படுகிறது</span>
              </div>
              <div className="text-xs text-slate-400 flex items-center gap-1.5">
                <Activity className="w-4 h-4 text-teal-400 animate-pulse" />
                <span>Real-Time Consultation Desk</span>
              </div>
            </div>

            {/* Token Hero Section */}
            <div className="py-8 my-auto text-center relative z-10 space-y-4">
              <div className="text-xs uppercase tracking-widest text-slate-400 font-medium">Patient Queue Token</div>
              <div className="text-7xl sm:text-8xl md:text-9xl font-black tracking-tight text-white drop-shadow-[0_0_35px_rgba(20,184,166,0.35)] animate-fade-in font-mono">
                {nowCalling ? nowCalling.token : "WAITING"}
              </div>

              {nowCalling && (
                <div className="pt-4 flex flex-wrap items-center justify-center gap-4 text-slate-300">
                  <div className="px-5 py-2.5 rounded-2xl bg-teal-500/10 border border-teal-500/30 text-teal-300 font-bold text-lg sm:text-xl flex items-center gap-2">
                    <Building2 className="w-5 h-5 text-teal-400" />
                    <span>Proceed to: {nowCalling.roomNumber}</span>
                  </div>
                </div>
              )}
            </div>

            {/* Doctor & Department Meta Strip */}
            {nowCalling ? (
              <div className="grid grid-cols-2 gap-4 pt-6 border-t border-slate-800/80 relative z-10">
                <div className="p-4 rounded-2xl bg-slate-800/60 border border-slate-800">
                  <span className="text-[11px] text-slate-400 uppercase tracking-wider block font-semibold mb-1">
                    Specialist Doctor
                  </span>
                  <div className="text-lg font-bold text-white flex items-center gap-2">
                    <User className="w-4 h-4 text-teal-400 shrink-0" />
                    <span className="truncate">{nowCalling.doctorName}</span>
                  </div>
                </div>

                <div className="p-4 rounded-2xl bg-slate-800/60 border border-slate-800">
                  <span className="text-[11px] text-slate-400 uppercase tracking-wider block font-semibold mb-1">
                    Clinical Department
                  </span>
                  <div className="text-lg font-bold text-white flex items-center gap-2">
                    <Building2 className="w-4 h-4 text-cyan-400 shrink-0" />
                    <span className="truncate">{nowCalling.departmentName}</span>
                  </div>
                </div>
              </div>
            ) : (
              <div className="text-center py-4 text-sm text-slate-500">
                Awaiting staff to call next patient from triage queue.
              </div>
            )}
          </div>
        </section>

        {/* Right Column: Queue Roster & Active Tokens (5 cols) */}
        <section className="lg:col-span-5 flex flex-col gap-6">
          {/* Recently Called Desk Strip */}
          <div className="bg-slate-900/90 rounded-3xl p-6 border border-slate-800 flex flex-col gap-4 shadow-xl">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-bold text-white uppercase tracking-wider flex items-center gap-2">
                <Layers className="w-4 h-4 text-teal-400" />
                <span>Recently Called / சமீபத்திய அழைப்புகள்</span>
              </h2>
              <span className="text-xs text-slate-400">{recentCalled.length} Active</span>
            </div>

            <div className="space-y-2.5">
              {recentCalled.length > 0 ? (
                recentCalled.map((item) => (
                  <div
                    key={item.id}
                    className="p-3.5 rounded-2xl bg-slate-800/80 border border-slate-700/80 flex items-center justify-between hover:border-teal-500/50 transition"
                  >
                    <div className="flex items-center gap-3">
                      <div className="w-12 h-10 rounded-xl bg-teal-500/20 text-teal-300 font-mono font-bold flex items-center justify-center text-sm border border-teal-500/30">
                        {item.token}
                      </div>
                      <div>
                        <div className="text-sm font-semibold text-white">
                          {item.appointment?.doctor?.name || "Consultant"}
                        </div>
                        <div className="text-xs text-slate-400">
                          {item.appointment?.department?.name || "OPD"}
                        </div>
                      </div>
                    </div>

                    <div className="text-right">
                      <div className="px-2.5 py-1 rounded-lg bg-teal-950/80 border border-teal-700/50 text-teal-300 font-semibold text-xs inline-flex items-center gap-1">
                        <span>{item.appointment?.doctor?.room_number || "Room"}</span>
                        <ArrowRight className="w-3 h-3 text-teal-400" />
                      </div>
                      <div className="text-[10px] text-slate-500 pt-0.5">
                        {item.called_time ? new Date(item.called_time).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : ""}
                      </div>
                    </div>
                  </div>
                ))
              ) : (
                <div className="text-center py-6 text-sm text-slate-500 border border-dashed border-slate-800 rounded-2xl">
                  No active consultation calls yet.
                </div>
              )}
            </div>
          </div>

          {/* Up Next in Queue */}
          <div className="bg-slate-900/90 rounded-3xl p-6 border border-slate-800 flex flex-col gap-4 flex-1 shadow-xl">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-bold text-white uppercase tracking-wider flex items-center gap-2">
                <Clock className="w-4 h-4 text-cyan-400" />
                <span>Next in Line / காத்திருக்கும் வரிசை</span>
              </h2>
              <span className="text-xs px-2.5 py-0.5 rounded-full bg-cyan-500/20 text-cyan-300 font-semibold border border-cyan-500/30">
                {waitingTokens.length} Waiting
              </span>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2.5 overflow-y-auto max-h-[380px] pr-1">
              {waitingTokens.length > 0 ? (
                waitingTokens.map((item, idx) => (
                  <div
                    key={item.id}
                    className="p-3 rounded-2xl bg-slate-800/60 border border-slate-800 flex flex-col items-center justify-center text-center gap-1 hover:border-slate-700 transition"
                  >
                    <span className="text-[10px] uppercase font-semibold text-slate-500">
                      Pos #{idx + 1}
                    </span>
                    <span className="text-base font-mono font-bold text-white">{item.token}</span>
                    <span className="text-[10px] text-slate-400 truncate max-w-[120px]">
                      {item.appointment?.department?.name || "General"}
                    </span>
                  </div>
                ))
              ) : (
                <div className="col-span-full text-center py-8 text-sm text-slate-500 border border-dashed border-slate-800 rounded-2xl">
                  Waiting lounge queue is currently clear.
                </div>
              )}
            </div>
          </div>
        </section>
      </main>

      {/* Footer Emergency Ticker */}
      <footer className="px-6 py-2.5 bg-slate-900 border-t border-slate-800/80 text-xs text-slate-400 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Sparkles className="w-3.5 h-3.5 text-teal-400" />
          <span>For emergency assistance, please immediately contact Emergency Desk or Call 108.</span>
        </div>
        <div className="text-[11px] text-slate-500">
          MediVoice Hospital Telemetry System • Automated Multilingual OPD Audio Announcements
        </div>
      </footer>
    </div>
  )
}
