from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class AssistantChatRequest(BaseModel):
    """User query or speech transcript sent to MediVoice AI Assistant."""

    conversation_id: Optional[str] = Field(None, description="Client session conversation ID")
    message: str = Field(..., min_length=1, max_length=1000, description="Recognized speech transcript or typed query")
    language: str = Field(default="en", pattern="^(en|ta|hi)$", description="Selected language code: en, ta, or hi")
    confirmed_action: Optional[Dict[str, Any]] = Field(None, description="Explicitly confirmed appointment action payload")
    patient_name: Optional[str] = Field(None, max_length=150, description="Optional patient name for booking context")
    patient_phone: Optional[str] = Field(None, max_length=30, description="Optional patient phone for booking verification")


class EmergencyAlertRequest(BaseModel):
    """Direct clinical emergency dispatch request."""

    symptoms: str = Field(..., min_length=2, max_length=500, description="Description of acute symptoms")
    language: str = Field(default="en", pattern="^(en|ta|hi)$")
    location: Optional[str] = Field(None, max_length=150, description="Patient location within hospital or home")
    patient_phone: Optional[str] = Field(None, max_length=30)


class AssistantChatResponse(BaseModel):
    """Structured response from the MediVoice AI Assistant."""

    conversation_id: str
    assistant_text: str
    speech_text: str
    language: str
    intent: str
    clarification_needed: bool = False
    pending_action: Optional[Dict[str, Any]] = None
    action_result: Optional[Dict[str, Any]] = None
    error_state: Optional[str] = None
    ai_provider_used: str  # "gemini" | "rule_based_fallback" | "unavailable"


class AssistantConfigResponse(BaseModel):
    """Public assistant capabilities and emergency contacts."""

    supported_languages: List[str]
    gemini_available: bool
    gemini_model: str
    emergency_phone: str
    ambulance_number: str
