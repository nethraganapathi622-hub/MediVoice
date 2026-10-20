import { useState, useEffect } from "react"
import { wsService } from "../services/websocket"

/**
 * React hook to observe live WebSocket connection status.
 * Returns: "connected" | "connecting" | "reconnecting" | "offline"
 */
export function useWebSocketStatus() {
  const [status, setStatus] = useState(wsService.getStatus())

  useEffect(() => {
    const unsubscribe = wsService.addStatusListener((newStatus) => {
      setStatus(newStatus)
    })
    return unsubscribe
  }, [])

  return status
}

/**
 * React hook to listen for specific WebSocket events.
 * Automatically cleans up subscription on component unmount.
 *
 * @param {string} eventType - e.g. "queue.*", "appointment.created", "alert.*"
 * @param {Function} handler - callback receiving (payload, rawEnvelope)
 */
export function useWebSocketEvent(eventType, handler) {
  useEffect(() => {
    if (!eventType || typeof handler !== "function") return

    const unsubscribe = wsService.subscribe(eventType, handler)
    return unsubscribe
  }, [eventType, handler])
}
