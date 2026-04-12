type SpeechMode = "word" | "sentence";
export type TTSStatus = {
  state: "idle" | "loading" | "playing" | "fallback" | "error";
  provider: "server" | "browser";
  message: string;
};

const API_BASE =
  import.meta.env.VITE_TTS_BASE ??
  `${window.location.protocol}//${window.location.hostname}:8000`;

const TTS_PROVIDER = (import.meta.env.VITE_TTS_PROVIDER ?? "browser").toLowerCase();

let activeAudio: HTMLAudioElement | null = null;
let activeAudioUrl: string | null = null;
let activeRequestController: AbortController | null = null;
let activeRequestToken = 0;
let activeUtterance: SpeechSynthesisUtterance | null = null;
const serverAudioCache = new Map<string, Blob>();
const preloadPromises = new Map<string, Promise<void>>();
let ttsLifecycleBound = false;
let currentStatus: TTSStatus = {
  state: "idle",
  provider: TTS_PROVIDER === "server" ? "server" : "browser",
  message: TTS_PROVIDER === "server" ? "Ready for server audio." : "Ready for browser audio.",
};
const statusListeners = new Set<(status: TTSStatus) => void>();

function setTTSStatus(status: TTSStatus): void {
  currentStatus = status;
  for (const listener of statusListeners) {
    listener(status);
  }
}

export function subscribeTTSStatus(listener: (status: TTSStatus) => void): () => void {
  statusListeners.add(listener);
  listener(currentStatus);
  return () => statusListeners.delete(listener);
}

function stopBrowserSpeech(): void {
  if (window.speechSynthesis) {
    window.speechSynthesis.cancel();
  }
  activeUtterance = null;
}

function stopServerSpeech(): void {
  activeRequestController?.abort();
  activeRequestController = null;

  if (activeAudio) {
    activeAudio.pause();
    activeAudio.currentTime = 0;
  }

  if (activeAudioUrl) {
    URL.revokeObjectURL(activeAudioUrl);
    activeAudioUrl = null;
  }
}

function getServerAudioCacheKey(text: string, mode: SpeechMode): string {
  return `${mode}:${text.trim()}`;
}

function canPlayAudio(): boolean {
  if (typeof document === "undefined") {
    return true;
  }
  if (document.hidden) {
    return false;
  }
  if (typeof document.hasFocus === "function" && !document.hasFocus()) {
    return false;
  }
  return true;
}

export function stopSpeaking(): void {
  stopBrowserSpeech();
  stopServerSpeech();
  setTTSStatus({
    state: "idle",
    provider: TTS_PROVIDER === "server" ? "server" : "browser",
    message: TTS_PROVIDER === "server" ? "Ready for replay." : "Ready for browser audio.",
  });
}

function bindTTSLifecycle(): void {
  if (ttsLifecycleBound || typeof window === "undefined" || typeof document === "undefined") {
    return;
  }
  ttsLifecycleBound = true;

  const stopForBackgroundState = () => {
    if (!canPlayAudio()) {
      stopSpeaking();
    }
  };

  document.addEventListener("visibilitychange", stopForBackgroundState);
  window.addEventListener("blur", stopForBackgroundState);
  window.addEventListener("pagehide", stopForBackgroundState);
}

function speakInBrowser(text: string, rate = 0.85, message = "Playing browser audio."): Promise<void> {
  if (!window.speechSynthesis) {
    setTTSStatus({
      state: "error",
      provider: "browser",
      message: "Browser speech is unavailable.",
    });
    return Promise.reject(new Error("Browser speech is unavailable."));
  }
  if (!canPlayAudio()) {
    setTTSStatus({
      state: "idle",
      provider: "browser",
      message: "Audio paused while the app is unfocused.",
    });
    return Promise.resolve();
  }

  stopSpeaking();

  return new Promise((resolve, reject) => {
    const utterance = new SpeechSynthesisUtterance(text);
    activeUtterance = utterance;
    utterance.lang = "th-TH";
    utterance.rate = rate;

    const voices = window.speechSynthesis.getVoices();
    const thaiVoice = voices.find((voice) => voice.lang.startsWith("th"));
    if (thaiVoice) {
      utterance.voice = thaiVoice;
    }

    utterance.onstart = () =>
      setTTSStatus({
        state: "playing",
        provider: "browser",
        message,
      });
    utterance.onend = () => {
      activeUtterance = null;
      setTTSStatus({
        state: "idle",
        provider: "browser",
        message: "Browser audio finished.",
      });
      resolve();
    };
    utterance.onerror = () => {
      activeUtterance = null;
      setTTSStatus({
        state: "error",
        provider: "browser",
        message: "Browser audio failed.",
      });
      reject(new Error("Browser speech playback failed."));
    };

    setTTSStatus({
      state: "loading",
      provider: "browser",
      message: "Starting browser audio...",
    });
    window.speechSynthesis.speak(utterance);
  });
}

async function fetchServerAudio(text: string, mode: SpeechMode, signal: AbortSignal): Promise<Blob> {
  const response = await fetch(
    `${API_BASE}/tts/speak?text=${encodeURIComponent(text)}&mode=${encodeURIComponent(mode)}`,
    { signal },
  );
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.blob();
}

async function ensureServerAudioCached(text: string, mode: SpeechMode): Promise<void> {
  const trimmed = text.trim();
  if (!trimmed) return;

  const cacheKey = getServerAudioCacheKey(trimmed, mode);
  if (serverAudioCache.has(cacheKey)) {
    return;
  }
  const inFlight = preloadPromises.get(cacheKey);
  if (inFlight) {
    return inFlight;
  }

  const preloadPromise = (async () => {
    const controller = new AbortController();
    const blob = await fetchServerAudio(trimmed, mode, controller.signal);
    serverAudioCache.set(cacheKey, blob);
  })().finally(() => {
    preloadPromises.delete(cacheKey);
  });

  preloadPromises.set(cacheKey, preloadPromise);
  return preloadPromise;
}

async function speakViaServer(text: string, mode: SpeechMode): Promise<void> {
  if (!canPlayAudio()) {
    setTTSStatus({
      state: "idle",
      provider: "server",
      message: "Audio paused while the app is unfocused.",
    });
    return;
  }

  stopSpeaking();
  const trimmed = text.trim();
  const cacheKey = getServerAudioCacheKey(trimmed, mode);
  const requestToken = activeRequestToken + 1;
  activeRequestToken = requestToken;
  const controller = new AbortController();
  activeRequestController = controller;
  if (!serverAudioCache.has(cacheKey)) {
    setTTSStatus({
      state: "loading",
      provider: "server",
      message: "Fetching server audio...",
    });
  }

  let blob = serverAudioCache.get(cacheKey) ?? null;
  if (blob === null) {
    let lastError: unknown = null;
    for (let attempt = 0; attempt < 2; attempt += 1) {
      try {
        blob = await fetchServerAudio(trimmed, mode, controller.signal);
        serverAudioCache.set(cacheKey, blob);
        break;
      } catch (error) {
        lastError = error;
        if (error instanceof DOMException && error.name === "AbortError") {
          throw error;
        }
        if (attempt === 0) {
          setTTSStatus({
            state: "loading",
            provider: "server",
            message: "Retrying server audio...",
          });
        }
      }
    }

    if (blob === null) {
      throw lastError instanceof Error ? lastError : new Error("Server audio failed.");
    }
  }
  if (requestToken !== activeRequestToken) {
    return;
  }
  if (!canPlayAudio()) {
    stopSpeaking();
    return;
  }
  const objectUrl = URL.createObjectURL(blob);
  activeAudioUrl = objectUrl;

  const audio = activeAudio ?? new Audio();
  activeAudio = audio;
  audio.src = objectUrl;
  audio.onplaying = () =>
    setTTSStatus({
      state: "playing",
      provider: "server",
      message: "Playing server audio.",
    });
  audio.onended = () =>
    setTTSStatus({
      state: "idle",
      provider: "server",
      message: "Server audio finished.",
    });
  audio.onerror = () =>
    setTTSStatus({
      state: "error",
      provider: "server",
      message: "Audio playback failed.",
    });
  await audio.play();
}

export function speak(text: string, rate = 0.85, mode: SpeechMode = "sentence"): void {
  if (!text.trim()) {
    return;
  }
  bindTTSLifecycle();
  if (TTS_PROVIDER === "server") {
    void speakViaServer(text, mode).catch((error: unknown) => {
      if (error instanceof DOMException && error.name === "AbortError") {
        return;
      }
      setTTSStatus({
        state: "fallback",
        provider: "browser",
        message: "Server audio failed, using browser speech.",
      });
      void speakInBrowser(text, rate, "Playing browser fallback audio.").catch(() => {
        setTTSStatus({
          state: "error",
          provider: "browser",
          message: "Audio is unavailable right now.",
        });
      });
    });
    return;
  }

  void speakInBrowser(text, rate);
}

export function speakWord(thai: string): void {
  speak(thai, 0.8, "word");
}

export function speakSentence(thai: string): void {
  speak(thai, 0.85, "sentence");
}

export function preloadSpeech(text: string, mode: SpeechMode = "sentence"): void {
  if (TTS_PROVIDER !== "server") return;
  void ensureServerAudioCached(text, mode).catch(() => {
    // Preload is best-effort only.
  });
}
