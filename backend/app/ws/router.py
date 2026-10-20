import asyncio
import json
import logging
from typing import Dict, Any
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status
from pydantic import BaseModel

from app.ws.connection_manager import ws_manager

logger = logging.getLogger("medivoice.ws")
router = APIRouter(tags=["WebSockets"])


class WebSocketStatusResponse(BaseModel):
    total_connections: int
    staff_connections: int
    public_connections: int
    manager_mode: str = "in-memory (single-process)"


@router.get("/api/ws/status", response_model=WebSocketStatusResponse, summary="Get WebSocket connection statistics")
def get_ws_status() -> WebSocketStatusResponse:
    """Return live metrics on active WebSocket connections."""
    return WebSocketStatusResponse(
        total_connections=ws_manager.total_connections,
        staff_connections=ws_manager.staff_connections_count,
        public_connections=ws_manager.public_connections_count,
    )


@router.websocket("/ws/events")
async def websocket_events_endpoint(websocket: WebSocket):
    """Unified WebSocket endpoint supporting public events and authenticated staff session upgrade."""
    await websocket.accept()
    session = await ws_manager.register_connection(websocket, is_staff=False)

    # Send initial connection acknowledgement with session metadata
    ack = {
        "type": "connection_established",
        "session_id": session.session_id,
        "scope": "public",
        "server_time": session.connected_at.isoformat(),
        "info": "Connected to MediVoice event bus. Send {'type': 'auth', 'token': '...'} for staff events.",
    }
    await websocket.send_text(json.dumps(ack))

    try:
        while True:
            raw_msg = await websocket.receive_text()
            try:
                data: Dict[str, Any] = json.loads(raw_msg)
            except json.JSONDecodeError:
                await websocket.send_text(
                    json.dumps({"type": "error", "message": "Malformed message: JSON expected"})
                )
                continue

            msg_type = data.get("type", "")

            # Heartbeat keepalive
            if msg_type == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))

            # Staff authentication handshake
            elif msg_type == "auth":
                token = data.get("token")
                if not token:
                    await websocket.send_text(
                        json.dumps({"type": "auth_error", "message": "Missing token parameter"})
                    )
                    continue

                staff_user = await ws_manager.upgrade_to_staff(websocket, token)
                if staff_user:
                    await websocket.send_text(
                        json.dumps(
                            {
                                "type": "auth_success",
                                "scope": "staff",
                                "staff": {
                                    "staff_id": staff_user.staff_id,
                                    "name": staff_user.name,
                                    "role": staff_user.role,
                                    "department": staff_user.department,
                                },
                            }
                        )
                    )
                else:
                    await websocket.send_text(
                        json.dumps(
                            {
                                "type": "auth_error",
                                "message": "Authentication failed: Invalid or expired staff access token",
                            }
                        )
                    )

            else:
                await websocket.send_text(
                    json.dumps({"type": "unknown_message", "received_type": msg_type})
                )

    except WebSocketDisconnect:
        await ws_manager.unregister_connection(websocket)
    except Exception as exc:
        logger.warning("Unexpected WebSocket error on %s: %s", session.session_id, str(exc))
        await ws_manager.unregister_connection(websocket)


@router.websocket("/ws/staff")
async def websocket_staff_endpoint(websocket: WebSocket):
    """Protected WebSocket endpoint strictly for authenticated hospital staff.

    Requires an immediate auth handshake within 5 seconds or connection closes with code 4003 (Forbidden).
    """
    await websocket.accept()

    try:
        # Await auth message with timeout
        raw_msg = await asyncio.wait_for(websocket.receive_text(), timeout=5.0)
        data = json.loads(raw_msg)

        if data.get("type") != "auth" or not data.get("token"):
            await websocket.send_text(
                json.dumps({"type": "auth_error", "message": "Initial auth message with token required"})
            )
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        token = data.get("token")
        from app.core.security import verify_staff_access_token

        try:
            staff_user = verify_staff_access_token(token)
        except Exception as e:
            await websocket.send_text(
                json.dumps({"type": "auth_error", "message": f"Invalid staff token: {str(e)}"})
            )
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        # Register as verified staff
        session = await ws_manager.register_connection(websocket, is_staff=True, staff_info=staff_user)
        await websocket.send_text(
            json.dumps(
                {
                    "type": "auth_success",
                    "session_id": session.session_id,
                    "scope": "staff",
                    "staff": {
                        "staff_id": staff_user.staff_id,
                        "name": staff_user.name,
                        "role": staff_user.role,
                        "department": staff_user.department,
                    },
                }
            )
        )

        while True:
            raw_msg = await websocket.receive_text()
            try:
                data = json.loads(raw_msg)
            except json.JSONDecodeError:
                continue

            if data.get("type") == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))

    except asyncio.TimeoutError:
        logger.warning("Staff WebSocket closed: handshake timed out without credentials")
        try:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        except Exception:
            pass
    except WebSocketDisconnect:
        await ws_manager.unregister_connection(websocket)
    except Exception as exc:
        logger.warning("Staff WebSocket error: %s", str(exc))
        await ws_manager.unregister_connection(websocket)
