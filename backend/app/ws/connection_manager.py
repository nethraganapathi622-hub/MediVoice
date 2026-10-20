"""WebSocket Connection Manager for MediVoice Real-Time Infrastructure.

ARCHITECTURAL NOTES:
-------------------
1. Scope & Concurrency:
   This connection manager is an in-memory manager designed for a single backend process.
   Connections are held directly in the process's memory space.

2. Multi-Worker & Multi-Instance Limitation:
   In multi-worker (e.g. multiple Uvicorn workers) or horizontally scaled multi-instance
   deployments (e.g. Kubernetes pods or Docker replicas behind a load balancer), an in-memory
   manager CANNOT distribute events across processes. To scale horizontally, a shared event
   broker (such as Redis Pub/Sub, NATS, or RabbitMQ) must be introduced to distribute events
   across all worker nodes.

3. Transactional Outbox Pattern for Durable Delivery:
   In-memory event publishing is fire-and-forget; if the backend process crashes or restarts,
   in-flight events are lost. To guarantee at-least-once, crash-resilient event delivery,
   a Transactional Outbox pattern should be employed: events are written to an `outbox` table
   within the same database transaction as the business entity, and an asynchronous relay
   worker polls the outbox, broadcasts the events, and marks them processed.
"""

import asyncio
from datetime import datetime, timezone
import json
import logging
from typing import Any, Dict, Optional, Set
import uuid

from fastapi import WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from app.core.security import StaffUser, verify_staff_access_token

logger = logging.getLogger("medivoice.ws")


class EventEnvelope(BaseModel):
    event_id: str
    event_type: str
    timestamp: str
    payload: Dict[str, Any]


class ClientSession:
    def __init__(self, websocket: WebSocket, is_staff: bool = False, staff_info: Optional[StaffUser] = None):
        self.session_id: str = f"ws_sess_{uuid.uuid4().hex[:12]}"
        self.websocket: WebSocket = websocket
        self.is_staff: bool = is_staff
        self.staff_info: Optional[StaffUser] = staff_info
        self.connected_at: datetime = datetime.now(timezone.utc)


class WebSocketManager:
    """Manages active WebSocket connections, authorization states, and event broadcasting."""

    def __init__(self):
        # Maps active WebSocket instance -> ClientSession
        self._connections: Dict[WebSocket, ClientSession] = {}
        self._lock = asyncio.Lock()

    @property
    def total_connections(self) -> int:
        return len(self._connections)

    @property
    def staff_connections_count(self) -> int:
        return sum(1 for sess in self._connections.values() if sess.is_staff)

    @property
    def public_connections_count(self) -> int:
        return sum(1 for sess in self._connections.values() if not sess.is_staff)

    async def register_connection(
        self,
        websocket: WebSocket,
        is_staff: bool = False,
        staff_info: Optional[StaffUser] = None,
    ) -> ClientSession:
        """Register an accepted WebSocket connection into the active pool."""
        session = ClientSession(websocket=websocket, is_staff=is_staff, staff_info=staff_info)
        async with self._lock:
            self._connections[websocket] = session
        logger.info(
            "WebSocket connected: %s (Type: %s, Total: %d)",
            session.session_id,
            "Staff" if is_staff else "Public",
            len(self._connections),
        )
        return session

    async def unregister_connection(self, websocket: WebSocket):
        """Cleanly remove a disconnected socket from the active pool."""
        async with self._lock:
            session = self._connections.pop(websocket, None)
        if session:
            logger.info("WebSocket disconnected: %s (Remaining: %d)", session.session_id, len(self._connections))

    async def upgrade_to_staff(self, websocket: WebSocket, token: str) -> Optional[StaffUser]:
        """Validate staff JWT token and upgrade the active session to staff scope."""
        try:
            staff_user = verify_staff_access_token(token)
            async with self._lock:
                if websocket in self._connections:
                    self._connections[websocket].is_staff = True
                    self._connections[websocket].staff_info = staff_user
            logger.info(
                "WebSocket upgraded to staff: %s (Staff: %s, Role: %s)",
                self._connections.get(websocket, ClientSession(websocket)).session_id,
                staff_user.staff_id,
                staff_user.role,
            )
            return staff_user
        except Exception as e:
            logger.warning("Staff WebSocket upgrade failed: %s", str(e))
            return None

    def create_envelope(self, event_type: str, payload: Dict[str, Any]) -> str:
        """Format a structured JSON event envelope."""
        envelope = {
            "event_id": f"evt_{uuid.uuid4().hex[:16]}",
            "event_type": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "payload": payload,
        }
        return json.dumps(envelope)

    async def _safe_send(self, websocket: WebSocket, message: str) -> bool:
        """Send message safely, catching transport exceptions without crashing."""
        try:
            await websocket.send_text(message)
            return True
        except (WebSocketDisconnect, RuntimeError, ConnectionResetError) as err:
            logger.debug("Failed sending to socket, marking for eviction: %s", str(err))
            return False

    async def broadcast(self, event_type: str, payload: Dict[str, Any], scope: str = "public"):
        """Broadcast an event across connections based on permission scope.

        Scopes:
        - "public": Broadcast to all connected clients (both public patients and staff).
        - "staff": Broadcast STRICTLY to authenticated staff clients.
        """
        message_json = self.create_envelope(event_type, payload)

        async with self._lock:
            if scope == "staff":
                recipients = [ws for ws, sess in self._connections.items() if sess.is_staff]
            else:
                recipients = list(self._connections.keys())

        if not recipients:
            logger.debug("No active WebSocket listeners for event '%s' (scope=%s)", event_type, scope)
            return

        # Broadcast asynchronously without blocking database transactions
        results = await asyncio.gather(
            *[self._safe_send(ws, message_json) for ws in recipients],
            return_exceptions=True,
        )

        # Evict dead connections discovered during send
        dead_sockets = [
            ws for ws, success in zip(recipients, results)
            if success is False or isinstance(success, Exception)
        ]
        if dead_sockets:
            async with self._lock:
                for dead_ws in dead_sockets:
                    self._connections.pop(dead_ws, None)
            logger.debug("Evicted %d broken WebSocket connections during broadcast", len(dead_sockets))


# Global singleton instance for the single-process backend
ws_manager = WebSocketManager()
