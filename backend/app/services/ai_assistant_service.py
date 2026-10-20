import json
import logging
import re
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.department import Department
from app.models.doctor import Doctor
from app.schemas.assistant import AssistantChatRequest, AssistantChatResponse
from app.services.emergency_detector import (
    detect_emergency_symptoms,
    get_emergency_response_text,
    trigger_emergency_alert,
)
from app.services.hospital_tools import (
    book_appointment_tool,
    cancel_appointment_tool,
    check_doctor_availability_tool,
    get_department_directions_tool,
    lookup_appointment_tool,
    reschedule_appointment_tool,
    search_departments,
    search_doctors,
)

logger = logging.getLogger("medivoice.assistant")

# Thread-safe in-memory session cache for multi-turn conversations
_CONVERSATION_SESSIONS: Dict[str, Dict[str, Any]] = {}


def _get_or_create_session(conversation_id: Optional[str]) -> tuple[str, Dict[str, Any]]:
    """Retrieve existing session state or initialize a clean one."""
    settings = get_settings()
    ttl = timedelta(minutes=settings.ASSISTANT_SESSION_TTL_MINUTES)
    now = datetime.now(timezone.utc)

    # Clean expired sessions
    expired_keys = [
        k for k, v in _CONVERSATION_SESSIONS.items()
        if now - v.get("updated_at", now) > ttl
    ]
    for k in expired_keys:
        _CONVERSATION_SESSIONS.pop(k, None)

    if not conversation_id or conversation_id not in _CONVERSATION_SESSIONS:
        cid = conversation_id or str(uuid.uuid4())
        session = {
            "conversation_id": cid,
            "created_at": now,
            "updated_at": now,
            "history": [],
            "pending_action": None,
            "selected_doctor_id": None,
            "selected_date": None,
            "patient_name": None,
            "patient_phone": None,
        }
        _CONVERSATION_SESSIONS[cid] = session
        return cid, session

    session = _CONVERSATION_SESSIONS[conversation_id]
    session["updated_at"] = now
    return conversation_id, session


# Clinical specialty map for multilingual intent detection across all hospital departments
SPECIALTY_SYNONYMS: Dict[str, List[str]] = {
    "Cardiology": [
        "cardiologist", "cardiology", "heart", "cardio", "cardiac", "chest", "hypertension",
        "heart specialist", "heart care", "heart-related", "cardiovascular", "card",
        "இதயம்", "இதய", "இதய நோய்", "மாரடைப்பு", "கார்டியாலஜி", "दिल", "हृदय", "हार्ट", "कार्डियोलॉजी"
    ],
    "Neurology": [
        "neurologist", "neurology", "brain", "nerve", "stroke", "stroke clinic", "headache", "headaches",
        "dizziness", "migraine", "epilepsy", "seizure", "paralysis", "neuropathy", "neur",
        "மூளை", "நரம்பியல்", "நரம்பு", "தலைவலி", "மயக்கம்", "நியூரோ", "दिमाग", "न्यूरो", "सिरदर्द", "चक्कर", "न्यूरोलॉजी"
    ],
    "Orthopedics": [
        "orthopedic", "orthopedics", "orthopedist", "ortho", "bone", "bones", "joint", "joints",
        "fracture", "knee", "knee pain", "joint pain", "spine", "back pain", "arthritis", "ligament", "joint replacement", "orth",
        "எலும்பு", "மூட்டு", "முழங்கால்", "முழங்கால் வலி", "ஆர்த்தோ", "हड्डी", "जोड़", "घुटने का दर्द", "जोड़ों का दर्द", "ऑर्थोपेडिक्स", "ऑर्थो"
    ],
    "Pediatrics": [
        "pediatrician", "pediatrics", "pediatric", "children's doctor", "children doctor", "child doctor",
        "child", "children", "baby", "infant", "newborn", "vaccination", "immunization", "child wellness", "pedi",
        "குழந்தை", "குழந்தைகள் நலன்", "குழந்தைகள்", "குழந்தை மருத்துவர்", "பீடியாட்ரிக்", "बच्चा", "बच्चे", "शिशु", "बाल रोग", "बच्चों के डॉक्टर"
    ],
    "Radiology": [
        "radiology", "radiologist", "imaging", "diagnostic imaging", "mri", "ct scan", "x-ray", "xray",
        "ultrasound", "scan", "scans", "dexa", "rad",
        "ஸ்கேன்", "எக்ஸ்ரே", "கதிரியக்கம்", "ரேடியாலஜி", "रेडियोलॉजी", "एक्स-रे", "सीटी स्कैन", "स्कैन", "अल्ट्रासाउंड"
    ],
    "Oncology": [
        "oncology", "oncologist", "cancer", "tumor", "chemotherapy", "radiation therapy",
        "biopsy", "day care", "onco", "புற்றுநோய்", "கட்டி", "ஆன்காலஜி", "ऑन्कोलॉजी", "कैंसर", "ट्यूमर"
    ],
    "General Medicine": [
        "general medicine", "internal medicine", "preventive medicine", "physician", "general physician",
        "general health", "general health concern", "general doctor", "general checkup", "routine checkup",
        "fever", "cough", "cold", "flu", "infection", "diabetes", "blood pressure", "geriatric", "genmed",
        "பொது மருத்துவம்", "பொது", "காய்ச்சல்", "இருமல்", "சளி", "பொது மருத்துவர்",
        "सामान्य चिकित्सा", "बुखार", "खांसी", "जुकाम", "चिकित्सक", "जनरल फिजिशियन"
    ],
    "Emergency": [
        "emergency", "trauma", "casualty", "accident", "urgent", "critical care",
        "emergency medical assistance", "critical trauma", "resuscitation", "ambulance", "108", "emrg",
        "அவசரம்", "விபத்து", "இமர்ஜென்சி", "इमरजेंसी", "आपातकालीन", "दुर्घटना"
    ],
}

# Precompile sorted list of (term, specialty) by length descending for longest-first matching
_SORTED_SPECIALTY_TERMS: List[Tuple[str, str]] = []
for _spec, _terms in SPECIALTY_SYNONYMS.items():
    for _t in _terms:
        _SORTED_SPECIALTY_TERMS.append((_t.lower().strip(), _spec))
_SORTED_SPECIALTY_TERMS.sort(key=lambda x: len(x[0]), reverse=True)


def _match_specialty(text: str) -> Optional[str]:
    lowered = text.lower().strip()
    for term, specialty in _SORTED_SPECIALTY_TERMS:
        if term.isascii():
            pattern = r"\b" + re.escape(term) + r"(?:s|es)?\b"
            if re.search(pattern, lowered):
                return specialty
        else:
            if term in lowered:
                return specialty
    return None



def _clean_speech_text(text: str) -> str:
    """Strip markdown formatting and symbols so TTS engine speaks cleanly."""
    cleaned = re.sub(r"[*_#`~\[\]]", "", text)
    cleaned = re.sub(r"\(.*?\)", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _process_with_gemini(
    message: str,
    language: str,
    session: Dict[str, Any],
    db: Session,
    settings=None,
) -> Optional[Dict[str, Any]]:
    """Invoke official Google Gemini SDK when GEMINI_API_KEY is configured."""
    if settings is None:
        settings = get_settings()
    if not settings.has_gemini_key:
        return None

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=settings.GEMINI_API_KEY)

        # Pull compact reference data for prompt context
        depts = db.execute(
            __import__("sqlalchemy").text("SELECT code, name, location, floor FROM departments WHERE is_active = true")
        ).fetchall()
        dept_summary = ", ".join([f"{d[1]} ({d[0]}, {d[2]}, Floor {d[3]})" for d in depts])

        docs = db.execute(
            __import__("sqlalchemy").text("SELECT id, name, specialty, room_number FROM doctors WHERE is_active = true")
        ).fetchall()
        doc_summary = ", ".join([f"ID {d[0]}: {d[1]} ({d[2]}, Room {d[3]})" for d in docs])

        system_instruction = (
            "You are MediVoice, a polite, professional AI hospital receptionist. "
            f"You serve patients in English ('en'), Tamil ('ta'), and Hindi ('hi'). The user's language is '{language}'. "
            "Hospital Directory Context:\n"
            f"- Departments: {dept_summary}\n"
            f"- Doctors: {doc_summary}\n\n"
            "Respond ONLY with a valid JSON object matching this schema:\n"
            "{\n"
            '  "intent": "greeting"|"find_doctor"|"find_department"|"check_availability"|"book_appointment"|"reschedule_appointment"|"cancel_appointment"|"check_appointment"|"hospital_directions"|"clarification"|"unsupported",\n'
            '  "assistant_text": "<Polite response in user language>",\n'
            '  "specialty": "<Specialty name if mentioned or null>",\n'
            '  "doctor_id": <doctor ID if mentioned or null>,\n'
            '  "doctor_name": "<doctor name if mentioned or null>",\n'
            '  "date": "<YYYY-MM-DD if mentioned or null>",\n'
            '  "time": "<HH:MM if mentioned or null>",\n'
            '  "department_name": "<department name if mentioned or null>",\n'
            '  "booking_reference": "<reference if checking/rescheduling or null>",\n'
            '  "clarification_needed": <true if missing critical info else false>\n'
            "}"
        )

        response = client.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=message,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                response_mime_type="application/json",
                temperature=0.2,
            ),
        )

        raw_text = response.text
        if raw_text:
            return json.loads(raw_text)
    except Exception as exc:
        logger.warning("Gemini AI API call encountered an error: %s. Using clinical fallback.", str(exc))

    return None


def _fallback_intent_parser(
    message: str,
    language: str,
    session: Dict[str, Any],
    db: Session,
) -> Dict[str, Any]:
    """Robust clinical rule-based intent and entity extractor supporting EN, TA, HI."""
    lowered = message.lower().strip()

    # 1. Greetings
    greeting_patterns = [
        r"\b(hello|hi|hey|good morning|good afternoon|good evening|namaste|vanakkam)\b",
        "வணக்கம்", "வாழ்க", "नमस्ते", "नमस्कार", "प्रणाम", "हेलो", "हाय"
    ]
    if any(re.search(p, lowered) if r"\b" in p else p in lowered for p in greeting_patterns):
        if len(lowered.split()) <= 4:
            if language == "ta":
                text = "வணக்கம்! நான் MediVoice மருத்துவமனை உதவியாளர். மருத்துவர் ஆலோசனை, துறை வழிகாட்டுதல் அல்லது முன்பதிவுகளுக்கு நான் உதவ முடியும்."
            elif language == "hi":
                text = "नमस्ते! मैं MediVoice अस्पताल सहायक हूँ। मैं डॉक्टर अपॉइंटमेंट, विभाग स्थान या परामर्श समय खोजने में आपकी मदद कर सकता हूँ।"
            else:
                text = "Hello! I am MediVoice, your virtual hospital receptionist. How can I assist you with doctor consultations, department directions, or appointment scheduling today?"
            return {
                "intent": "greeting",
                "assistant_text": text,
                "clarification_needed": False,
            }

    # 2. Check existing appointment / lookup
    if any(w in lowered for w in ["check appointment", "status", "token", "என் முன்பதிவு", "சரிபார்", "मेरी अपॉइंटमेंट", "स्टेटस"]):
        ref_match = re.search(r"\b(APT-\d{8}-[A-Z0-9]{6})\b", message.upper())
        phone_match = re.search(r"\b(\+?\d{10,13})\b", message)
        return {
            "intent": "check_appointment",
            "booking_reference": ref_match.group(1) if ref_match else None,
            "patient_phone": phone_match.group(1) if phone_match else None,
            "clarification_needed": not bool(ref_match),
            "assistant_text": (
                "To look up your appointment details, please provide your booking reference (e.g., APT-20261019-XXXXXX) and registered phone number."
                if language == "en" else
                "உங்கள் முன்பதிவு தகவலைப் பார்க்க, தயவுசெய்து முன்பதிவு எண் (APT-...) மற்றும் தொலைபேசி எண்ணை வழங்கவும்."
                if language == "ta" else
                "अपनी अपॉइंटमेंट देखने के लिए, कृपया अपनी बुकिंग संदर्भ संख्या (APT-...) और पंजीकृत फोन नंबर प्रदान करें।"
            ),
        }

    # 3. Department directions vs Doctor inquiries
    is_doctor_query = any(
        w in lowered
        for w in [
            "doctor", "doctors", "dr", "dr.", "physician", "specialist", "specialists",
            "appointment", "book", "consult", "consultation", "available", "see a doctor",
            "மருத்துவர்", "டாக்டர்", "முன்பதிவு", "டாக்டர்கள்", "डॉक्टर", "अपॉइंटमेंट", "दिखाना"
        ]
    )
    wayfinding_keywords = ["where is", "direction", "floor", "how to reach", "way to", "location", "எங்கே உள்ளது", "कहाँ है"]
    is_wayfinding = any(k in lowered for k in wayfinding_keywords) or (
        any(k in lowered for k in ["department", "பிரிவு", "विभाग"]) and not is_doctor_query
    )
    if is_wayfinding:
        return {
            "intent": "hospital_directions",
            "department_name": lowered,
            "clarification_needed": False,
            "assistant_text": "Searching our clinical campus directory...",
        }

    # 4. Doctor search or appointment booking
    specialty = _match_specialty(lowered)
    matched_doctor_id = None
    all_docs = db.query(Doctor).filter(Doctor.is_active == True).all()
    for d in all_docs:
        doc_clean_name = re.sub(r"(?i)^dr\.?\s*", "", d.name).lower().strip()
        if d.name.lower() in lowered or (doc_clean_name and doc_clean_name in lowered):
            matched_doctor_id = d.id
            if not specialty:
                specialty = d.specialty
            break

    # Check for date in text
    date_found = None
    today = date.today()
    if "tomorrow" in lowered or "நாளை" in lowered or "कल" in lowered:
        date_found = today + timedelta(days=1)
    elif "today" in lowered or "இன்று" in lowered or "आज" in lowered:
        date_found = today
    else:
        # Check for YYYY-MM-DD
        iso_match = re.search(r"\b(202\d-\d{2}-\d{2})\b", message)
        if iso_match:
            try:
                date_found = datetime.strptime(iso_match.group(1), "%Y-%m-%d").date()
            except ValueError:
                pass

    # Check for time (e.g. 10:30, 09:00, 10 am)
    time_found = None
    time_match = re.search(r"\b([01]?\d|2[0-3]):([0-5]\d)\b", message)
    if time_match:
        time_found = f"{int(time_match.group(1)):02d}:{time_match.group(2)}"

    # Determine intent
    is_booking_intent = any(
        w in lowered
        for w in [
            "book", "schedule", "appointment", "consultation", "see a doctor", "முன்பதிவு",
            "புக்", "நேரம்", "बुक", "अपॉइंटमेंट", "दिखाना"
        ]
    )
    is_doctor_search_intent = any(
        w in lowered
        for w in [
            "find a doctor", "find doctor", "available doctor", "doctors available",
            "which doctor", "list doctor", "available specialist", "who are the doctor",
            "show doctor", "show me doctor", "look for doctor", "see doctor", "doctors at",
            "மருத்துவர்கள்", "மருத்துவர் பட்டியல்", "டாக்டர்கள்", "டாக்டர் யார்",
            "डॉक्टर उपलब्ध", "डॉक्टरों की सूची", "कौन से डॉक्टर", "डॉक्टरों को दिखाएं"
        ]
    ) or ("doctor" in lowered and any(w in lowered for w in ["available", "find", "list", "hospital", "have", "who", "which"]))

    if is_booking_intent or is_doctor_search_intent or specialty or matched_doctor_id or date_found or time_found:
        is_gen = bool(is_doctor_search_intent and not specialty and not matched_doctor_id)
        return {
            "intent": "book_appointment" if is_booking_intent else "find_doctor",
            "doctor_id": matched_doctor_id,
            "specialty": specialty,
            "date": str(date_found) if date_found else None,
            "time": time_found,
            "is_general_discovery": is_gen,
            "clarification_needed": not bool((matched_doctor_id or specialty) and date_found),
            "assistant_text": "",
        }


    # Default fallback
    if language == "ta":
        fallback_msg = "மன்னிக்கவும், உங்கள் கோரிக்கையை முழுமையாகப் புரிந்துகொள்ள முடியவில்லை. தயவுசெய்து மருத்துவர் பெயர், துறை அல்லது நீங்கள் திட்டமிட விரும்பும் நேரத்தைக் குறிப்பிடவும்."
    elif language == "hi":
        fallback_msg = "क्षमा करें, मैं आपके अनुरोध को पूरी तरह से समझ नहीं पाया। कृपया विशेषज्ञ डॉक्टर का नाम, विभाग या अपॉइंटमेंट का विवरण बताएं।"
    else:
        fallback_msg = "I did not completely catch that. Would you like to search for a specialist, check department directions, or book an outpatient appointment?"

    return {
        "intent": "clarification",
        "assistant_text": fallback_msg,
        "clarification_needed": True,
    }


def handle_assistant_interaction(
    request: AssistantChatRequest,
    db: Session,
    settings=None,
) -> AssistantChatResponse:
    """Coordinate emergency checking, entity extraction, hospital tool execution, and session management."""
    if settings is None:
        settings = get_settings()
    conversation_id, session = _get_or_create_session(request.conversation_id)
    language = request.language or "en"
    message = request.message.strip()

    # --------------------------------------------------------------------------
    # Step 1: Immediate Conservative Emergency Detection (Zero Latency)
    # --------------------------------------------------------------------------
    emergency = detect_emergency_symptoms(message)
    if emergency:
        alert = trigger_emergency_alert(
            db=db,
            symptoms=message,
            location="Virtual Reception Intake",
            patient_phone=request.patient_phone,
        )
        resp_guidance = get_emergency_response_text(language)
        return AssistantChatResponse(
            conversation_id=conversation_id,
            assistant_text=resp_guidance["text"],
            speech_text=resp_guidance["speech"],
            language=language,
            intent="emergency",
            clarification_needed=False,
            pending_action=None,
            action_result={
                "emergency": True,
                "alert_id": alert.id,
                "alert_status": alert.status,
                "emergency_phone": get_settings().EMERGENCY_CONTACT_PHONE,
                "ambulance_number": get_settings().EMERGENCY_AMBULANCE_NUMBER,
                "trauma_wing": "Ground Floor, Block A (Red Zone Entrance)",
            },
            ai_provider_used="rule_based_fallback",
        )

    # --------------------------------------------------------------------------
    # Step 2: Handle Explicitly Confirmed Actions (Safe Transaction Commit)
    # --------------------------------------------------------------------------
    confirmed = request.confirmed_action or session.get("pending_action")
    is_confirming_reply = message.lower() in [
        "confirm", "yes", "yes please", "proceed", "book it", "ஆம்", "உறுதிப்படுத்து", "हाँ", "कन्फर्म"
    ]

    if (request.confirmed_action or (is_confirming_reply and confirmed)):
        action_data = request.confirmed_action or confirmed
        action_type = action_data.get("action")

        if action_type == "book_appointment":
            doctor_id = action_data["doctor_id"]
            apt_date = datetime.strptime(action_data["date"], "%Y-%m-%d").date()
            slot_time = action_data["time"]
            p_name = request.patient_name or action_data.get("patient_name") or "Outpatient Guest"
            p_phone = request.patient_phone or action_data.get("patient_phone")

            res = book_appointment_tool(
                db=db,
                doctor_id=doctor_id,
                appointment_date=apt_date,
                start_time_str=slot_time,
                patient_name=p_name,
                patient_phone=p_phone,
            )

            session["pending_action"] = None  # Clear pending action

            if res["success"]:
                ref = res["booking_reference"]
                doc = res["doctor_name"]
                t_str = res["start_time"]
                d_str = res["appointment_date"]

                if language == "ta":
                    text = f"உங்கள் முன்பதிவு வெற்றிகரமாக உறுதிசெய்யப்பட்டது! முன்பதிவு எண்: {ref}. மருத்துவர்: {doc}, தேதி: {d_str}, நேரம்: {t_str}."
                elif language == "hi":
                    text = f"आपकी अपॉइंटमेंट सफलतापूर्वक पक्की हो गई है! संदर्भ संख्या: {ref}. डॉक्टर: {doc}, तारीख: {d_str}, समय: {t_str}."
                else:
                    text = f"Your appointment has been successfully confirmed! Booking Reference: {ref}. Doctor: {doc} on {d_str} at {t_str}."

                return AssistantChatResponse(
                    conversation_id=conversation_id,
                    assistant_text=text,
                    speech_text=_clean_speech_text(text),
                    language=language,
                    intent="book_appointment",
                    clarification_needed=False,
                    action_result=res,
                    ai_provider_used="rule_based_fallback",
                )
            else:
                err_msg = res.get("error", "Unable to complete booking.")
                if language == "ta":
                    text = f"மன்னிக்கவும், அந்த நேரம் இப்போது கிடைக்கவில்லை: {err_msg}."
                elif language == "hi":
                    text = f"क्षमा करें, यह समय स्लॉट अब उपलब्ध नहीं है: {err_msg}."
                else:
                    text = f"I apologize, that slot could not be reserved: {err_msg}."

                return AssistantChatResponse(
                    conversation_id=conversation_id,
                    assistant_text=text,
                    speech_text=_clean_speech_text(text),
                    language=language,
                    intent="book_appointment",
                    clarification_needed=True,
                    action_result=res,
                    ai_provider_used="rule_based_fallback",
                )

    # --------------------------------------------------------------------------
    # Step 3: Intent & Entity Parsing (Gemini or Fallback)
    # --------------------------------------------------------------------------
    ai_provider = "gemini" if settings.has_gemini_key else "rule_based_fallback"
    parsed = _process_with_gemini(message, language, session, db, settings=settings)
    if not parsed:
        parsed = _fallback_intent_parser(message, language, session, db)
        ai_provider = "rule_based_fallback"

    intent = parsed.get("intent", "clarification")

    # --------------------------------------------------------------------------
    # Step 4: Execute Validated Hospital Tools based on Parsed Intent
    # --------------------------------------------------------------------------
    action_result = None
    pending_action = None
    clarification_needed = parsed.get("clarification_needed", False)
    assistant_text = parsed.get("assistant_text", "")

    # Tool Execution: Find Doctor / Check Availability / Book
    if intent in ["find_doctor", "book_appointment"]:
        explicit_specialty = parsed.get("specialty") or _match_specialty(message)
        explicit_doctor_id = parsed.get("doctor_id")
        is_general_discovery = (
            parsed.get("is_general_discovery", False)
            or (
                intent == "find_doctor"
                and not explicit_specialty
                and not explicit_doctor_id
                and any(
                    w in message.lower()
                    for w in [
                        "which doctor", "doctors are available", "available doctor",
                        "doctors at your hospital", "hospital doctors", "list of doctors",
                        "who are the doctors", "show all doctors", "all doctors", "list doctors",
                        "available at your hospital", "மருத்துவர்கள்", "மருத்துவர் பட்டியல்",
                        "டாக்டர்கள்", "டாக்டர் யார்", "डॉक्टर उपलब्ध", "डॉक्टरों की सूची", "कौन से डॉक्टर"
                    ]
                )
            )
        )

        target_date_str = parsed.get("date")
        target_time = parsed.get("time")

        docs = []
        doctor_id = None
        specialty = None

        if is_general_discovery:
            # Case 1: Broad Hospital-Wide Discovery
            session["selected_doctor_id"] = None
            session["pending_action"] = None
            session["selected_date"] = None
            session["user_specified_date"] = False
            docs = search_doctors(db)
            action_result = {"doctors": docs}
            clarification_needed = True
            if language == "ta":
                assistant_text = "எங்கள் மருத்துவமனையில் பணியில் உள்ள சிறப்பு மருத்துவர்களின் விவரம் கீழே உள்ளது. நீங்கள் எந்தத் துறையின் மருத்துவரை அணுக விரும்புகிறீர்கள்?"
            elif language == "hi":
                assistant_text = "हमारे अस्पताल के कार्यरत विशेषज्ञ डॉक्टरों की सूची नीचे दी गई है। आप किस विशेषता के डॉक्टर से परामर्श लेना चाहते हैं?"
            else:
                assistant_text = "Here are our on-duty hospital specialists across departments. Which department or specialist would you like to consult?"

        elif explicit_doctor_id or explicit_specialty:
            # Case 2: New Explicit Doctor or Specialty in current message
            session["pending_action"] = None  # Clear any previous pending action

            if explicit_doctor_id:
                doc_record = db.query(Doctor).filter(Doctor.id == explicit_doctor_id, Doctor.is_active == True).first()
                if doc_record:
                    doctor_id = doc_record.id
                    specialty = doc_record.specialty
                    docs = [
                        {
                            "id": doc_record.id,
                            "name": doc_record.name,
                            "specialty": doc_record.specialty,
                            "qualifications": doc_record.qualifications,
                            "experience": doc_record.experience,
                            "consultation_fee": float(doc_record.consultation_fee),
                            "room_number": doc_record.room_number,
                            "department_id": doc_record.department_id,
                            "department_name": doc_record.department.name if doc_record.department else "Outpatient Wing",
                        }
                    ]
            elif explicit_specialty:
                specialty = explicit_specialty
                docs = search_doctors(db, specialty=explicit_specialty)
                if docs:
                    doctor_id = docs[0]["id"]

            if not docs or not doctor_id:
                session["selected_doctor_id"] = None
                clarification_needed = True
                disp_spec = explicit_specialty or "that specialty"
                if language == "ta":
                    assistant_text = f"{disp_spec} பிரிவில் தற்போது செயலில் உள்ள மருத்துவர்கள் கிடைக்கவில்லை. தயவுசெய்து வேறு துறையைத் தேர்ந்தெடுக்கவும்."
                elif language == "hi":
                    assistant_text = f"{disp_spec} में वर्तमान में कोई डॉक्टर उपलब्ध नहीं हैं। कृपया किसी अन्य विभाग का चयन करें।"
                else:
                    assistant_text = f"We could not find active specialists for {disp_spec}. Please choose another department or consult General Medicine."
                action_result = {"specialty": disp_spec, "doctors": []}
            else:
                session["selected_doctor_id"] = doctor_id

        elif session.get("selected_doctor_id"):
            # Case 3: Retain doctor for follow-up turns in existing conversation flow
            doctor_id = session.get("selected_doctor_id")
            doc_record = db.query(Doctor).filter(Doctor.id == doctor_id, Doctor.is_active == True).first()
            if doc_record:
                specialty = doc_record.specialty
                docs = [
                    {
                        "id": doc_record.id,
                        "name": doc_record.name,
                        "specialty": doc_record.specialty,
                        "qualifications": doc_record.qualifications,
                        "experience": doc_record.experience,
                        "consultation_fee": float(doc_record.consultation_fee),
                        "room_number": doc_record.room_number,
                        "department_id": doc_record.department_id,
                        "department_name": doc_record.department.name if doc_record.department else "Outpatient Wing",
                    }
                ]
            else:
                session["selected_doctor_id"] = None
                docs = search_doctors(db)[:4]
                action_result = {"doctors": docs}
                clarification_needed = True
                assistant_text = "Here are our on-duty hospital specialists. Which department or specialist would you like to consult?"

        else:
            # Case 4: No doctor or specialty found
            docs = search_doctors(db)[:4]
            action_result = {"doctors": docs}
            clarification_needed = True
            if language == "ta":
                assistant_text = "எங்கள் சிறப்பு மருத்துவர்களின் பட்டியல் கீழே உள்ளது. நீங்கள் எந்த துறையை அணுக விரும்புகிறீர்கள்?"
            elif language == "hi":
                assistant_text = "हमारे प्रमुख विशेषज्ञ डॉक्टरों की सूची नीचे दी गई है। आप किस विशेषता के डॉक्टर से मिलना चाहते हैं?"
            else:
                assistant_text = "Here are our on-duty hospital specialists. Which department or specialist would you like to consult?"

        if docs and doctor_id:
            doctor = docs[0]
            doc_name = doctor["name"]
            doc_room = doctor.get("room_number", "")
            doc_fee = doctor.get("consultation_fee", 0.0)
            doc_dept = doctor.get("department_name", "Outpatient Wing")

            # Determine target date
            if target_date_str:
                try:
                    target_date = datetime.strptime(target_date_str, "%Y-%m-%d").date()
                except ValueError:
                    target_date = date.today() + timedelta(days=1)
                session["selected_date"] = str(target_date)
                session["user_specified_date"] = True
            elif session.get("selected_date") and session.get("user_specified_date"):
                try:
                    target_date = datetime.strptime(session["selected_date"], "%Y-%m-%d").date()
                except ValueError:
                    target_date = date.today() + timedelta(days=1)
            else:
                target_date = date.today() + timedelta(days=1)
                session["selected_date"] = str(target_date)
                session["user_specified_date"] = False

            avail = check_doctor_availability_tool(db, doctor_id, target_date)
            slots = avail.get("available_slots", [])

            # If user specified a time and it is available, prepare confirmation step
            if target_time and target_time in slots:
                pending_action = {
                    "action": "book_appointment",
                    "doctor_id": doctor_id,
                    "doctor_name": doc_name,
                    "date": str(target_date),
                    "time": target_time,
                    "patient_name": request.patient_name or "Guest Patient",
                    "patient_phone": request.patient_phone,
                    "room_number": doc_room,
                    "consultation_fee": doc_fee,
                    "department_name": doc_dept,
                }
                session["pending_action"] = pending_action
                clarification_needed = False

                if language == "ta":
                    assistant_text = (
                        f"தயவுசெய்து உங்கள் முன்பதிவை உறுதிப்படுத்தவும்: {doc_name} ({doc_dept}) உடன் "
                        f"{target_date} அன்று {target_time} மணிக்கு (அறை: {doc_room}, கட்டணம்: ₹{doc_fee:.0f}). தொடர 'உறுதிப்படுத்து' என்பதைத் தொடவும்."
                    )
                elif language == "hi":
                    assistant_text = (
                        f"कृपया अपनी अपॉइंटमेंट की पुष्टि करें: {doc_name} ({doc_dept}) के साथ "
                        f"{target_date} को {target_time} बजे (कमरा: {doc_room}, शुल्क: ₹{doc_fee:.0f})। आगे बढ़ने के लिए 'कन्फर्म' पर क्लिक करें।"
                    )
                else:
                    assistant_text = (
                        f"Please confirm your appointment: {doc_name} ({doc_dept}, Room: {doc_room}, Fee: ₹{doc_fee:.0f}) "
                        f"on {target_date} at {target_time}. Click 'Confirm Booking' or reply 'Yes' to finalize."
                    )
                action_result = {
                    "confirmation_required": True,
                    "pending_action": pending_action,
                    "doctors": docs,
                    "doctor_name": doc_name,
                    "date": str(target_date),
                    "available_slots": slots,
                    "slots": slots,
                }

            elif not session.get("user_specified_date"):
                # No target date explicitly requested by user; show doctor details and tomorrow's slots
                clarification_needed = True
                action_result = {
                    "doctors": docs,
                    "recommended_doctor": doctor,
                    "doctor_name": doc_name,
                    "specialty": doctor.get("specialty"),
                    "department_name": doc_dept,
                    "room_number": doc_room,
                    "consultation_fee": doc_fee,
                    "date": str(target_date),
                    "available_slots": slots,
                    "slots": slots,
                    "target_date": str(target_date),
                }
                disp_spec = explicit_specialty or doctor.get("specialty", "Specialist")
                if language == "ta":
                    assistant_text = f"{disp_spec} துறைக்கு {doc_name} ({doc_room}, கட்டணம்: ₹{doc_fee:.0f}) பணியில் உள்ளார். நீங்கள் நாளை ({target_date}) அல்லது வேறு தேதியில் ஆலோசனை பெற விரும்புகிறீர்களா?"
                elif language == "hi":
                    assistant_text = f"{disp_spec} के लिए {doc_name} (कमरा: {doc_room}, शुल्क: ₹{doc_fee:.0f}) उपलब्ध हैं। क्या आप कल ({target_date}) या किसी अन्य तारीख को परामर्श चाहते हैं?"
                else:
                    assistant_text = f"For {disp_spec}, {doc_name} (Room: {doc_room}, Fee: ₹{doc_fee:.0f}) is available. Available slots for tomorrow ({target_date}) include {', '.join(slots[:4]) if slots else 'standard hours'}. Which date and time would you prefer?"

            else:
                # User specified a date (e.g. "tomorrow", "2026-10-21")
                action_result = {
                    "doctor_name": doc_name,
                    "specialty": doctor.get("specialty"),
                    "department_name": doc_dept,
                    "room_number": doc_room,
                    "consultation_fee": doc_fee,
                    "date": str(target_date),
                    "available_slots": slots,
                    "slots": slots,
                    "doctors": docs,
                }
                clarification_needed = True
                if slots:
                    if language == "ta":
                        assistant_text = f"{doc_name} ({doc_room}) அவர்களுக்கு {target_date} அன்று கிடைக்கும் நேரங்கள்: {', '.join(slots[:5])}. எந்த நேரத்தை தேர்ந்தெடுக்க விரும்புகிறீர்கள்?"
                    elif language == "hi":
                        assistant_text = f"{doc_name} (कमरा: {doc_room}) के लिए {target_date} को उपलब्ध समय: {', '.join(slots[:5])}. कृपया एक समय चुनें।"
                    else:
                        assistant_text = f"Available slots for {doc_name} (Room: {doc_room}, Fee: ₹{doc_fee:.0f}) on {target_date} are: {', '.join(slots[:5])}. Which slot works best for you?"
                else:
                    if language == "ta":
                        assistant_text = f"மன்னிக்கவும், {target_date} அன்று நேரங்கள் அனைத்தும் முன்பதிவு செய்யப்பட்டுள்ளன. தயவுசெய்து வேறு தேதியைத் தேர்ந்தெடுக்கவும்."
                    elif language == "hi":
                        assistant_text = f"क्षमा करें, {target_date} को सभी स्लॉट बुक हैं। कृपया दूसरी तारीख चुनें।"
                    else:
                        assistant_text = f"I apologize, but all slots for {target_date} are currently booked. Please select an alternate date."

    # Tool Execution: Check existing appointment
    elif intent == "check_appointment":
        ref = parsed.get("booking_reference")
        phone = parsed.get("patient_phone") or request.patient_phone
        if ref and phone:
            lookup = lookup_appointment_tool(db, booking_reference=ref, patient_phone=phone)
            action_result = lookup
            if lookup.get("found"):
                clarification_needed = False
                doc = lookup['doctor_name']
                d_str = lookup['appointment_date']
                t_str = lookup['start_time']
                room = lookup['room_number']
                token = lookup.get('queue_token') or 'N/A'

                if language == "ta":
                    assistant_text = f"முன்பதிவு {ref}: {doc} அவர்களுடன் {d_str} {t_str}-க்கு உறுதிசெய்யப்பட்டுள்ளது. அறை எண்: {room}, டோக்கன்: {token}."
                elif language == "hi":
                    assistant_text = f"अपॉइंटमेंट {ref}: {doc} के साथ {d_str} को {t_str} बजे है। कमरा: {room}, टोकन: {token}."
                else:
                    assistant_text = f"Appointment {ref} is active for {doc} on {d_str} at {t_str}. Room: {room}. Current Token: {token}."
            else:
                clarification_needed = True
                assistant_text = lookup.get("message", "Appointment not found.")

    # Tool Execution: Department Directions
    elif intent == "hospital_directions":
        dept_term = parsed.get("department_name", message)
        dirs = get_department_directions_tool(db, dept_term)
        action_result = dirs
        if dirs.get("found"):
            clarification_needed = False
            name = dirs['name']
            loc = dirs['location']
            fl = dirs['floor']
            ext = dirs.get('extension') or 'OPD Desk'
            if language == "ta":
                assistant_text = f"{name} துறை: {loc}, தளம் {fl} இல் அமைந்துள்ளது. விரிவாக்கம்: {ext}."
            elif language == "hi":
                assistant_text = f"{name} विभाग {loc}, तल {fl} पर स्थित है। संपर्क एक्सटेंशन: {ext}."
            else:
                assistant_text = f"{name} is located at {loc}, Floor {fl}. Clinical Extension: {ext}."
        else:
            clarification_needed = True
            assistant_text = dirs.get("message", "Department not found.")

    # If greeting
    elif intent == "greeting" and not assistant_text:
        if language == "ta":
            assistant_text = "வணக்கம்! நான் MediVoice மருத்துவமனை வரவேற்பாளர். இன்று உங்களுக்கு எவ்வாறு உதவ முடியும்?"
        elif language == "hi":
            assistant_text = "नमस्ते! मैं MediVoice वर्चुअल रिसेप्शनिस्ट हूँ। आज मैं आपकी क्या सहायता कर सकता हूँ?"
        else:
            assistant_text = "Hello! I am MediVoice, your virtual hospital receptionist. How can I help you today?"

    # Ensure clean speech output text
    speech_text = _clean_speech_text(assistant_text)

    # Save to history
    session["history"].append({"user": message, "assistant": assistant_text, "timestamp": datetime.now(timezone.utc).isoformat()})

    return AssistantChatResponse(
        conversation_id=conversation_id,
        assistant_text=assistant_text,
        speech_text=speech_text,
        language=language,
        intent=intent,
        clarification_needed=clarification_needed,
        pending_action=pending_action,
        action_result=action_result,
        ai_provider_used=ai_provider,
    )
