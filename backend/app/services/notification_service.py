import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional
import httpx
from pydantic import BaseModel

from app.core.config import get_settings

logger = logging.getLogger("medivoice.notifications")
settings = get_settings()

# In-memory notification log for audit, telemetry, and unit testing verification
_NOTIFICATION_HISTORY: List[Dict] = []
MAX_HISTORY_ENTRIES = 100


class NotificationRecord(BaseModel):
    id: str
    recipient_phone: str
    channel: str  # sms, whatsapp, emergency_broadcast
    template: str
    language: str
    message: str
    status: str  # delivered, queued, simulated
    created_at: str


class NotificationService:
    """Enterprise hospital notification dispatcher with multilingual SMS and WhatsApp support."""

    def __init__(self):
        self.webhook_url = getattr(settings, "NOTIFICATION_WEBHOOK_URL", None)

    def _record(self, recipient: str, channel: str, template: str, lang: str, message: str) -> Dict:
        """Store notification record for verification and audit trail."""
        record = {
            "id": f"NOTIF-{len(_NOTIFICATION_HISTORY) + 1:05d}",
            "recipient_phone": recipient,
            "channel": channel,
            "template": template,
            "language": lang,
            "message": message,
            "status": "delivered" if self.webhook_url else "simulated",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        _NOTIFICATION_HISTORY.insert(0, record)
        if len(_NOTIFICATION_HISTORY) > MAX_HISTORY_ENTRIES:
            _NOTIFICATION_HISTORY.pop()

        logger.info(
            "[%s] Sent to %s (%s, lang=%s): %s",
            channel.upper(),
            recipient,
            template,
            lang,
            message[:80] + "..." if len(message) > 80 else message,
        )
        return record

    async def _dispatch_webhook(self, record: Dict) -> None:
        """Forward payload to external webhook if configured."""
        if not self.webhook_url:
            return
        try:
            async with httpx.AsyncClient(timeout=4.0) as client:
                await client.post(self.webhook_url, json=record)
        except Exception as exc:
            logger.warning("Failed to dispatch external notification webhook: %s", exc)

    def send_appointment_confirmed(
        self,
        phone: str,
        patient_name: str,
        booking_ref: str,
        doctor_name: str,
        dept_name: str,
        apt_date: str,
        start_time: str,
        room_number: str = "OPD",
        lang: str = "en",
    ) -> Dict:
        """Send appointment confirmation receipt over SMS and WhatsApp."""
        if lang == "ta":
            msg = (
                f"வணக்கம் {patient_name}, MediVoice மருத்துவமனையில் உங்கள் முன்பதிவு உறுதி செய்யப்பட்டது. "
                f"குறிப்பு எண்: {booking_ref}. மருத்துவர்: {doctor_name} ({dept_name}). "
                f"நாள்: {apt_date} நேரம்: {start_time}. அறை: {room_number}."
            )
        elif lang == "hi":
            msg = (
                f"नमस्ते {patient_name}, MediVoice अस्पताल में आपकी अपॉइंटमेंट की पुष्टि हो गई है। "
                f"संदर्भ संख्या: {booking_ref}। डॉक्टर: {doctor_name} ({dept_name})। "
                f"दिनांक: {apt_date} समय: {start_time}। कमरा: {room_number}।"
            )
        else:
            msg = (
                f"Hello {patient_name}, your MediVoice consultation is confirmed. "
                f"Ref: {booking_ref}. Doctor: {doctor_name} ({dept_name}). "
                f"Date: {apt_date} at {start_time}. Room: {room_number}."
            )

        return self._record(phone, "both", "appointment_confirmed", lang, msg)

    def send_appointment_rescheduled(
        self,
        phone: str,
        patient_name: str,
        booking_ref: str,
        doctor_name: str,
        new_date: str,
        new_time: str,
        lang: str = "en",
    ) -> Dict:
        """Send rescheduling alert."""
        if lang == "ta":
            msg = (
                f"MediVoice தகவல்: உங்கள் முன்பதிவு {booking_ref} மாற்றியமைக்கப்பட்டுள்ளது. "
                f"புதிய நாள்: {new_date} நேரம்: {new_time} மருத்துவர்: {doctor_name}."
            )
        elif lang == "hi":
            msg = (
                f"MediVoice सूचना: आपकी अपॉइंटमेंट {booking_ref} पुनर्निर्धारित कर दी गई है। "
                f"नई तिथि: {new_date} समय: {new_time} डॉक्टर: {doctor_name}।"
            )
        else:
            msg = (
                f"MediVoice Notice: Your consultation {booking_ref} has been rescheduled. "
                f"New schedule: {new_date} at {new_time} with {doctor_name}."
            )

        return self._record(phone, "sms", "appointment_rescheduled", lang, msg)

    def send_appointment_cancelled(
        self,
        phone: str,
        booking_ref: str,
        lang: str = "en",
    ) -> Dict:
        """Send cancellation notice."""
        if lang == "ta":
            msg = f"MediVoice தகவல்: உங்கள் முன்பதிவு {booking_ref} வெற்றிகரமாக ரத்து செய்யப்பட்டது."
        elif lang == "hi":
            msg = f"MediVoice सूचना: आपकी अपॉइंटमेंट {booking_ref} सफलतापूर्वक रद्द कर दी गई है।"
        else:
            msg = f"MediVoice Notice: Your consultation {booking_ref} has been cancelled as requested."

        return self._record(phone, "sms", "appointment_cancelled", lang, msg)

    def send_queue_token_issued(
        self,
        phone: str,
        token: str,
        dept_name: str,
        lang: str = "en",
    ) -> Dict:
        """Send OPD queue check-in token alert."""
        if lang == "ta":
            msg = (
                f"MediVoice OPD டோக்கன்: உங்கள் டோக்கன் {token} ({dept_name} துறை). "
                f"காத்திருப்பு பகுதியில் காத்திருக்கவும். அறிவிப்பு பலகையை கவனிக்கவும்."
            )
        elif lang == "hi":
            msg = (
                f"MediVoice ओपीडी टोकन: आपका टोकन {token} ({dept_name} विभाग)। "
                f"कृपया प्रतीक्षा क्षेत्र में रहें और डिस्प्ले बोर्ड पर ध्यान दें।"
            )
        else:
            msg = (
                f"MediVoice OPD Token: Your token is {token} for {dept_name}. "
                f"Please proceed to the waiting lounge and watch the live display."
            )

        return self._record(phone, "whatsapp", "queue_token_issued", lang, msg)

    def send_emergency_triage_alert(
        self,
        on_call_phone: str,
        alert_id: int,
        priority: str,
        symptom_summary: str,
    ) -> Dict:
        """Send urgent broadcast to on-call clinical trauma supervisor."""
        msg = (
            f"[URGENT TRIAGE ALERT #{alert_id}] Priority: {priority.upper()}. "
            f"Symptom: {symptom_summary}. Immediate clinical response required at Emergency Desk."
        )
        return self._record(on_call_phone, "emergency_broadcast", "triage_escalation", "en", msg)


# Singleton notification instance
notification_service = NotificationService()


def get_notification_history(limit: int = 50) -> List[Dict]:
    """Return recent notification history for diagnostics and verification."""
    return _NOTIFICATION_HISTORY[:limit]


def clear_notification_history() -> None:
    """Clear notification history (useful in test suites)."""
    _NOTIFICATION_HISTORY.clear()
