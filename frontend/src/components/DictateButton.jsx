import { useEffect, useRef, useState } from "react";
import { Mic, Square } from "lucide-react";
import { toast } from "sonner";

const SR = typeof window !== "undefined" ? (window.SpeechRecognition || window.webkitSpeechRecognition) : null;

// Diktier-Knopf: haengt erkannten Text (de-DE) an den aktuellen Feldwert an. Browser-Spracherkennung (Chrome/Android, iOS Safari).
export function DictateButton({ value, onText, testId }) {
  const [on, setOn] = useState(false);
  const rec = useRef(null);
  const base = useRef("");

  useEffect(() => () => { try { rec.current?.stop(); } catch { /* noop */ } }, []);

  if (!SR) return null;

  const start = () => {
    const r = new SR();
    r.lang = "de-DE"; r.continuous = true; r.interimResults = true;
    base.current = value ? value.replace(/\s+$/, "") + " " : "";
    r.onresult = (e) => {
      let text = "";
      for (let i = 0; i < e.results.length; i++) text += e.results[i][0].transcript;
      onText(base.current + text.trim());
    };
    r.onerror = (e) => { if (e.error !== "aborted") toast.error("Spracherkennung: " + (e.error === "not-allowed" ? "Mikrofon nicht erlaubt" : e.error)); setOn(false); };
    r.onend = () => setOn(false);
    rec.current = r;
    try { r.start(); setOn(true); } catch { toast.error("Spracherkennung konnte nicht starten"); }
  };
  const stop = () => { try { rec.current?.stop(); } catch { /* noop */ } setOn(false); };

  return (
    <button type="button" onClick={on ? stop : start} title={on ? "Diktat beenden" : "Einsprechen"} data-testid={testId}
      className={`h-7 px-2 rounded-md text-xs font-medium inline-flex items-center gap-1 transition ${on ? "bg-red-600 text-white animate-pulse" : "bg-fuchsia-50 text-fuchsia-700 hover:bg-fuchsia-100"}`}>
      {on ? <Square className="w-3 h-3" /> : <Mic className="w-3 h-3" />} {on ? "Stopp" : "Einsprechen"}
    </button>
  );
}
