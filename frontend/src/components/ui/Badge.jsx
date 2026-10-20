export default function Badge({
  variant = "default",
  size = "sm",
  children,
  dot = false,
  className = "",
}) {
  const variantStyles = {
    default: "bg-slate-800 text-slate-300 border-slate-700",
    teal: "bg-teal-950/60 text-teal-300 border-teal-800/80",
    emerald: "bg-emerald-950/60 text-emerald-300 border-emerald-800/80",
    amber: "bg-amber-950/60 text-amber-300 border-amber-800/80",
    rose: "bg-rose-950/60 text-rose-300 border-rose-800/80",
    cyan: "bg-cyan-950/60 text-cyan-300 border-cyan-800/80",
    blue: "bg-blue-950/60 text-blue-300 border-blue-800/80",
  }

  const dotColors = {
    default: "bg-slate-400",
    teal: "bg-teal-400",
    emerald: "bg-emerald-400",
    amber: "bg-amber-400",
    rose: "bg-rose-400",
    cyan: "bg-cyan-400",
    blue: "bg-blue-400",
  }

  const sizeStyles = {
    xs: "text-[10px] px-1.5 py-0.5 font-mono",
    sm: "text-xs px-2.5 py-0.5",
    md: "text-xs px-3 py-1 font-medium",
  }

  const chosenVariant = variantStyles[variant] || variantStyles.default
  const chosenDot = dotColors[variant] || dotColors.default
  const chosenSize = sizeStyles[size] || sizeStyles.sm

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border font-medium ${chosenVariant} ${chosenSize} ${className}`}
    >
      {dot && <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${chosenDot}`} />}
      {children}
    </span>
  )
}
