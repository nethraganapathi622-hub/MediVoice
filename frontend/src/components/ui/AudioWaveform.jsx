export default function AudioWaveform({ active = false, barCount = 18 }) {
  // Heights in percentage when resting
  const restingHeights = [18, 28, 42, 60, 35, 75, 45, 90, 55, 80, 40, 65, 30, 85, 48, 25, 38, 20]

  return (
    <div className="flex items-center justify-center gap-1.5 h-14 px-4 py-2 select-none" aria-hidden="true">
      <style>{`
        @keyframes wavePulse {
          0%, 100% {
            transform: scaleY(0.25);
            opacity: 0.45;
          }
          50% {
            transform: scaleY(1);
            opacity: 1;
          }
        }
        @media (prefers-reduced-motion: reduce) {
          .waveform-bar {
            animation: none !important;
            transform: scaleY(0.5) !important;
          }
        }
      `}</style>

      {Array.from({ length: barCount }).map((_, index) => {
        const height = restingHeights[index % restingHeights.length]
        const delay = (index * 0.08).toFixed(2)
        const duration = (0.7 + (index % 5) * 0.15).toFixed(2)

        return (
          <div
            key={index}
            className={`waveform-bar w-1 rounded-full bg-gradient-to-t from-teal-500 to-cyan-300 transition-all duration-300 ${
              active ? "origin-center" : "opacity-30"
            }`}
            style={{
              height: `${height}%`,
              animation: active
                ? `wavePulse ${duration}s ease-in-out ${delay}s infinite alternate`
                : "none",
            }}
          />
        )
      })}
    </div>
  )
}
