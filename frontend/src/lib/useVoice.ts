import { useCallback, useRef, useState } from "react";

// MediaRecorder-based mic capture with a live amplitude readout for the orb.
function pickMimeType(): string {
  const candidates = [
    "audio/webm;codecs=opus",
    "audio/webm",
    "audio/ogg;codecs=opus",
    "audio/mp4",
  ];
  for (const t of candidates) {
    if (typeof MediaRecorder !== "undefined" && MediaRecorder.isTypeSupported(t)) {
      return t;
    }
  }
  return "";
}

// Browser's built-in live speech recognition (interim results while speaking).
// Available in Chromium/Edge/Safari; gracefully skipped elsewhere.
function getSpeechRecognition(): any {
  const w = window as any;
  return w.SpeechRecognition || w.webkitSpeechRecognition || null;
}

export function useVoiceRecorder() {
  const [recording, setRecording] = useState(false);
  const [amplitude, setAmplitude] = useState(0);
  const [error, setError] = useState<string | null>(null);
  // Live text the browser hears in real time, shown during the animation.
  const [liveTranscript, setLiveTranscript] = useState("");

  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const mimeRef = useRef<string>("audio/webm");
  const streamRef = useRef<MediaStream | null>(null);
  const rafRef = useRef<number>(0);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const recognitionRef = useRef<any>(null);
  const finalizedRef = useRef<string>("");

  // Returns null on success, or an error message string on failure.
  const start = useCallback(async (): Promise<string | null> => {
    setError(null);
    const fail = (msg: string) => {
      setError(msg);
      return msg;
    };
    // getUserMedia only exists in a secure context (https:// or localhost).
    if (!navigator.mediaDevices?.getUserMedia) {
      return fail(
        window.isSecureContext === false
          ? "Microphone needs a secure page. Open the app via http://localhost:5173 (not an IP address) or use HTTPS."
          : "This browser doesn't expose microphone access (navigator.mediaDevices is unavailable)."
      );
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });
      streamRef.current = stream;
      chunksRef.current = [];

      const mimeType = pickMimeType();
      mimeRef.current = mimeType || "audio/webm";
      const rec = mimeType
        ? new MediaRecorder(stream, { mimeType })
        : new MediaRecorder(stream);
      recorderRef.current = rec;
      rec.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };
      // timeslice flushes data periodically so we never lose the tail.
      rec.start(250);

      // amplitude analyser for the orb
      const ctx = new AudioContext();
      audioCtxRef.current = ctx;
      const src = ctx.createMediaStreamSource(stream);
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 256;
      src.connect(analyser);
      analyserRef.current = analyser;
      const buf = new Uint8Array(analyser.frequencyBinCount);
      const tick = () => {
        analyser.getByteTimeDomainData(buf);
        let sum = 0;
        for (let i = 0; i < buf.length; i++) {
          const v = (buf[i] - 128) / 128;
          sum += v * v;
        }
        setAmplitude(Math.min(1, Math.sqrt(sum / buf.length) * 3));
        rafRef.current = requestAnimationFrame(tick);
      };
      tick();

      // live interim transcription (best-effort, independent of Whisper)
      setLiveTranscript("");
      finalizedRef.current = "";
      const SR = getSpeechRecognition();
      if (SR) {
        try {
          const recog = new SR();
          recog.lang = "en-US";
          recog.continuous = true;
          recog.interimResults = true;
          recog.onresult = (event: any) => {
            let interim = "";
            for (let i = event.resultIndex; i < event.results.length; i++) {
              const chunk = event.results[i][0].transcript;
              if (event.results[i].isFinal) {
                finalizedRef.current = (finalizedRef.current + " " + chunk).trim();
              } else {
                interim += chunk;
              }
            }
            setLiveTranscript((finalizedRef.current + " " + interim).trim());
          };
          recog.onerror = () => {};
          recognitionRef.current = recog;
          recog.start();
        } catch {
          recognitionRef.current = null;
        }
      }

      setRecording(true);
      return null;
    } catch (e) {
      // Map the common DOMException names to actionable messages.
      const name = e instanceof DOMException ? e.name : "";
      switch (name) {
        case "NotAllowedError":
        case "SecurityError":
          return fail(
            "Microphone permission was blocked. Click the padlock/🎤 icon in the address bar, allow the mic, then reload and try again."
          );
        case "NotFoundError":
        case "OverconstrainedError":
          return fail("No microphone was found. Plug in or enable a mic, then try again.");
        case "NotReadableError":
          return fail(
            "Your microphone is being used by another app. Close it (Zoom/Teams/etc.) and try again."
          );
        default:
          return fail(
            (e instanceof Error && e.message) ||
              "Microphone access failed. Check browser permissions."
          );
      }
    }
  }, []);

  const stop = useCallback((): Promise<Blob | null> => {
    return new Promise((resolve) => {
      const rec = recorderRef.current;
      if (!rec) {
        resolve(null);
        return;
      }
      rec.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: mimeRef.current });
        cancelAnimationFrame(rafRef.current);
        streamRef.current?.getTracks().forEach((t) => t.stop());
        audioCtxRef.current?.close().catch(() => {});
        try {
          recognitionRef.current?.stop();
        } catch {
          /* ignore */
        }
        recognitionRef.current = null;
        setAmplitude(0);
        setRecording(false);
        resolve(blob);
      };
      rec.stop();
    });
  }, []);

  return { recording, amplitude, error, start, stop, liveTranscript };
}
