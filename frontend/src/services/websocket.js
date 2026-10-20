// Centralized WebSocket Service for MediVoice Real-Time Infrastructure

import { getAuthStaff } from "./api"

const DEFAULT_WS_URL =
  import.meta.env.VITE_WS_URL ||
  `${window.location.protocol === "https:" ? "wss:" : "ws:"}//${window.location.hostname || "localhost"}:8000/ws/events`

class WebSocketService {
  constructor() {
    this.ws = null
    this.status = "offline" // "offline" | "connecting" | "connected" | "reconnecting"
    this.listeners = new Map() // eventType -> Set of callbacks
    this.statusListeners = new Set()
    this.reconnectAttempts = 0
    this.maxReconnectAttempts = 20
    this.baseDelayMs = 1000
    this.maxDelayMs = 10000
    this.reconnectTimer = null
    this.pingInterval = null
    this.url = DEFAULT_WS_URL
    this.isManualClose = false
  }

  getStatus() {
    return this.status
  }

  setStatus(newStatus) {
    if (this.status !== newStatus) {
      this.status = newStatus
      this.statusListeners.forEach((fn) => {
        try {
          fn(newStatus)
        } catch (e) {
          console.error("Error in WS status listener:", e)
        }
      })
    }
  }

  addStatusListener(fn) {
    this.statusListeners.add(fn)
    fn(this.status)
    return () => this.statusListeners.delete(fn)
  }

  connect(customUrl = null) {
    if (customUrl) this.url = customUrl

    // Avoid duplicate connections
    if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
      return
    }

    this.isManualClose = false
    this.setStatus(this.reconnectAttempts === 0 ? "connecting" : "reconnecting")

    try {
      this.ws = new WebSocket(this.url)

      this.ws.onopen = () => {
        this.reconnectAttempts = 0
        this.setStatus("connected")

        // Authenticate staff session if a signed token is stored
        const staffAuth = getAuthStaff()
        if (staffAuth?.access_token) {
          this.authenticateStaff(staffAuth.access_token)
        }

        // Start ping heartbeat
        this.startHeartbeat()

        // Notify subscribers of reconnect so pages refresh authoritative REST data
        this.emitInternalEvent("reconnect", { timestamp: new Date().toISOString() })
      }

      this.ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)

          // Handle system control messages
          if (data.type === "pong") return
          if (data.type === "connection_established") {
            return
          }
          if (data.type === "auth_success") {
            this.emitInternalEvent("auth_success", data.staff)
            return
          }

          // Handle structured broadcast envelope: { event_id, event_type, timestamp, payload }
          if (data.event_type) {
            this.dispatch(data.event_type, data.payload, data)
          }
        } catch (err) {
          console.warn("Non-JSON message received on WebSocket:", event.data, err)
        }
      }

      this.ws.onerror = (err) => {
        // Log minimal safe error notice
        console.warn("WebSocket transport error:", err?.message || "connection error")
      }

      this.ws.onclose = () => {
        this.stopHeartbeat()
        this.ws = null

        if (!this.isManualClose) {
          this.scheduleReconnect()
        } else {
          this.setStatus("offline")
        }
      }
    } catch (err) {
      console.warn("Error initiating WebSocket connection:", err)
      this.scheduleReconnect()
    }
  }

  authenticateStaff(token) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN && token) {
      this.ws.send(JSON.stringify({ type: "auth", token }))
    }
  }

  scheduleReconnect() {
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer)

    this.reconnectAttempts += 1
    this.setStatus("reconnecting")

    // Bounded exponential backoff with jitter: delay = min(base * 1.5^(attempt-1), max) + jitter
    const exponential = this.baseDelayMs * Math.pow(1.5, Math.min(this.reconnectAttempts - 1, 6))
    const jitter = Math.random() * 300
    const delay = Math.min(exponential + jitter, this.maxDelayMs)

    this.reconnectTimer = setTimeout(() => {
      this.connect()
    }, delay)
  }

  startHeartbeat() {
    this.stopHeartbeat()
    this.pingInterval = setInterval(() => {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        try {
          this.ws.send(JSON.stringify({ type: "ping" }))
        } catch {
          // ignore
        }
      }
    }, 25000)
  }

  stopHeartbeat() {
    if (this.pingInterval) {
      clearInterval(this.pingInterval)
      this.pingInterval = null
    }
  }

  disconnect() {
    this.isManualClose = true
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer)
    this.stopHeartbeat()
    if (this.ws) {
      this.ws.close()
      this.ws = null
    }
    this.setStatus("offline")
  }

  subscribe(eventType, callback) {
    if (!this.listeners.has(eventType)) {
      this.listeners.set(eventType, new Set())
    }
    this.listeners.get(eventType).add(callback)

    // Auto-connect if not currently active
    if (this.status === "offline") {
      this.connect()
    }

    return () => {
      const set = this.listeners.get(eventType)
      if (set) {
        set.delete(callback)
        if (set.size === 0) this.listeners.delete(eventType)
      }
    }
  }

  emitInternalEvent(eventType, payload) {
    this.dispatch(eventType, payload, { event_type: eventType, payload })
  }

  dispatch(eventType, payload, rawEnvelope) {
    // Exact match listeners
    const handlers = this.listeners.get(eventType)
    if (handlers) {
      handlers.forEach((fn) => {
        try {
          fn(payload, rawEnvelope)
        } catch (e) {
          console.error(`Error in WS listener for ${eventType}:`, e)
        }
      })
    }

    // Domain wildcard listeners (e.g., "queue.*")
    if (eventType.includes(".")) {
      const domain = eventType.split(".")[0]
      const wildcardHandlers = this.listeners.get(`${domain}.*`)
      if (wildcardHandlers) {
        wildcardHandlers.forEach((fn) => {
          try {
            fn(payload, rawEnvelope)
          } catch (e) {
            console.error(`Error in WS wildcard listener for ${domain}.*:`, e)
          }
        })
      }
    }

    // Catch-all listeners
    const allHandlers = this.listeners.get("*")
    if (allHandlers) {
      allHandlers.forEach((fn) => {
        try {
          fn(payload, rawEnvelope)
        } catch (e) {
          console.error("Error in WS global listener:", e)
        }
      })
    }
  }
}

export const wsService = new WebSocketService()
