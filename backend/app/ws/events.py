"""Event dispatcher for MediVoice database-backed real-time events.

Ensures strict privacy: patient PII, phone numbers, email addresses,
symptom narratives, and private medical notes are NEVER broadcast over WebSockets.
"""

import asyncio
import logging
from typing import Optional
from app.ws.connection_manager import ws_manager

logger = logging.getLogger("medivoice.events")


def _fire_and_forget(coro):
    """Schedule event broadcast as an asynchronous task without blocking DB transactions."""
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(coro)
    except RuntimeError:
        # If no running loop (e.g., synchronous tests), run via asyncio.run or ignore safely
        try:
            asyncio.run(coro)
        except Exception as e:
            logger.debug("Failed running event broadcast in synchronous fallback: %s", str(e))


def emit_appointment_created(
    appointment_id: int,
    booking_reference: str,
    doctor_id: int,
    department_id: int,
    appointment_date: str,
    start_time: str,
    end_time: str,
    status: str = "booked",
):
    """Broadcast appointment created event (PII-stripped)."""
    payload = {
        "appointment_id": appointment_id,
        "booking_reference": booking_reference,
        "doctor_id": doctor_id,
        "department_id": department_id,
        "appointment_date": str(appointment_date),
        "start_time": str(start_time),
        "end_time": str(end_time),
        "status": status,
    }
    _fire_and_forget(ws_manager.broadcast("appointment.created", payload, scope="public"))


def emit_appointment_rescheduled(
    appointment_id: int,
    booking_reference: str,
    doctor_id: int,
    department_id: int,
    appointment_date: str,
    start_time: str,
    end_time: str,
):
    """Broadcast appointment rescheduled event."""
    payload = {
        "appointment_id": appointment_id,
        "booking_reference": booking_reference,
        "doctor_id": doctor_id,
        "department_id": department_id,
        "appointment_date": str(appointment_date),
        "start_time": str(start_time),
        "end_time": str(end_time),
        "status": "rescheduled",
    }
    _fire_and_forget(ws_manager.broadcast("appointment.rescheduled", payload, scope="public"))


def emit_appointment_cancelled(
    appointment_id: int,
    booking_reference: str,
    doctor_id: int,
    department_id: int,
):
    """Broadcast appointment cancelled event."""
    payload = {
        "appointment_id": appointment_id,
        "booking_reference": booking_reference,
        "doctor_id": doctor_id,
        "department_id": department_id,
        "status": "cancelled",
    }
    _fire_and_forget(ws_manager.broadcast("appointment.cancelled", payload, scope="public"))


def emit_queue_checked_in(
    queue_id: int,
    token: str,
    appointment_id: int,
    department_id: int,
    priority: str,
    check_in_time: str,
):
    """Broadcast patient checked-in token event."""
    payload = {
        "queue_id": queue_id,
        "token": token,
        "appointment_id": appointment_id,
        "department_id": department_id,
        "priority": priority,
        "status": "waiting",
        "check_in_time": str(check_in_time),
    }
    _fire_and_forget(ws_manager.broadcast("queue.checked_in", payload, scope="public"))


def emit_queue_patient_called(
    queue_id: int,
    token: str,
    appointment_id: int,
    called_time: str,
    department_name: Optional[str] = None,
    doctor_name: Optional[str] = None,
    room_number: Optional[str] = None,
):
    """Broadcast queue patient called to desk event."""
    payload = {
        "queue_id": queue_id,
        "token": token,
        "appointment_id": appointment_id,
        "status": "called",
        "called_time": str(called_time),
        "department_name": department_name,
        "doctor_name": doctor_name,
        "room_number": room_number or "OPD Consultation Room",
    }
    _fire_and_forget(ws_manager.broadcast("queue.patient_called", payload, scope="public"))



def emit_queue_completed(
    queue_id: int,
    token: str,
    appointment_id: int,
    completed_time: str,
):
    """Broadcast queue patient completed event."""
    payload = {
        "queue_id": queue_id,
        "token": token,
        "appointment_id": appointment_id,
        "status": "completed",
        "completed_time": str(completed_time),
    }
    _fire_and_forget(ws_manager.broadcast("queue.completed", payload, scope="public"))


def emit_alert_created(
    alert_id: int,
    priority: str,
    alert_type: str,
    description: str,
    department_id: Optional[int],
    location: Optional[str],
    created_at: str,
):
    """Broadcast triage alert creation (STRICTLY to staff subscribers)."""
    payload = {
        "alert_id": alert_id,
        "priority": priority,
        "alert_type": alert_type,
        "description": description,
        "department_id": department_id,
        "location": location,
        "status": "active",
        "created_at": str(created_at),
    }
    _fire_and_forget(ws_manager.broadcast("alert.created", payload, scope="staff"))


def emit_alert_acknowledged(
    alert_id: int,
    acknowledged_by: str,
    acknowledged_at: str,
):
    """Broadcast triage alert acknowledgement (STRICTLY to staff subscribers)."""
    payload = {
        "alert_id": alert_id,
        "status": "acknowledged",
        "acknowledged_by": acknowledged_by,
        "acknowledged_at": str(acknowledged_at),
    }
    _fire_and_forget(ws_manager.broadcast("alert.acknowledged", payload, scope="staff"))
