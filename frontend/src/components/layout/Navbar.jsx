import { useState } from "react"
import { Link, useLocation } from "react-router-dom"
import {
  Mic,
  Users,
  Calendar,
  Building2,
  ShieldAlert,
  LayoutDashboard,
  Globe,
  Menu,
  X,
} from "lucide-react"
import Logo from "../ui/Logo"
import LiveApiStatus from "../ui/LiveApiStatus"
import { translations } from "../../services/i18n"

export default function Navbar({ lang = "en", setLang }) {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const location = useLocation()
  const t = translations[lang] || translations.en

  const navLinks = [
    { name: t.nav.assistant, path: "/", icon: Mic },
    { name: t.nav.doctors, path: "/doctors", icon: Users },
    { name: t.nav.appointments, path: "/appointments", icon: Calendar },
    { name: t.nav.departments, path: "/departments", icon: Building2 },
  ]

  const isCurrent = (path) => {
    if (path === "/" && location.pathname === "/") return true
    if (path !== "/" && location.pathname.startsWith(path)) return true
    return false
  }

  const isStaffSection = location.pathname.startsWith("/staff") || location.pathname.startsWith("/alerts")

  return (
    <header className="sticky top-0 z-40 w-full border-b border-slate-800/80 bg-slate-950/80 backdrop-blur-md">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Brand Logo */}
          <Link
            to="/"
            className="flex items-center gap-2 hover:opacity-95 transition"
            onClick={() => setMobileMenuOpen(false)}
          >
            <Logo size="md" />
          </Link>

          {/* Desktop Navigation Links */}
          <nav className="hidden md:flex items-center gap-1">
            {navLinks.map((link) => {
              const Icon = link.icon
              const active = isCurrent(link.path)
              return (
                <Link
                  key={link.path}
                  to={link.path}
                  className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition ${
                    active
                      ? "text-teal-400 bg-teal-950/40 border border-teal-800/50"
                      : "text-slate-300 hover:text-white hover:bg-slate-900"
                  }`}
                >
                  <Icon className={`w-4 h-4 ${active ? "text-teal-400" : "text-slate-400"}`} />
                  <span>{link.name}</span>
                </Link>
              )
            })}
          </nav>

          {/* Right Header Utilities: Language Selector, API Status, Staff Switcher */}
          <div className="hidden lg:flex items-center gap-3">
            {/* Live API Health Check Probe */}
            <LiveApiStatus />

            {/* Language Selector */}
            <div className="flex items-center rounded-lg bg-slate-900 border border-slate-800 p-0.5 text-xs font-medium text-slate-300">
              <span className="px-2 py-1 text-slate-500 flex items-center gap-1">
                <Globe className="w-3.5 h-3.5" />
              </span>
              <button
                onClick={() => setLang("en")}
                className={`px-2 py-1 rounded-md transition cursor-pointer ${
                  lang === "en"
                    ? "bg-teal-600 text-white font-semibold shadow-xs"
                    : "hover:text-white"
                }`}
              >
                EN
              </button>
              <button
                onClick={() => setLang("ta")}
                className={`px-2 py-1 rounded-md transition cursor-pointer ${
                  lang === "ta"
                    ? "bg-teal-600 text-white font-semibold shadow-xs"
                    : "hover:text-white"
                }`}
              >
                தமிழ்
              </button>
              <button
                onClick={() => setLang("hi")}
                className={`px-2 py-1 rounded-md transition cursor-pointer ${
                  lang === "hi"
                    ? "bg-teal-600 text-white font-semibold shadow-xs"
                    : "hover:text-white"
                }`}
              >
                हिन्दी
              </button>
            </div>

            {/* OPD Waiting Room Kiosk Display */}
            <Link
              to="/display"
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold tracking-wide border border-teal-500/40 bg-teal-500/10 text-teal-300 hover:bg-teal-500/20 transition cursor-pointer"
              title="Open full-screen waiting room token display"
            >
              <span className="w-1.5 h-1.5 rounded-full bg-teal-400 animate-ping" />
              <span>OPD Kiosk</span>
            </Link>

            {/* Staff Command Center Button */}
            <Link
              to="/staff"
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold tracking-wide border transition cursor-pointer ${
                isStaffSection
                  ? "bg-cyan-600 text-white border-cyan-500 shadow-md shadow-cyan-600/20"
                  : "bg-slate-900 text-slate-200 border-slate-700 hover:bg-slate-800 hover:border-slate-600"
              }`}
            >
              <LayoutDashboard className="w-3.5 h-3.5 text-cyan-400" />
              <span>{t.nav.staffPortal}</span>
            </Link>

            {/* Emergency Hotline Button */}
            <a
              href="tel:108"
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-rose-950/80 hover:bg-rose-900 text-rose-300 border border-rose-800/80 transition"
              title="24/7 Casualty & Ambulance Hotline"
            >
              <ShieldAlert className="w-3.5 h-3.5 text-rose-400" />
              <span>108 Casualty</span>
            </a>
          </div>

          {/* Mobile Menu Button */}
          <div className="flex md:hidden items-center gap-2">
            <LiveApiStatus />
            <button
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="p-2 rounded-lg text-slate-400 hover:text-white hover:bg-slate-900 transition"
              aria-label="Toggle navigation menu"
            >
              {mobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
            </button>
          </div>
        </div>
      </div>

      {/* Mobile Dropdown Menu */}
      {mobileMenuOpen && (
        <div className="md:hidden border-b border-slate-800 bg-slate-950/95 px-4 pt-2 pb-6 space-y-3">
          <nav className="flex flex-col space-y-1">
            {navLinks.map((link) => {
              const Icon = link.icon
              const active = isCurrent(link.path)
              return (
                <Link
                  key={link.path}
                  to={link.path}
                  onClick={() => setMobileMenuOpen(false)}
                  className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium ${
                    active
                      ? "text-teal-400 bg-teal-950/60 border border-teal-800/50"
                      : "text-slate-300 hover:text-white hover:bg-slate-900"
                  }`}
                >
                  <Icon className="w-4 h-4 text-slate-400" />
                  <span>{link.name}</span>
                </Link>
              )
            })}
            <Link
              to="/staff"
              onClick={() => setMobileMenuOpen(false)}
              className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium text-cyan-300 bg-cyan-950/40 border border-cyan-800/50"
            >
              <LayoutDashboard className="w-4 h-4 text-cyan-400" />
              <span>{t.nav.staffPortal}</span>
            </Link>
          </nav>

          {/* Language selector in mobile menu */}
          <div className="pt-2 border-t border-slate-800/80 flex items-center justify-between">
            <span className="text-xs text-slate-400 flex items-center gap-1.5">
              <Globe className="w-3.5 h-3.5 text-teal-400" />
              Language:
            </span>
            <div className="flex gap-1">
              <button
                onClick={() => setLang("en")}
                className={`px-2.5 py-1 text-xs rounded-md ${
                  lang === "en" ? "bg-teal-600 text-white font-bold" : "bg-slate-900 text-slate-300"
                }`}
              >
                English
              </button>
              <button
                onClick={() => setLang("ta")}
                className={`px-2.5 py-1 text-xs rounded-md ${
                  lang === "ta" ? "bg-teal-600 text-white font-bold" : "bg-slate-900 text-slate-300"
                }`}
              >
                தமிழ்
              </button>
              <button
                onClick={() => setLang("hi")}
                className={`px-2.5 py-1 text-xs rounded-md ${
                  lang === "hi" ? "bg-teal-600 text-white font-bold" : "bg-slate-900 text-slate-300"
                }`}
              >
                हिन्दी
              </button>
            </div>
          </div>
        </div>
      )}
    </header>
  )
}
