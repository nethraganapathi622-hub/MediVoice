import { Link } from "react-router-dom"
import { Phone, MapPin, Clock, ShieldCheck, HeartPulse } from "lucide-react"
import Logo from "../ui/Logo"
import { translations } from "../../services/i18n"

export default function Footer({ lang = "en" }) {
  const t = translations[lang] || translations.en

  return (
    <footer className="border-t border-slate-800/80 bg-slate-950 text-slate-400 text-xs mt-auto">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8 mb-8">
          {/* Brand & Purpose */}
          <div className="space-y-4">
            <Logo size="sm" />
            <p className="text-slate-400 leading-relaxed text-xs">
              {t.footer.about}
            </p>
            <div className="flex items-center gap-2 text-teal-400 font-mono text-[11px]">
              <HeartPulse className="w-3.5 h-3.5" />
              <span>Multilingual Clinical Triage · AI Assistant</span>
            </div>
          </div>

          {/* Quick Navigation */}
          <div className="space-y-3">
            <h3 className="font-semibold text-slate-200 text-sm tracking-tight">{t.footer.quickLinks}</h3>
            <ul className="space-y-2">
              <li>
                <Link to="/" className="hover:text-teal-400 transition">
                  {t.nav.assistant}
                </Link>
              </li>
              <li>
                <Link to="/doctors" className="hover:text-teal-400 transition">
                  {t.nav.doctors}
                </Link>
              </li>
              <li>
                <Link to="/appointments" className="hover:text-teal-400 transition">
                  {t.nav.appointments}
                </Link>
              </li>
              <li>
                <Link to="/departments" className="hover:text-teal-400 transition">
                  {t.nav.departments}
                </Link>
              </li>
              <li>
                <Link to="/staff" className="hover:text-cyan-400 transition">
                  {t.nav.staffPortal}
                </Link>
              </li>
            </ul>
          </div>

          {/* Hospital Contact & Emergency */}
          <div className="space-y-3">
            <h3 className="font-semibold text-slate-200 text-sm tracking-tight">Hospital Campus</h3>
            <ul className="space-y-2.5 text-slate-400">
              <li className="flex items-start gap-2">
                <MapPin className="w-4 h-4 text-teal-400 shrink-0 mt-0.5" />
                <span>MediVoice Central Medical Campus, Apollo Cross Way, Anna Salai, Chennai 600006</span>
              </li>
              <li className="flex items-center gap-2">
                <Phone className="w-4 h-4 text-teal-400 shrink-0" />
                <span>Outpatient Desk: +91 (44) 2829 0100</span>
              </li>
              <li className="flex items-center gap-2 text-rose-300 font-semibold">
                <ShieldCheck className="w-4 h-4 text-rose-400 shrink-0" />
                <span>24/7 Casualty & Triage: 108</span>
              </li>
              <li className="flex items-center gap-2">
                <Clock className="w-4 h-4 text-teal-400 shrink-0" />
                <span>OPD Hours: 08:00 AM - 08:00 PM</span>
              </li>
            </ul>
          </div>

          {/* Clinical Notice / Disclaimer */}
          <div className="space-y-3 p-4 rounded-xl bg-slate-900/60 border border-slate-800">
            <h3 className="font-semibold text-amber-300 text-xs tracking-tight uppercase flex items-center gap-1.5">
              <span>⚠️</span>
              {t.footer.legal}
            </h3>
            <p className="text-[11px] text-slate-400 leading-relaxed">
              {t.footer.legalText}
            </p>
            <div className="pt-2 text-[10px] font-mono text-slate-500">
              Demo Environment · Simulated Medical Assistant
            </div>
          </div>
        </div>

        {/* Bottom Bar */}
        <div className="pt-8 border-t border-slate-800/80 flex flex-col sm:flex-row items-center justify-between gap-4 text-slate-500 text-xs">
          <div>
            &copy; {new Date().getFullYear()} {t.footer.rights}
          </div>
          <div className="flex items-center gap-4 text-slate-500 font-mono text-[11px]">
            <span>Phase 2 Production UI</span>
            <span>•</span>
            <span>React 19 + Tailwind CSS v4</span>
          </div>
        </div>
      </div>
    </footer>
  )
}
