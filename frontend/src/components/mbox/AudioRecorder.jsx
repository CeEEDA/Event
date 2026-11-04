import { useEffect, useRef, useState } from "react";
import { Mic, Square, RotateCcw, Check, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "../ui/button";
import { Input } from "../ui/input";

const pickMime = () => ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/ogg;codecs=opus"].find(m => window.MediaRecorder?.isTypeSupported?.(m)) || "";
const extFor = (mime) => mime.includes("mp4") ? "mp4" : mime.includes("ogg") ? "ogg" : "webm";
const mmss = (s) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;

// Mikrofon-Aufnahme (Notdurchsage) - wiederverwendbar fuer Messe und spaeter Auftraege.
// onSave(file, { name }) bekommt die fertige Datei; die Sprach-Optimierung passiert auf dem Server.
export function AudioRecorder({ onSave, busy, maxSec = 120, defaultName = "Notdurchsage" }) {
  const [state, setState] = useState("idle"); // idle | recording | done
  const [sec, setSec] = useState(0);
  const [level, setLevel] = useState(0);
  const [blob, setBlob] = useState(null);
  const [name, setName] = useState(defaultName);
  const rec = useRef(null);
  const chunks = useRef([]);
  const stream = useRef(null);
  const raf = useRef(null);
  const timer = useRef(null);
  const url = useRef(null);

  const cleanup = () => {
    cancelAnimationFrame(raf.current);
    clearInterval(timer.current);
    stream.current?.getTracks().forEach(t => t.stop());
    stream.current = null;
  };
  useEffect(() => () => { cleanup(); if (url.current) URL.revokeObjectURL(url.current); }, []);

  const start = async () => {
    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) { toast.error("Aufnahme wird von diesem Browser nicht unterstützt"); return; }
    try {
      stream.current = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: false, channelCount: 1 } });
    } catch {
      toast.error("Kein Mikrofon-Zugriff – bitte im Browser erlauben");
      return;
    }
    const mime = pickMime();
    const r = new MediaRecorder(stream.current, mime ? { mimeType: mime, audioBitsPerSecond: 128000 } : undefined);
    chunks.current = [];
    r.ondataavailable = e => { if (e.data.size) chunks.current.push(e.data); };
    r.onstop = () => {
      const b = new Blob(chunks.current, { type: r.mimeType || mime || "audio/webm" });
      setBlob(b);
      if (url.current) URL.revokeObjectURL(url.current);
      url.current = URL.createObjectURL(b);
      setState("done");
      cleanup();
    };
    rec.current = r;
    r.start(250);
    setSec(0); setState("recording");
    timer.current = setInterval(() => setSec(s => { if (s + 1 >= maxSec) stop(); return s + 1; }), 1000);
    // Pegelanzeige
    try {
      const ctx = new (window.AudioContext || window.webkitAudioContext)();
      const an = ctx.createAnalyser(); an.fftSize = 512;
      ctx.createMediaStreamSource(stream.current).connect(an);
      const buf = new Uint8Array(an.frequencyBinCount);
      const loop = () => { an.getByteTimeDomainData(buf); let m = 0; for (const v of buf) m = Math.max(m, Math.abs(v - 128)); setLevel(Math.min(100, Math.round(m / 1.28))); raf.current = requestAnimationFrame(loop); };
      loop();
    } catch { /* ohne Pegel weiter */ }
  };

  const stop = () => { if (rec.current && rec.current.state !== "inactive") rec.current.stop(); };
  const reset = () => { setBlob(null); setState("idle"); setSec(0); setLevel(0); };
  const save = () => {
    if (!blob) return;
    const ext = extFor(blob.type);
    onSave(new File([blob], `aufnahme_${Date.now()}.${ext}`, { type: blob.type }), { name: name.trim() || defaultName });
  };

  return (
    <div className="rounded-xl border border-gray-200 bg-gray-50 p-4 space-y-3" data-testid="audio-recorder">
      {state === "idle" && (
        <button type="button" onClick={start} className="w-full h-14 rounded-xl bg-red-600 hover:bg-red-700 text-white font-semibold flex items-center justify-center gap-2 active:scale-[0.99] transition" data-testid="recorder-start">
          <Mic className="w-5 h-5" /> Aufnahme starten
        </button>
      )}
      {state === "recording" && (
        <div className="space-y-3">
          <div className="flex items-center gap-3">
            <span className="w-3 h-3 rounded-full bg-red-600 animate-pulse" />
            <span className="font-semibold text-gray-900 tabular-nums" data-testid="recorder-time">{mmss(sec)}</span>
            <span className="text-xs text-gray-400">max. {mmss(maxSec)}</span>
            <div className="flex-1 h-2 bg-gray-200 rounded-full overflow-hidden"><div className="h-full bg-emerald-500 transition-[width] duration-75" style={{ width: `${level}%` }} /></div>
          </div>
          <button type="button" onClick={stop} className="w-full h-12 rounded-xl bg-gray-900 text-white font-semibold flex items-center justify-center gap-2" data-testid="recorder-stop">
            <Square className="w-4 h-4" /> Aufnahme beenden
          </button>
          <p className="text-xs text-gray-500">Deutlich und mit etwas Abstand zum Mikrofon sprechen. Nebengeräusche werden anschließend automatisch entfernt.</p>
        </div>
      )}
      {state === "done" && blob && (
        <div className="space-y-3">
          <audio controls src={url.current} className="w-full h-10" data-testid="recorder-preview" />
          <Input value={name} onChange={e => setName(e.target.value)} placeholder="Bezeichnung" className="h-9" data-testid="recorder-name" />
          <div className="flex flex-col-reverse sm:flex-row gap-2">
            <Button type="button" variant="outline" onClick={reset} disabled={busy} className="w-full sm:w-auto" data-testid="recorder-redo"><RotateCcw className="w-4 h-4 mr-1" /> Neu aufnehmen</Button>
            <Button type="button" onClick={save} disabled={busy} className="w-full sm:flex-1 h-11 bg-fuchsia-600 hover:bg-fuchsia-700 text-white font-semibold" data-testid="recorder-save">
              {busy ? <Loader2 className="w-4 h-4 mr-1 animate-spin" /> : <Check className="w-4 h-4 mr-1" />} {busy ? "wird verarbeitet …" : "Optimieren & speichern"}
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
