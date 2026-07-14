# Voice Assistant — Production Architecture

A modular, provider-based voice layer that turns the AI Personal CFO into a
voice-driven financial assistant. It **reuses** the existing LLM router, copilot
memory, and RAG — the voice layer is just another interface to the same engine.

## Scope & honesty note
Implemented and tested here: multi-provider **STT** (Groq Whisper + local
Whisper) and **TTS** (gTTS + Edge TTS) with automatic failover, confidence-based
retry, `.env` configuration, structured logging, observability metrics, graceful
degradation, and a browser voice UI (VAD-style auto-stop, live transcript,
barge-in, provider/confidence/latency indicators).

Deliberately **not** implemented (would require paid keys, native binaries, or
introduce RCE risk — flagged rather than faked):
- Deepgram / AssemblyAI / Google streaming STT, ElevenLabs / Azure TTS,
  Porcupine / OpenWakeWord, Silero / RNNoise. The provider registry is designed
  so these drop in as new `STTProvider` / `TTSProvider` classes, gated by `.env`.
- Arbitrary "run terminal command / open application" function-calling — this is
  remote code execution from a web client and contradicts the security
  requirements. Financial function-calling stays scoped to the existing engine.

## Clean architecture (SOLID)
```
voice/
  config.py                 # VoiceConfig — single source of truth from .env
  service.py                # VoiceService orchestrator + observability metrics
  voice_service.py          # backward-compatible facade (unchanged public API)
  stt/
    base.py                 # STTProvider ABC + STTResult
    whisper_local.py        # offline Whisper (confidence from avg_logprob)
    groq_whisper.py         # Groq Whisper API (verbose_json → confidence+lang)
    registry.py             # priority ordering, failover, confidence retry
  tts/
    base.py                 # TTSProvider ABC + TTSResult
    gtts_tts.py             # gTTS (online)
    edge_tts_provider.py    # Edge neural TTS (optional dep)
    registry.py             # priority ordering, failover
```
- **Dependency inversion**: the service depends on `STTProvider`/`TTSProvider`
  abstractions, never on concretes.
- **Open/closed**: add a provider by writing one class and registering it — no
  changes to the service or API.
- **Single responsibility**: config, providers, registries, orchestration, and
  the API facade are all separate.

## Pipeline
```
Mic → (browser) noise suppression + echo cancel + AGC + getUserMedia
    → VAD-style amplitude + live Web-Speech interim transcript
    → POST /voice/transcribe → STT registry (Groq → local, confidence retry)
    → intent/RAG/memory via existing copilot (POST /chat)
    → LLM router (Gemini/Groq/GitHub/OpenRouter/Ollama failover)
    → answer text → POST /voice/speak → TTS registry (gTTS → Edge)
    → browser playback (autoplay-unlocked) with barge-in
```

## Failover & confidence
- STT tries providers in `STT_PROVIDER` order; on error → next provider.
- If a result's confidence `< VOICE_STT_MIN_CONFIDENCE` (default 0.75) and
  `VOICE_AUTO_RETRY=true`, the next provider is tried; the best-scoring result is
  returned flagged `low_confidence` so the UI can ask the user to repeat.
- TTS tries providers in `TTS_PROVIDER` order; first success wins.
- Offline mode (`ENABLE_OFFLINE_MODE`) restricts STT to offline providers.

## API
| Method | Path | Purpose |
|---|---|---|
| POST | `/voice/transcribe` | audio → `{text, provider, confidence, language, latency_ms, low_confidence, ...}` |
| POST | `/voice/speak` | `{text}` → audio/mpeg stream |
| GET  | `/voice/config` | providers + effective `.env` config |
| GET  | `/voice/metrics` | STT/TTS latency, fallbacks, provider usage, errors |
| GET  | `/capabilities` | now includes a `voice` block |

Backward compatibility: `/voice/transcribe` keeps its original keys
(`text/available/error/bytes`) and only **adds** fields.

## Environment variables
```
STT_PROVIDER=groq_whisper,whisper_local
TTS_PROVIDER=gtts,edge_tts
ENABLE_STREAMING=true
ENABLE_MEMORY=true
ENABLE_RAG=true
ENABLE_OFFLINE_MODE=true
VOICE_AUTO_RETRY=true
WHISPER_MODEL=small
WHISPER_LANG=en           # set to "" for auto language detection
GROQ_STT_MODEL=whisper-large-v3-turbo
VOICE_STT_MIN_CONFIDENCE=0.75
VOICE_TTS_LANG=en
EDGE_TTS_VOICE=en-US-AriaNeural
```
No API keys are hardcoded; Groq STT reuses the existing `GROQ_API_KEY`.

## Observability
Every provider logs structured lines (provider, confidence, language, latency,
error). `/voice/metrics` aggregates STT/TTS call counts, average latency,
low-confidence count, error count, and per-provider usage.

## Security checklist
- No secrets in code; all keys via `.env` (git-ignored).
- STT/TTS providers never raise — failures are structured data, no stack leaks.
- TTS input is user answer text only; no shell/eval anywhere in the voice path.
- Arbitrary command execution intentionally excluded.
- Uploaded audio is written to a temp file and deleted in a `finally` block.
- CORS unchanged; endpoints validate input via Pydantic / FastAPI.

## Installation (optional providers)
- Local Whisper (offline STT): `pip install openai-whisper` (already installed).
- Edge neural TTS: `pip install edge-tts` (optional; degrades to gTTS if absent).
- ffmpeg on PATH is required by Whisper for browser audio (already present).

## Testing report
`backend/tests/test_voice.py` (10, offline via fakes): env config parsing,
first-confident-provider selection, error failover, confidence-retry→best,
retry-disabled path, offline-only filtering, no-provider case, TTS failover,
TTS all-fail, and the backward-compatible facade shape. Full suite: 42 passing.

## Performance
- Query embedded once; providers short-circuit on first confident result.
- Whisper model warmed at startup in a background thread (no first-call stall).
- Frontend uses a 2D canvas waveform (no extra WebGL context) to avoid GPU
  context-limit crashes; audio element pre-unlocked within the user gesture.
