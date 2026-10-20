from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import security_bearer, HTTPAuthorizationCredentials
from app.models.alert import TriageAlert
from app.schemas.alert import AlertAcknowledgeRequest, AlertCreate, AlertRead

router = APIRouter(prefix="/alerts", tags=["Alerts"])


@router.get("", response_model=List[AlertRead], summary="List hospital triage alerts")
def list_alerts(
    priority: Optional[str] = Query(None, description="Filter by priority: critical, moderate, advisory"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by alert status: active, acknowledged, resolved"),
    db: Session = Depends(get_db),
) -> List[TriageAlert]:
    """Retrieve operational triage and emergency notifications."""
    query = db.query(TriageAlert)
    if priority and priority.lower() != "all":
        query = query.filter(TriageAlert.priority == priority.lower())
    if status_filter and status_filter.lower() != "all":
        query = query.filter(TriageAlert.status == status_filter.lower())

    return query.order_by(TriageAlert.created_at.desc()).all()


@router.get("/{alert_id}", response_model=AlertRead, summary="Get alert details")
def get_alert(alert_id: int, db: Session = Depends(get_db)) -> TriageAlert:
    """Retrieve details for a specific triage alert."""
    alert = db.query(TriageAlert).filter(TriageAlert.id == alert_id).first()
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert with ID {alert_id} not found",
        )
    return alert


@router.post("", response_model=AlertRead, status_code=status.HTTP_201_CREATED, summary="Create triage alert")
def create_alert(payload: AlertCreate, db: Session = Depends(get_db)) -> TriageAlert:
    """Create a new clinical priority or operational alert."""
    alert = TriageAlert(
        priority=payload.priority,
        alert_type=payload.alert_type,
        description=payload.description,
        department_id=payload.department_id,
        patient_id=payload.patient_id,
        appointment_id=payload.appointment_id,
        location=payload.location,
        status="active",
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)

    # Broadcast alert.created event strictly after commit (staff scope)
    from app.ws.events import emit_alert_created
    emit_alert_created(
        alert_id=alert.id,
        priority=alert.priority,
        alert_type=alert.alert_type,
        description=alert.description,
        department_id=alert.department_id,
        location=alert.location,
        created_at=str(alert.created_at),
    )

    return alert


@router.post("/{alert_id}/acknowledge", response_model=AlertRead, summary="Acknowledge alert with staff validation")
def acknowledge_alert(
    alert_id: int,
    payload: AlertAcknowledgeRequest,
    x_staff_role: Optional[str] = Header(None, description="Clinical staff role verification header"),
    auth: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
    db: Session = Depends(get_db),
) -> TriageAlert:
    """Acknowledge a triage alert with staff validation requirements.

    Validates cryptographic Bearer token when provided, or verifies staff credentials.
    """
    alert = db.query(TriageAlert).filter(TriageAlert.id == alert_id).first()
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert with ID {alert_id} not found",
        )

    # Basic authorization check: verify staff identification credentials
    if not payload.staff_id or not payload.staff_name:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Staff ID and staff name must be provided to acknowledge clinical alerts",
        )

    staff_role = x_staff_role
    if auth and auth.credentials:
        from app.core.security import verify_staff_access_token
        staff_user = verify_staff_access_token(auth.credentials)
        staff_role = staff_user.role

    alert.status = "acknowledged"
    alert.acknowledged_at = datetime.now(timezone.utc)
    role_suffix = f" [{staff_role}]" if staff_role else ""
    alert.acknowledged_by = f"{payload.staff_name} ({payload.staff_id}){role_suffix}"

    db.commit()
    db.refresh(alert)

    # Broadcast alert.acknowledged strictly after commit (staff scope)
    from app.ws.events import emit_alert_acknowledged
    emit_alert_acknowledged(
        alert_id=alert.id,
        acknowledged_by=alert.acknowledged_by,
        acknowledged_at=str(alert.acknowledged_at),
    )

    return alert
