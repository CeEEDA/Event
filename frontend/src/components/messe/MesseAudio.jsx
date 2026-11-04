import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { Upload, Trash2, Music, Headphones, Mic, Sparkles, X, Clock } from "lucide-react";
import api, { getErrorMsg, BACKEND_URL } from "../../lib/api";
import { Button } from "../ui/button";
import { Input } from "../ui/input";
import { Karte } from "../mbox/MBoxUi";
import { AudioRecorder } from "../mbox/AudioRecorder";

const STATUS = {
  processing: ["bg-amber-100 text-amber-800", "wird verarbeitet …"],
  ready: ["bg-emerald-100 text-emerald-800", "bereit"],
  ready_unprocessed: ["bg-emerald-100 text-emerald-800", "bereit (unverändert)"],
  failed: ["bg-red-100 text-red-800", "fehlgeschlagen"],
};
const AUDIO_RE = /\.(mp3|wav|m4a|ogg|aac|flac)$/i;
const baseName = (f) => f.name.replace(/\.[^.]+$/, "");
const hhmm = (iso) => new Date(iso).toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" });

export function MesseAudio({ messeId, audio = [], onChange }) {
  const [pending, setPending] = useState([]); // [{ file, name }]
  const [busy, setBusy] = useState(false);
  const [modus, setModus] = useState("upload"); // upload | record
  const [enhance, setEnhance] = useState(false);
  const [gast, setGast] = useState(true);
  const [keep, setKeep] = useState(15);
  const [drag, setDrag] = useState(false);
  const inputRef = useRef(null);
  const token = localStorage.getItem("token");
  const processing = audio.some(f => f.status === "processing");

  useEffect(() => {
    if (!processing) return;
    const t = setInterval(onChange, 3000);
    return () => clearInterval(t);
  }, [processing, onChange]);

  const send = async (f, label, opts = {}) => {
    const fd = new FormData();
    fd.append("file", f);
    fd.append("name", label);
    fd.append("source", opts.source || "upload");
    fd.append("enhance", (opts.enhance ?? enhance) ? "1" : "");
    fd.append("temporary", opts.temporary ? "1" : "");
    fd.append("keep_minutes", String(opts.keep || 15));
    await api.post(`/messe/${messeId}/audio`, fd, { headers: { "Content-Type": "multipart/form-data" }, timeout: 120000 });
  };

  const uploadPending = async () => {
    if (pending.length === 0) return;
    setBusy(true);
    try {
      for (const p of pending) await send(p.file, p.name.trim());
      toast.success(`${pending.length} Datei(en) hochgeladen – wird verarbeitet`);
      setPending([]);
      if (inputRef.current) inputRef.current.value = "";
      onChange();
    } catch (e) {
      toast.error(getErrorMsg(e, "Upload fehlgeschlagen"));
    } finally {
      setBusy(false);
    }
  };

  const saveRecording = async (f, { name }) => {
    setBusy(true);
    try {
      await send(f, name, { source: "record", enhance: true, temporary: gast, keep });
      toast.success(gast ? `Aufnahme gespeichert – wird optimiert und nach ${keep} Min. automatisch entfernt` : "Aufnahme gespeichert – wird optimiert");
      setModus("upload");
      onChange();
    } catch (e) {
      toast.error(getErrorMsg(e, "Speichern fehlgeschlagen"));
    } finally {
      setBusy(false);
    }
  };

  const addFiles = (files) => {
    const ok = Array.from(files || []).filter(f => AUDIO_RE.test(f.name));
    if (ok.length === 0) { toast.error("Nur Audiodateien (MP3, WAV, M4A, OGG, AAC, FLAC)"); return; }
    setPending(p => [...p, ...ok.map(f => ({ file: f, name: baseName(f) }))]);
  };

  const del = async (f) => {
    try {
      await api.delete(`/messe/${messeId}/audio/${f.id}`);
      toast.success("Gelöscht");
      onChange();
    } catch (e) {
      toast.error(getErrorMsg(e));
    }
  };

  return (
    <Karte titel="Testdurchsagen" testId="messe-audio">
      <ul className="divide-y divide-gray-100 mb-3" data-testid="messe-audio-list">
        {audio.length === 0 && <li className="py-3 text-sm text-gray-400">Noch keine Testdurchsage hinterlegt.</li>}
        {audio.map(f => {
          const [cls, txt] = STATUS[f.status] || STATUS.processing;
          return (
            <li key={f.id} className="py-2.5 flex items-center gap-3" data-testid={`messe-audio-file-${f.id}`}>
              <Music className="w-4 h-4 text-fuchsia-500 shrink-0" />
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-sm font-medium text-gray-900 truncate">{f.name}</span>
                  <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${cls}`}>{txt}</span>
                  {f.source === "record" && <span className="text-[10px] px-1.5 py-0.5 rounded font-medium bg-red-100 text-red-700 inline-flex items-center gap-0.5"><Mic className="w-2.5 h-2.5" /> Aufnahme</span>}
                  {f.enhanced && <span className="text-[10px] px-1.5 py-0.5 rounded font-medium bg-fuchsia-100 text-fuchsia-700 inline-flex items-center gap-0.5" title="Nebengeräusche entfernt, 0 dB"><Sparkles className="w-2.5 h-2.5" /> optimiert</span>}
                  {f.temporary && f.expires_at && <span className="text-[10px] px-1.5 py-0.5 rounded font-medium bg-amber-100 text-amber-800 inline-flex items-center gap-0.5" title="Gast-Aufnahme – wird automatisch entfernt" data-testid={`messe-audio-temp-${f.id}`}><Clock className="w-2.5 h-2.5" /> Gast · bis {hhmm(f.expires_at)}</span>}
                </div>
                <p className="text-xs text-gray-400">{f.duration_sec ? `${Math.round(f.duration_sec)} s · ` : ""}{f.uploaded_by}{f.error ? ` · ${f.error}` : ""}{f.warning ? ` · ${f.warning}` : ""}</p>
              </div>
              {(f.status === "ready" || f.status === "ready_unprocessed") && token && (
                <audio controls preload="none" className="h-8 w-40 hidden sm:block" src={`${BACKEND_URL}/api/messe/${messeId}/audio/${f.id}/stream?token=${encodeURIComponent(token)}`} data-testid={`messe-audio-preview-${f.id}`} />
              )}
              <button type="button" onClick={() => del(f)} className="text-gray-400 hover:text-red-600" title="Löschen" data-testid={`messe-audio-delete-${f.id}`}><Trash2 className="w-4 h-4" /></button>
            </li>
          );
        })}
      </ul>

      <div className="border-t border-gray-100 pt-3 space-y-2">
        <div className="flex gap-1 bg-gray-100 rounded-lg p-1 text-sm" data-testid="messe-audio-mode">
          <button type="button" onClick={() => setModus("upload")} className={`flex-1 h-8 rounded-md font-medium flex items-center justify-center gap-1.5 transition ${modus === "upload" ? "bg-white shadow text-gray-900" : "text-gray-500"}`} data-testid="messe-audio-mode-upload"><Upload className="w-4 h-4" /> Datei</button>
          <button type="button" onClick={() => setModus("record")} className={`flex-1 h-8 rounded-md font-medium flex items-center justify-center gap-1.5 transition ${modus === "record" ? "bg-white shadow text-gray-900" : "text-gray-500"}`} data-testid="messe-audio-mode-record"><Mic className="w-4 h-4" /> Aufnehmen</button>
        </div>

        {modus === "record" && (
          <>
            <AudioRecorder busy={busy} onSave={saveRecording} />
            <label className="flex items-center gap-2 text-xs text-gray-600 cursor-pointer select-none">
              <input type="checkbox" checked={gast} onChange={e => setGast(e.target.checked)} className="accent-fuchsia-600" data-testid="messe-audio-gast" />
              <Clock className="w-3 h-3 text-amber-500" /> Gast-Aufnahme – automatisch entfernen nach
              <select value={keep} onChange={e => setKeep(Number(e.target.value))} disabled={!gast} className="border border-gray-200 rounded px-1 py-0.5 text-xs bg-white" data-testid="messe-audio-keep">
                {[5, 10, 15, 30, 60].map(m => <option key={m} value={m}>{m} Min.</option>)}
              </select>
            </label>
            <p className="text-xs text-gray-500 flex items-center gap-1"><Sparkles className="w-3 h-3 text-fuchsia-500" /> Aufnahmen werden automatisch optimiert: Nebengeräusche (z.B. Hallen-Atmo), Rauschen entfernt, Pegel auf 0 dB.</p>
          </>
        )}

        {modus === "upload" && (<>
          <div
            onDragOver={e => { e.preventDefault(); setDrag(true); }}
            onDragLeave={() => setDrag(false)}
            onDrop={e => { e.preventDefault(); setDrag(false); addFiles(e.dataTransfer.files); }}
            onClick={() => inputRef.current?.click()}
            className={`rounded-xl border-2 border-dashed px-4 py-5 text-center cursor-pointer transition-colors ${drag ? "border-fuchsia-500 bg-fuchsia-50" : "border-gray-300 hover:border-fuchsia-300 bg-gray-50"}`}
            data-testid="messe-audio-dropzone"
          >
            <input ref={inputRef} type="file" multiple accept=".mp3,.wav,.m4a,.ogg,.aac,.flac,audio/*" className="hidden"
              onChange={e => { addFiles(e.target.files); e.target.value = ""; }} data-testid="messe-audio-file-input" />
            <Upload className={`w-6 h-6 mx-auto mb-1 ${drag ? "text-fuchsia-600" : "text-gray-400"}`} />
            <p className="text-sm text-gray-700 font-medium">{drag ? "Loslassen zum Hinzufügen" : "Audiodatei hierher ziehen oder klicken"}</p>
            <p className="text-xs text-gray-400 mt-0.5">MP3, WAV, M4A, OGG, AAC, FLAC · max. 25 MB · mehrere Dateien möglich</p>
          </div>

          {pending.length > 0 && (
            <div className="space-y-2" data-testid="messe-audio-pending">
              {pending.map((p, i) => (
                <div key={i} className="flex items-center gap-2" data-testid={`messe-audio-pending-${i}`}>
                  <Music className="w-4 h-4 text-gray-400 shrink-0" />
                  <Input value={p.name} onChange={e => setPending(list => list.map((x, j) => j === i ? { ...x, name: e.target.value } : x))}
                    placeholder="Bezeichnung" className="h-9" data-testid={`messe-audio-pending-name-${i}`} />
                  <span className="text-[11px] text-gray-400 truncate max-w-[120px] hidden sm:block" title={p.file.name}>{p.file.name}</span>
                  <button type="button" onClick={() => setPending(list => list.filter((_, j) => j !== i))} className="text-gray-400 hover:text-red-600" data-testid={`messe-audio-pending-remove-${i}`}><X className="w-4 h-4" /></button>
                </div>
              ))}
              <div className="flex gap-2 justify-end">
                <Button size="sm" variant="ghost" onClick={() => setPending([])} disabled={busy} data-testid="messe-audio-clear-btn">Verwerfen</Button>
                <Button size="sm" onClick={uploadPending} disabled={busy} className="bg-fuchsia-600 hover:bg-fuchsia-700 text-white" data-testid="messe-audio-upload-btn">
                  <Upload className="w-4 h-4 mr-1" /> {busy ? "lädt …" : `${pending.length} Datei${pending.length === 1 ? "" : "en"} hochladen`}
                </Button>
              </div>
            </div>
          )}

          <label className="flex items-center gap-2 text-xs text-gray-600 cursor-pointer select-none">
            <input type="checkbox" checked={enhance} onChange={e => setEnhance(e.target.checked)} className="accent-fuchsia-600" data-testid="messe-audio-enhance" />
            <Sparkles className="w-3 h-3 text-fuchsia-500" /> Sprach-Optimierung (Nebengeräusche entfernen, 0 dB) auch für diese Datei(en)
          </label>
          <p className="text-xs text-gray-500 flex items-center gap-1"><Headphones className="w-3 h-3" /> Wird normalisiert und auf alle Messe-Geräte verteilt.</p>
        </>)}
      </div>
    </Karte>
  );
}
