import re
from typing import Dict, List, Optional
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.alert import TriageAlert
from app.ws.events import emit_alert_created

# Emergency keywords & clinical triggers
EMERGENCY_TRIGGERS: Dict[str, List[str]] = {
    "en": [
        "chest pain",
        "heart attack",
        "cardiac arrest",
        "cannot breathe",
        "can't breathe",
        "difficulty breathing",
        "shortness of breath",
        "stroke",
        "facial drooping",
        "slurred speech",
        "sudden numbness",
        "unconscious",
        "unresponsive",
        "fainted",
        "fainting",
        "heavy bleeding",
        "profuse bleeding",
        "severe bleeding",
        "poison",
        "poisoning",
        "swallowed poison",
        "anaphylaxis",
        "allergic shock",
        "severe trauma",
        "head injury",
        "seizure",
        "convulsion",
        "choking",
        "overdose",
        "collapsed",
    ],
    "ta": [
        "நெஞ்சு வலி",
        "நெஞ்சுவலி",
        "மாரடைப்பு",
        "மூச்சு விட முடியவில்லை",
        "மூச்சுத்திணறல்",
        "மயக்கம்",
        "சுயநினைவின்மை",
        "பக்கவாதம்",
        "ரத்தப்போக்கு",
        "இரத்தப்போக்கு",
        "விஷம்",
        "கடுமையான காயம்",
        "விபத்து",
        "வலிப்பு",
        "மூச்சு அடைப்பு",
        "உயிருக்கு ஆபத்து",
    ],
    "hi": [
        "सीने में दर्द",
        "दिल का दौरा",
        "सांस नहीं आ रही",
        "सांस लेने में तकलीफ",
        "सांस फूलना",
        "बेहोश",
        "बेहोशी",
        "लकवा",
        "रक्तस्राव",
        "खून बह रहा",
        "जहर",
        "गंभीर चोट",
        "दुर्घटना",
        "दौरा",
        "दम घुटना",
        "हार्ट अटैक",
    ],
}


def detect_emergency_symptoms(text: str) -> Optional[Dict[str, str]]:
    """Conservatively check if text indicates an acute clinical emergency across languages.

    Returns trigger details if acute symptoms match, or None if safe.
    """
    if not text:
        return None

    lowered = text.lower().strip()

    for lang, triggers in EMERGENCY_TRIGGERS.items():
        for trigger in triggers:
            # Word boundary regex for latin letters, substring matching for Indic scripts
            if lang == "en":
                pattern = r"\b" + re.escape(trigger) + r"\b"
                if re.search(pattern, lowered):
                    return {"matched_trigger": trigger, "language": lang}
            else:
                if trigger in lowered:
                    return {"matched_trigger": trigger, "language": lang}

    return None


def get_emergency_response_text(language: str, settings=None) -> Dict[str, str]:
    """Return authoritative emergency guidance in the requested language."""
    if settings is None:
        settings = get_settings()

    phone = settings.EMERGENCY_CONTACT_PHONE
    ambulance = settings.EMERGENCY_AMBULANCE_NUMBER

    if language == "ta":
        text = (
            f"அவசர மருத்துவ எச்சரிக்கை! நீங்கள் விவரித்த அறிகுறிகள் தீவிர அவசர சிகிச்சை தேவைப்படுவதைக் குறிக்கின்றன. "
            f"உடனடியாக {ambulance} (ஆம்புலன்ஸ்) அல்லது மருத்துவமனை அவசர பிரிவை {phone} என்ற எண்ணில் அழைக்கவும். "
            f"மருத்துவமனை ஊழியர்களுக்கு அவசர அறிவிப்பு அனுப்பப்பட்டுள்ளது."
        )
        speech = f"அவசர மருத்துவ எச்சரிக்கை! தயவுசெய்து உடனடியாக {ambulance} ஆம்புலன்ஸை அழைக்கவும்."
    elif language == "hi":
        text = (
            f"आपातकालीन चिकित्सा चेतावनी! आपके बताए गए लक्षण गंभीर आपातकाल का संकेत देते हैं। "
            f"कृपया तुरंत {ambulance} (एम्बुलेंस) या अस्पताल कैजुअल्टी डेस्क {phone} पर कॉल करें। "
            f"अस्पताल स्टाफ को आपातकालीन अलर्ट भेज दिया गया है।"
        )
        speech = f"आपातकालीन चिकित्सा चेतावनी! कृपया तुरंत {ambulance} एम्बुलेंस को कॉल करें।"
    else:
        text = (
            f"CRITICAL MEDICAL ALERT: The symptoms you described require immediate emergency intervention. "
            f"Please call {ambulance} (Ambulance) or reach the Hospital Casualty Desk at {phone} immediately. "
            f"An urgent notification has been dispatched to the hospital emergency triage team."
        )
        speech = f"Critical medical alert! Please call {ambulance} emergency services immediately."

    return {"text": text, "speech": speech}


def trigger_emergency_alert(
    db: Session,
    symptoms: str,
    location: Optional[str] = None,
    patient_phone: Optional[str] = None,
) -> TriageAlert:
    """Persist a critical triage alert and broadcast it to authorized clinical staff."""
    desc = f"Voice Reception Escalation: {symptoms.strip()}"
    if patient_phone:
        desc += f" [Contact: {patient_phone}]"

    alert = TriageAlert(
        priority="critical",
        alert_type="trauma_priority",
        description=desc,
        location=location or "Patient Virtual Reception Intake",
        status="active",
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)

    # Real-time WebSocket notification strictly to staff channel
    emit_alert_created(
        alert_id=alert.id,
        priority=alert.priority,
        alert_type=alert.alert_type,
        description=alert.description,
        department_id=alert.department_id,
        location=alert.location,
        created_at=str(alert.created_at),
    )

    # Dispatch urgent trauma broadcast
    try:
        from app.services.notification_service import notification_service
        settings = get_settings()
        notification_service.send_emergency_triage_alert(
            on_call_phone=settings.EMERGENCY_CONTACT_PHONE,
            alert_id=alert.id,
            priority=alert.priority,
            symptom_summary=symptoms[:100],
        )
    except Exception as n_err:
        pass

    return alert
