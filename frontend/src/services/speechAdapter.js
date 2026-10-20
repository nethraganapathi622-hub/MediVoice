// Pluggable Speech Recognition & Synthesis Adapter for MediVoice
// Encapsulates Web Speech API with support for English (en-US), Tamil (ta-IN), and Hindi (hi-IN)
// Designed for drop-in replacement with Cloud STT/TTS providers (Google Cloud Speech, Azure, ElevenLabs).

const BROWSER_LOCALE_MAP = {
  en: "en-US",
  ta: "ta-IN",
  hi: "hi-IN",
}

export class BrowserSpeechAdapter {
  constructor() {
    this.recognition = null
    this.currentUtterance = null
    this.isListening = false
    this.isSpeaking = false
  }

  isRecognitionSupported() {
    return typeof window !== "undefined" && Boolean(window.SpeechRecognition || window.webkitSpeechRecognition)
  }

  isSynthesisSupported() {
    return typeof window !== "undefined" && Boolean("speechSynthesis" in window)
  }

  getCapabilities() {
    const hasRec = this.isRecognitionSupported()
    const hasSynth = this.isSynthesisSupported()
    return {
      recognitionSupported: hasRec,
      synthesisSupported: hasSynth,
      supportedLanguages: ["en", "ta", "hi"],
      recommendedBrowser: "Google Chrome or Microsoft Edge",
      limitationsNote:
        "Chromium-based browsers (Chrome, Edge) provide native cloud-backed speech models for Tamil and Hindi. Firefox and Safari support is limited or requires system voice packs.",
    }
  }

  async requestMicrophonePermission() {
    if (typeof navigator === "undefined" || !navigator.mediaDevices?.getUserMedia) {
      throw new Error("Microphone API is not supported in this browser environment.")
    }
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    // Stop tracks immediately after granting permission
    stream.getTracks().forEach((track) => track.stop())
    return true
  }

  startListening({ language = "en", onInterim, onFinal, onError, onStart, onEnd }) {
    if (!this.isRecognitionSupported()) {
      onError?.(
        new Error(
          "Speech recognition is not supported in this browser. Please use Google Chrome or type your query below."
        )
      )
      return
    }

    // Stop existing instance if active
    this.abortListening()

    const SpeechRecClass = window.SpeechRecognition || window.webkitSpeechRecognition
    this.recognition = new SpeechRecClass()

    const targetLocale = BROWSER_LOCALE_MAP[language] || "en-US"
    this.recognition.lang = targetLocale
    this.recognition.continuous = false
    this.recognition.interimResults = true
    this.recognition.maxAlternatives = 1

    let finalTranscript = ""

    this.recognition.onstart = () => {
      this.isListening = true
      onStart?.()
    }

    this.recognition.onresult = (event) => {
      let interim = ""
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const item = event.results[i]
        const text = item[0]?.transcript || ""
        if (item.isFinal) {
          finalTranscript += text
        } else {
          interim += text
        }
      }
      if (interim) {
        onInterim?.(interim)
      }
      if (finalTranscript) {
        onFinal?.(finalTranscript.trim())
      }
    }

    this.recognition.onerror = (event) => {
      let friendlyMessage
      switch (event.error) {
        case "not-allowed":
        case "service-not-allowed":
          friendlyMessage =
            "Microphone permission was denied. Please allow microphone access in your browser settings to speak."
          break
        case "no-speech":
          friendlyMessage = "No speech was detected. Please tap the microphone and try speaking again."
          break
        case "audio-capture":
          friendlyMessage = "No microphone hardware was detected or it is in use by another application."
          break
        case "network":
          friendlyMessage =
            "Speech recognition network timeout. Please check your connection or use typed input."
          break
        case "language-not-supported":
          friendlyMessage = `Speech model for '${targetLocale}' is not installed in this browser. Please use typed input.`
          break
        default:
          friendlyMessage = `Recognition error: ${event.error}`
      }
      const err = new Error(friendlyMessage)
      err.code = event.error
      onError?.(err)
    }

    this.recognition.onend = () => {
      this.isListening = false
      onEnd?.(finalTranscript.trim())
      this.recognition = null
    }

    try {
      this.recognition.start()
    } catch (e) {
      onError?.(e)
    }
  }

  stopListening() {
    if (this.recognition && this.isListening) {
      try {
        this.recognition.stop()
      } catch {
        // safely ignore
      }
      this.isListening = false
    }
  }

  abortListening() {
    if (this.recognition) {
      try {
        this.recognition.abort()
      } catch {
        // safely ignore
      }
      this.recognition = null
      this.isListening = false
    }
  }

  speak(text, language = "en", { onStart, onEnd, onError } = {}) {
    if (!this.isSynthesisSupported() || !text) {
      return
    }

    this.stopSpeaking()

    const cleanText = text.replace(/[*_#`~[\]]/g, "").trim()
    if (!cleanText) return

    const utterance = new SpeechSynthesisUtterance(cleanText)
    const targetLocale = BROWSER_LOCALE_MAP[language] || "en-US"
    utterance.lang = targetLocale
    utterance.rate = 0.95
    utterance.pitch = 1.0

    // Try finding matching voice
    if (typeof window.speechSynthesis.getVoices === "function") {
      const voices = window.speechSynthesis.getVoices()
      const match = voices.find((v) => v.lang.startsWith(targetLocale) || v.lang.startsWith(language))
      if (match) {
        utterance.voice = match
      }
    }

    utterance.onstart = () => {
      this.isSpeaking = true
      onStart?.()
    }

    utterance.onend = () => {
      this.isSpeaking = false
      this.currentUtterance = null
      onEnd?.()
    }

    utterance.onerror = (e) => {
      this.isSpeaking = false
      this.currentUtterance = null
      onError?.(e)
    }

    this.currentUtterance = utterance
    window.speechSynthesis.speak(utterance)
  }

  stopSpeaking() {
    if (this.isSynthesisSupported() && window.speechSynthesis) {
      try {
        window.speechSynthesis.cancel()
      } catch {
        // safely ignore
      }
      this.isSpeaking = false
      this.currentUtterance = null
    }
  }
}

export const speechAdapter = new BrowserSpeechAdapter()
