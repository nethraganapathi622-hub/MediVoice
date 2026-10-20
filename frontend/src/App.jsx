import { useState } from "react"
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom"
import Navbar from "./components/layout/Navbar"
import Footer from "./components/layout/Footer"
import PatientAssistant from "./pages/PatientAssistant"
import StaffDashboard from "./pages/StaffDashboard"
import Doctors from "./pages/Doctors"
import Appointments from "./pages/Appointments"
import Departments from "./pages/Departments"
import Alerts from "./pages/Alerts"
import QueueDisplay from "./pages/QueueDisplay"

export default function App() {
  const [lang, setLang] = useState("en")

  return (
    <BrowserRouter>
      <Routes>
        {/* Full-Screen Waiting Room Kiosk Display (No standard layout navbar) */}
        <Route path="/display" element={<QueueDisplay />} />
        <Route path="/kiosk" element={<QueueDisplay />} />

        {/* Standard Patient & Staff Pages with Global Navbar/Footer */}
        <Route
          path="*"
          element={
            <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col justify-between selection:bg-teal-500 selection:text-white font-sans antialiased">
              <Navbar lang={lang} setLang={setLang} />
              <main className="flex-1 w-full">
                <Routes>
                  <Route path="/" element={<PatientAssistant lang={lang} />} />
                  <Route path="/doctors" element={<Doctors />} />
                  <Route path="/appointments" element={<Appointments />} />
                  <Route path="/departments" element={<Departments />} />
                  <Route path="/staff" element={<StaffDashboard />} />
                  <Route path="/alerts" element={<Alerts />} />
                  <Route path="*" element={<Navigate to="/" replace />} />
                </Routes>
              </main>
              <Footer lang={lang} />
            </div>
          }
        />
      </Routes>
    </BrowserRouter>
  )
}
