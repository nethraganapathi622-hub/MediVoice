import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.schemas.assistant import (
    AssistantChatRequest,
    AssistantChatResponse,
    AssistantConfigResponse,
    EmergencyAlertRequest,
)
from app.services.ai_assistant_service import handle_assistant_interaction
from app.services.emergency_detector import (
    get_emergency_response_text,
    trigger_emergency_alert,
)

logger = logging.getLogger("medivoice.assistant.router")
router = APIRouter(prefix="/assistant", tags=["AI Voice Assistant"])


@router.post("/chat", response_model=AssistantChatResponse, summary="Send query or recognized voice transcript to AI Assistant")
def chat_with_assistant(
    request: AssistantChatRequest,
    db: Session = Depends(get_db),
    settings = Depends(get_settings),
) -> AssistantChatResponse:
    """Multi-turn, multilingual conversational interaction with MediVoice AI Assistant.

    Processes patient intent in English, Tamil, or Hindi, extracts clinical entities,
    interfaces with real hospital appointment and department tools, and supports safe
    confirmation flows before appointment creation.
    """
    try:
        return handle_assistant_interaction(request=request, db=db, settings=settings)
    except Exception as exc:
        logger.exception("Error processing assistant interaction: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error processing assistant interaction",
        )


@router.post("/emergency", summary="Direct clinical emergency dispatch")
def dispatch_emergency_alert(
    request: EmergencyAlertRequest,
    db: Session = Depends(get_db),
):
    """Directly persist an acute clinical emergency triage alert and notify hospital staff via WebSockets."""
    settings = get_settings()
    alert = trigger_emergency_alert(
        db=db,
        symptoms=request.symptoms,
        location=request.location or "Patient Virtual Reception Intake",
        patient_phone=request.patient_phone,
    )

    resp_text = get_emergency_response_text(request.language or "en", settings)

    return {
        "status": "dispatched",
        "alert_id": alert.id,
        "priority": alert.priority,
        "alert_type": alert.alert_type,
        "guidance": resp_text["text"],
        "speech_guidance": resp_text["speech"],
        "emergency_phone": settings.EMERGENCY_CONTACT_PHONE,
        "ambulance_number": settings.EMERGENCY_AMBULANCE_NUMBER,
        "wing": "Ground Floor, Block A (Red Zone Entrance)",
    }


@router.get("/config", response_model=AssistantConfigResponse, summary="Get assistant capabilities and emergency contacts")
def get_assistant_config() -> AssistantConfigResponse:
    """Return public metadata regarding supported languages, active AI provider mode, and emergency numbers."""
    settings = get_settings()
    return AssistantConfigResponse(
        supported_languages=["en", "ta", "hi"],
        gemini_available=settings.has_gemini_key,
        gemini_model=settings.GEMINI_MODEL,
        emergency_phone=settings.EMERGENCY_CONTACT_PHONE,
        ambulance_number=settings.EMERGENCY_AMBULANCE_NUMBER,
    )
