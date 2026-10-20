export default function Logo({ size = "md", showSubtitle = true, light = false }) {
  const isSm = size === "sm"
  const isLg = size === "lg"

  return (
    <div className="flex items-center gap-3 select-none">
      <div
        className={`relative flex items-center justify-center rounded-xl bg-gradient-to-tr from-teal-500 via-cyan-500 to-blue-600 shadow-md shadow-teal-500/20 text-white shrink-0 ${
          isSm ? "w-8 h-8" : isLg ? "w-11 h-11" : "w-9 h-9"
        }`}
      >
        {/* SVG medical cross + voice soundwave emblem */}
        <svg
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2.2"
          strokeLinecap="round"
          strokeLinejoin="round"
          className={isSm ? "w-4 h-4" : isLg ? "w-6 h-6" : "w-5 h-5"}
        >
          {/* Medical Cross Foundation */}
          <path d="M12 4v16" stroke="rgba(255,255,255,0.4)" strokeWidth="2" />
          <path d="M4 12h16" stroke="rgba(255,255,255,0.4)" strokeWidth="2" />
          {/* Pulse / Waveform Overlay */}
          <path d="M3 12h3l2-4 3 8 3-7 2 5 2-2h3" stroke="white" strokeWidth="2.2" />
        </svg>

        {/* Ambient indicator dot */}
        <span className="absolute -top-1 -right-1 w-2.5 h-2.5 rounded-full bg-emerald-400 ring-2 ring-slate-950 animate-pulse" />
      </div>

      <div className="flex flex-col">
        <div className="flex items-center gap-1.5 leading-none">
          <span
            className={`font-bold tracking-tight ${
              light ? "text-slate-900" : "text-white"
            } ${isSm ? "text-base" : isLg ? "text-2xl" : "text-lg"}`}
          >
            Medi<span className="text-teal-400">Voice</span>
          </span>
          <span className="text-[10px] uppercase font-mono tracking-wider font-semibold px-1.5 py-0.5 rounded bg-teal-500/10 text-teal-400 border border-teal-500/20">
            AI Triage
          </span>
        </div>
        {showSubtitle && (
          <span
            className={`text-[11px] font-medium tracking-tight mt-0.5 ${
              light ? "text-slate-500" : "text-slate-400"
            }`}
          >
            Virtual Hospital Receptionist
          </span>
        )}
      </div>
    </div>
  )
}
