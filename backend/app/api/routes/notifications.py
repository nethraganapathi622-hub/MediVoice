from typing import List
from fastapi import APIRouter, Query

from app.services.notification_service import NotificationRecord, get_notification_history

router = APIRouter(prefix="/notifications", tags=["Hospital Notifications"])


@router.get("/recent", response_model=List[NotificationRecord], summary="List recently dispatched SMS/WhatsApp notifications")
def list_recent_notifications(
    limit: int = Query(50, ge=1, le=100, description="Maximum notifications to return"),
):
    """Retrieve audit trail of recent SMS, WhatsApp, and emergency broadcast messages."""
    return get_notification_history(limit=limit)
