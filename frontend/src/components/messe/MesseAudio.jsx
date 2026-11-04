import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { Upload, Trash2, Music, Headphones } from "lucide-react";
import api, { getErrorMsg, BACKEND_URL } from "../../lib/api";
import { Button } from "../ui/button";
import { Input } from "../ui/input";
import { Karte } from "../mbox/MBoxUi";

const STATUS = {
  processing: ["bg-amber-100 text-amber-800", "wird verarbeitet …"],
  ready: ["bg-emerald-100 text-emerald-800", "bereit"],
  ready_unprocessed: ["bg-emerald-100 text-emerald-800", "bereit (unverändert)"],
  failed: ["bg-red-100 text-red-800", "fehlgeschlagen"],
};

export function MesseAudio({ messeId, audio = [], onChange }) {
  const [file, setFile] = useState(null);
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const inputRef = useRef(null);
  const processing = audio.some(f => f.status === "processing");

  useEffect(() => {
    if (!processing) return;
    const t = setInterval(onChange, 3000);
    return () => clearInterval(t);
  }, [processing, onChange]);

  const upload = async (f = file, label = name) => {
    if (!f) { toast.error("Bitte Audiodatei wählen"); return; }
    setBusy(true);
    try {
      const fd = new FormData();
      fd.append("file", f);
      fd.append("name", label);
      await api.post(`/messe/${messeId}/audio`, fd, { headers: { "Content-Type": "multipart/form-data" }, timeout: 120000 });
      toast.success("Hochgeladen – wird verarbeitet");
      setFile(null); setName("");
      if (inputRef.current) inputRef.current.value = "";
      onChange();
    } catch (e) {
      toast.error(getErrorMsg(e, "Upload fehlgeschlagen"));
    } finally {
      setBusy(false);
    }
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

  const [drag, setDrag] = useState(false);
  const token = localStorage.getItem("token");

  const onDrop = (e) => {
    e.preventDefault();
    setDrag(false);
    const dropped = Array.from(e.dataTransfer.files || []).filter(f => /\.(mp3|wav|m4a|ogg|aac|flac)$/i.test(f.name));
    if (dropped.length === 0) { toast.error("Nur Audiodateien (MP3, WAV, M4A, OGG, AAC, FLAC)"); return; }
    if (dropped.length === 1) { setFile(dropped[0]); upload(dropped[0]); return; }
    setName("");
    dropped.forEach(f => upload(f, ""));
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
        <div
          onDragOver={e => { e.preventDefault(); setDrag(true); }}
          onDragLeave={() => setDrag(false)}
          onDrop={onDrop}
          onClick={() => inputRef.current?.click()}
          className={`rounded-xl border-2 border-dashed px-4 py-5 text-center cursor-pointer transition-colors ${drag ? "border-fuchsia-500 bg-fuchsia-50" : "border-gray-300 hover:border-fuchsia-300 bg-gray-50"}`}
          data-testid="messe-audio-dropzone"
        >
          <input ref={inputRef} type="file" multiple accept=".mp3,.wav,.m4a,.ogg,.aac,.flac,audio/*" className="hidden"
            onChange={e => { const fs = Array.from(e.target.files || []); if (fs.length > 1) { fs.forEach(f => upload(f, "")); e.target.value = ""; } else setFile(fs[0] || null); }}
            data-testid="messe-audio-file-input" />
          <Upload className={`w-6 h-6 mx-auto mb-1 ${drag ? "text-fuchsia-600" : "text-gray-400"}`} />
          <p className="text-sm text-gray-700 font-medium">{file ? file.name : drag ? "Loslassen zum Hochladen" : "Audiodatei hierher ziehen oder klicken"}</p>
          <p className="text-xs text-gray-400 mt-0.5">MP3, WAV, M4A, OGG, AAC, FLAC · max. 25 MB · mehrere Dateien möglich</p>
        </div>
        {file && (
          <div className="flex flex-col sm:flex-row gap-2">
            <Input value={name} onChange={e => setName(e.target.value)} placeholder="Bezeichnung (optional)" className="h-9" data-testid="messe-audio-name-input" />
            <Button size="sm" onClick={() => upload()} disabled={busy} className="bg-fuchsia-600 hover:bg-fuchsia-700 text-white" data-testid="messe-audio-upload-btn">
              <Upload className="w-4 h-4 mr-1" /> {busy ? "lädt …" : "Hochladen"}
            </Button>
            <Button size="sm" variant="ghost" onClick={() => { setFile(null); if (inputRef.current) inputRef.current.value = ""; }} data-testid="messe-audio-clear-btn">Abbrechen</Button>
          </div>
        )}
        <p className="text-xs text-gray-500 flex items-center gap-1"><Headphones className="w-3 h-3" /> Wird normalisiert und auf alle Messe-Masten verteilt.</p>
      </div>
    </Karte>
  );
}
