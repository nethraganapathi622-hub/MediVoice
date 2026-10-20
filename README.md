# MediVoice — AI-Powered Virtual Hospital Receptionist

> **Phase 1: Engineering Foundation** (Complete & Verified)  
> **Phase 2: Premium Frontend Design System & UI** (Complete & Verified)  
> **Phase 3: Real Database and Hospital API** (Complete & Verified)  
> **Phase 4: Real-Time WebSocket Infrastructure** (Complete & Verified)  
> **Phase 5A: Live PostgreSQL Verification & Authentication Hardening** (Complete & Verified)  
> **Phase 5B: Real Multilingual Voice AI and Hospital Tool Integration** (Complete & Verified)  
> **Phase 6: Enterprise Patient Self-Service, Kiosk Display, EHR & Notifications** (Complete & Verified)

---

## 1. System Overview

**MediVoice** is an enterprise-grade virtual hospital receptionist, outpatient coordination, and clinical staff platform designed for multi-tier healthcare environments.

### Phase Capabilities
- **Real Multilingual Voice AI Engine**: Native browser speech recognition (`SpeechRecognition` / `webkitSpeechRecognition`) and high-fidelity speech synthesis (`speechSynthesis`) supporting English (`en-US`), Tamil (`ta-IN`), and Hindi (`hi-IN`) with micro-state transitions (`idle`, `requesting_permission`, `listening`, `transcribing`, `processing`, `speaking`, `error`).
- **Patient Self-Service Portal & Verification**: Phone OTP verification flow, verified patient dashboard, privacy-preserving consultation passes with digital QR/Barcode graphics, self-service slot rescheduling, cancellation, and mobile check-in.
- **Outpatient Waiting Room Kiosk Display (`/display`, `/kiosk`)**: High-contrast waiting room monitor view with "Now Calling", "Recently Called", and "Waiting Queue" rosters, Web Audio chime synthesis, and multilingual spoken announcements in EN, TA, and HI.
- **Multilingual SMS & WhatsApp Notification Service**: Asynchronous notification dispatcher delivering immediate booking receipts, reschedule alerts, cancellation notices, queue token updates, and urgent trauma triage broadcasts in English, Tamil, and Hindi.
- **Clinical Staff Electronic Health Record (EHR)**: Doctor consultation workspace supporting clinical observations, vitals, diagnosis, and structured digital prescriptions with automatic consultation progression.
- **Transactional Hospital Tool Integration**: Safe, typed backend tools for department search, doctor directory filtering, real-time slot availability, appointment creation with explicit confirmation safeguards, booking rescheduling, safe cancellation, privacy-preserving appointment status lookups, and campus wayfinding.
- **Deterministic Emergency Escalation**: Immediate synchronous multi-lingual clinical symptom triage (chest pain, breathing difficulty, trauma, stroke symptoms) that issues life-saving directions (108 Ambulance / Emergency Ward) and broadcasts high-priority real-time `alert.created` events to the Staff Command Center via WebSockets before model execution.
- **Alembic Database Migrations**: Version-controlled schemas: `001_initial_schema` and `002_add_consultation_notes`.
- **Hardened Staff Authentication**: Cryptographic JWT Bearer token authentication, strict role-based access control (`doctor`, `nurse`, `admin`), removal of credential discovery endpoints, and production environment guards.
- **Dual-Channel WebSocket Push Engine**: Dedicated public `/ws/public` channel and authenticated `/ws/staff` channel for instantaneous UI synchronization without polling.
- **Comprehensive Automated Test Suite**: Fast in-memory SQLite unit test suite (**48 passed unit tests**) plus live PostgreSQL integration test suite (5 tests).

---

## 2. Technology Stack

| Domain | Technology | Version | Purpose |
|---|---|---|---|
| **Frontend UI** | React | 19.x | Declarative component state & clinical UX |
| **Routing** | React Router | 7.x | Dual-portal routing (Patient Assistant & Staff Command Center) |
| **Icons** | Lucide React | Latest | Healthcare, diagnostic, and administrative icons |
| **Tooling & Bundler** | Vite | 8.x | High-speed ESM development and production builds |
| **Styling** | Tailwind CSS | 4.x | Utility-first clinical responsive design system |
| **Linting** | ESLint | 10.x | Strict code quality enforcement |
| **Backend Framework** | FastAPI | >=0.115.0 | Asynchronous REST and WebSocket API |
| **ASGI Server** | Uvicorn | >=0.32.0 | ASGI server with WebSocket support |
| **Settings & Validation** | Pydantic / Pydantic Settings | >=2.10.0 | Schema validation & environment configuration |
| **ORM / Data Access** | SQLAlchemy | >=2.0.36 | Database mapping, relationships, constraints & connection pooling |
| **Schema Migrations** | Alembic | >=1.14.0 | Database migration versioning |
| **Database Driver** | Psycopg2-binary | >=2.9.10 | PostgreSQL dialect engine |
| **Database** | PostgreSQL | 14+ / 16+ / 18+ | Primary relational database |
| **Security & JWT** | PyJWT | >=2.10.0 | Cryptographic HMAC-SHA256 Bearer tokens |
| **Testing** | Pytest / HTTPX | >=8.3.0 | Unit and PostgreSQL integration testing |

---

## 3. Repository Structure

```text
MediVoice/
├── .env.example                     # Root environment template
├── .gitignore                        # Universal git ignore (Python, Node, secrets, OS)
├── README.md                         # Complete system documentation
├── frontend/
│   ├── eslint.config.js              # ESLint configuration
│   ├── index.html                    # Main entry point with SEO metadata
│   ├── package.json                  # React 19, Tailwind v4, Lucide, React Router
│   ├── vite.config.js                # Vite build configuration
│   └── src/
│       ├── components/
│       │   ├── layout/               # Navbar, Footer, StaffSidebar
│       │   └── ui/                   # Logo, Badge, AudioWaveform, LiveApiStatus
│       ├── pages/
│       │   ├── PatientAssistant.jsx  # Voice-first intake & quick actions
│       │   ├── StaffDashboard.jsx    # Live clinical KPI dashboard & patient queue
│       │   ├── Doctors.jsx           # Specialist roster with specialty filters
│       │   ├── Appointments.jsx      # Consultations, pass cards & slot bookings
│       │   ├── Departments.jsx       # Campus wayfinding & wait times
│       │   └── Alerts.jsx            # Emergency triage alerts & acknowledgments
│       ├── services/
│       │   ├── api.js                # REST client & authenticated staff requests
│       │   ├── websocket.js          # Reconnecting dual-channel WebSocket client
│       │   └── i18n.js               # EN, TA, HI translations
│       ├── App.jsx                   # Central routing & WebSocket event distributor
│       ├── index.css                 # Tailwind CSS v4 directives
│       └── main.jsx                  # React DOM mount point
└── backend/
    ├── .env.example                  # Backend environment template
    ├── requirements.txt              # Core runtime dependencies
    ├── requirements-dev.txt          # Development, Alembic & pytest dependencies
    ├── alembic.ini                   # Alembic configuration
    ├── alembic/
    │   ├── env.py                    # Safe URL resolution with escaped '%' signs
    │   └── versions/                 # Version-controlled migration scripts
    ├── app/
    │   ├── main.py                   # FastAPI app, lifespan, CORS & error handlers
    │   ├── seed.py                   # Idempotent development seed script
    │   ├── core/
    │   │   ├── config.py             # Discrete PostgreSQL parameters & safe URL construction
    │   │   ├── database.py           # Engine initialization & session dependency
    │   │   ├── security.py           # JWT token generation, role verification & password hashing
    │   │   └── websocket_manager.py  # Public & staff real-time broadcast engine
    │   ├── models/                   # Department, Doctor, Appointment, Queue, Alert models
    │   ├── schemas/                  # Pydantic v2 validation models
    │   ├── services/                 # Hospital business logic & mutation handlers
    │   └── api/routes/               # Health, Auth, Hospital, WebSocket endpoints
    └── tests/
        ├── conftest.py               # SQLite in-memory test fixtures
        ├── test_health.py            # Liveness and readiness probe tests
        ├── test_hospital_api.py      # Core appointment, queue, alert business tests
        └── test_postgres_integration.py # Real PostgreSQL persistence & concurrency tests
```

---

## 4. Local PostgreSQL Setup (Windows PowerShell)

Follow these exact steps to configure, migrate, and seed your local PostgreSQL instance on Windows.

### Step 1: Verify PostgreSQL Service Status
In an **Administrator PowerShell** or standard PowerShell window:
```powershell
Get-Service -Name postgresql*
```
If the service is stopped, start it:
```powershell
Start-Service -Name postgresql*
```

### Step 2: Create the Databases
Locate your PostgreSQL binary path (e.g., PostgreSQL 16 or 18) and create the primary and optional test database:
```powershell
# Default installation path for PostgreSQL 18
$psql = "C:\Program Files\PostgreSQL\18\bin\psql.exe"

# If using PostgreSQL 16:
# $psql = "C:\Program Files\PostgreSQL\16\bin\psql.exe"

# Create primary database
& $psql -U postgres -c "CREATE DATABASE medivoice_db;"

# Create optional integration test database
& $psql -U postgres -c "CREATE DATABASE medivoice_test_db;"
```
*(Enter your PostgreSQL master password when prompted).*

### Step 3: Configure Environment Variables
Copy the template to `backend/.env`:
```powershell
Copy-Item backend\.env.example backend\.env
```

Open `backend/.env` and enter your credentials. If your password contains special characters (e.g. `@`, `#`, `%`, `!`, `^`), use **Option A** (discrete fields) — MediVoice uses `sqlalchemy.engine.URL.create` to automatically and safely encode them:

```env
# Option A: Discrete parameters (Recommended)
POSTGRES_USER=postgres
POSTGRES_PASSWORD=YourSecretPasswordHere
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=medivoice_db

# Optional integration test database URL
POSTGRES_TEST_DATABASE_URL=postgresql+psycopg2://postgres:YourSecretPasswordHere@localhost:5432/medivoice_test_db

# Security settings
SECRET_KEY=medivoice-strong-secret-key-at-least-32-chars-long
ENVIRONMENT=development
```

> **Security Rule**: `backend/.env` is ignored by Git. Never commit or log database passwords.

### Step 4: Run Alembic Database Migrations
Activate your virtual environment and apply migrations against PostgreSQL:
```powershell
cd backend
.\.venv\Scripts\Activate.ps1
alembic upgrade head
```

### Step 5: Run the Idempotent Seed Script
Populate departments, doctors, appointments, and queue tokens:
```powershell
python -m app.seed
```
*Note: The seed script uses unique constraint lookups. Running it multiple times will safely update or skip existing records without creating duplicates or dropping tables.*

---

## 5. Staff Authentication & Security Architecture

MediVoice enforces strict authentication and authorization standards across all endpoints:

1. **No Public Credential Discovery**:
   - The insecure endpoint `/api/auth/staff-accounts` has been completely removed.
   - Clinical staff log in by submitting credentials directly to `POST /api/auth/login`.

2. **Cryptographic Token Verification**:
   - Successful logins return an HMAC-SHA256 JWT access token.
   - Staff REST endpoints require a valid `Authorization: Bearer <token>` header.
   - The token contains claims for `sub` (employee ID) and `role` (`doctor`, `nurse`, `admin`).
   - Client-supplied headers (e.g., `X-Staff-Employee-ID`, `X-Staff-Role`) are never trusted for authorization.

3. **WebSocket Authorization**:
   - `/ws/public` is open to patients and monitors public queue and department wait updates.
   - `/ws/staff` requires a cryptographically valid token via query parameter `?token=<jwt>`. Unauthorized connections are immediately rejected with status code `1008 Policy Violation`.

4. **Production Guard**:
   - In `development` mode, predefined staff accounts (`EMP-DOC-01`, `EMP-NUR-01`, `EMP-ADM-01`) are available for testing.
   - When `ENVIRONMENT` is set to `staging` or `production`, synthetic accounts are **strictly disabled**, and `SECRET_KEY` must be at least 32 characters long.

---

## 6. Multilingual Voice AI & Hospital Tool Architecture

MediVoice Phase 5B connects the voice intake frontend directly to real clinical backend tools via a safe, privacy-preserving conversation pipeline.

### A. Speech Pipeline & Adapter Pattern
- **Adapter Architecture**: Implemented via `BrowserSpeechAdapter` in [frontend/src/services/speechAdapter.js](file:///frontend/src/services/speechAdapter.js). It wraps the W3C Web Speech API (`SpeechRecognition` / `webkitSpeechRecognition` and `window.speechSynthesis`) behind a clean interface:
  - `startListening({ onTranscript, onError, onEnd, lang })`
  - `stopListening()`
  - `speak(text, { lang, onStart, onEnd, onError })`
  - `stopSpeaking()`
- **Supported Languages**:
  - English (`en-US`)
  - Tamil (`ta-IN`)
  - Hindi (`hi-IN`)
- **Micro-State Lifecycle**: `idle` ➔ `requesting_permission` ➔ `listening` ➔ `transcribing` ➔ `processing` ➔ `speaking` ➔ `error`.
- **Accessibility & Fallback**: If microphone permission is denied or the browser lacks SpeechRecognition (e.g., Firefox), the UI seamlessly falls back to a typed input box while continuing to support spoken audio responses. Spoken audio can be cancelled or muted at any time via the Mute button.

### B. AI Conversation Engine & Hospital Tools
- **Configurable LLM Provider**: Integrated with Google Gemini via the official server-side SDK `google-genai` (default: `gemini-2.5-flash`). API keys are stored exclusively in `backend/.env` as `GEMINI_API_KEY` and are never exposed to client bundles or WebSocket messages.
- **Clinical Rule-Based Fallback**: When `GEMINI_API_KEY` is not configured, expired, or experiences network timeouts, MediVoice automatically and seamlessly switches to a built-in multilingual clinical regex and semantic parser.
- **Typed Hospital Backend Tools**:
  1. `search_departments`: Campus directories and floor wayfinding.
  2. `search_doctors`: Query specialists by department or specialty name.
  3. `check_doctor_availability_tool`: Computes exact free slots for any requested date.
  4. `book_appointment_tool`: Executes transactional booking **only after explicit patient confirmation**; prevents past bookings and double-bookings.
  5. `reschedule_appointment_tool`: Moves verified bookings to new time slots.
  6. `cancel_appointment_tool`: Safely cancels bookings without deleting audit records.
  7. `lookup_appointment_tool`: Requires matching patient phone number to protect patient privacy against unauthorized snooping.
  8. `get_department_directions_tool`: Natural language campus floor and wing navigation.

### C. Conservative Emergency Symptom Escalation
- **Deterministic Pre-LLM Detection**: Symptom phrases (e.g., "chest pain", "shortness of breath", "நெஞ்சு வலி", "सीने में दर्द") are evaluated synchronously by `emergency_detector.py` before model execution.
- **Immediate Life-Saving Guidance**: Immediately prompts patient to call 108 Emergency Ambulance or report directly to the Emergency Trauma Ward.
- **Instant Staff Dispatch**: Automatically persists a `TriageAlert` (`priority="critical"`, `alert_type="trauma_priority"`) to the database and dispatches a high-priority WebSocket event (`alert.created`) to the Staff Command Center in real time.

---

## 7. Running Tests

### A. Fast Unit Tests (SQLite In-Memory)
Unit tests run completely in-memory without requiring an active PostgreSQL instance:
```powershell
cd backend
.\.venv\Scripts\Activate.ps1
pytest -v
```
**Results**: **48 unit tests passed** covering:
- Health and readiness probes (`/api/health`, `/api/health/ready`).
- Department and doctor directory queries.
- Slot booking, validation, past date rejection, and collision prevention.
- Queue check-in, token progression, and status transitions.
- Triage alert generation and acknowledgment.
- JWT authentication, role enforcement, and token expiry.
- Assistant request/response Pydantic v2 validation.
- Multilingual greetings in English, Tamil, and Hindi.
- Deterministic emergency escalation and staff triage alert creation.
- Multi-turn appointment booking flow with confirmation step safeguards.
- Slot conflict detection with real alternative slot recommendations.
- Patient privacy protection preventing unauthorized appointment lookups.
- Department wayfinding with filler-word scrubbing.
- Mocked Gemini provider integration and graceful fallback on connection timeout.
- Patient portal OTP request, validation, and JWT session issuance.
- Patient privacy-preserving single pass lookup by reference and matching phone number.
- Patient self-service appointment rescheduling and cancellation with strict ownership verification.
- Multilingual SMS/WhatsApp confirmation, rescheduling, and cancellation notification dispatches.
- OPD Queue token issuance notifications.
- Emergency triage trauma broadcast dispatch.
- Doctor consultation note creation with structured digital prescriptions.
- Prevention of duplicate EHR consultation notes.
- Role-based authorization guarding EHR mutations to doctors/clinical leads.

### B. Live PostgreSQL Integration Tests
When `POSTGRES_TEST_DATABASE_URL` is configured in `backend/.env`, run the live integration test suite:
```powershell
pytest tests/test_postgres_integration.py -v
```
**Integration Test Coverage**:
- `test_pg_schema_and_constraints`: Verifies tables, foreign keys, and indexes on live PostgreSQL.
- `test_pg_persistence_across_separate_sessions`: Verifies data commits survive session closure.
- `test_pg_appointment_persistence_across_restart`: Simulates application restart and verifies appointment persistence.
- `test_pg_concurrent_booking_collision_prevention`: Executes multithreaded concurrent booking attempts against the same doctor slot, verifying that database isolation prevents double-booking.
- `test_pg_unauthorized_user_cannot_access_staff_alerts`: Verifies that unauthenticated or patient-role requests cannot read clinical emergency alerts.

---

## 8. Running the Application

### Backend Service
```powershell
cd backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
- API Endpoint: `http://localhost:8000/api/health`
- Assistant Config Probe: `http://localhost:8000/api/assistant/config`
- Interactive OpenAPI Docs: `http://localhost:8000/docs`

### Frontend Service
```powershell
cd frontend
npm run dev
```
- Patient Assistant: `http://localhost:5173/`
- Patient Self-Service & Pass Lookup: `http://localhost:5173/appointments`
- Outpatient Waiting Room Kiosk Display: `http://localhost:5173/display` (or `/kiosk`)
- Specialist Directory & Booking: `http://localhost:5173/doctors`
- Hospital Departments & Wayfinding: `http://localhost:5173/departments`
- Staff Command Center: `http://localhost:5173/staff`
- Emergency Triage Live Feed: `http://localhost:5173/alerts`

---

## 9. Real-Time Multi-Client Verification

To verify real-time database persistence, AI intake, and WebSocket push synchronization:

1. Open **Client 1** (Patient Portal): `http://localhost:5173/` in a browser window.
2. Open **Client 2** (Staff Command Center): `http://localhost:5173/staff` in an incognito window. Log in as a staff member.
3. In **Client 1**, click the microphone button or type a request (e.g. *"I need to see a cardiologist tomorrow"*).
4. Select a specialist and slot, review the confirmation prompt, and confirm the appointment.
5. In **Client 1**, try an emergency phrase (e.g. *"I have severe chest pain and dizziness"*).
6. Observe **Client 2**: A critical triage alert immediately flashes on the staff board via WebSocket push **without a page reload**.
7. Stop the backend process (`Ctrl+C`), then restart it (`uvicorn app.main:app --reload`).
8. Refresh both browser tabs: All appointments and emergency alerts remain intact in the database.

### Event Delivery Architecture & Limitations
- **Current Architecture**: The application uses an in-memory asynchronous broadcast manager (`ConnectionManager`) optimized for a single Uvicorn worker process.
- **Multi-Worker Limitation**: When scaling to multiple Uvicorn workers or clustered backend containers, WebSocket connections residing on separate worker processes require an external message bus (such as **Redis PUB/SUB** or **PostgreSQL LISTEN/NOTIFY**) to distribute broadcast events across workers.
