import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { Upload, Play, Square, Trash2, Pencil, Check, Volume2, Loader2, AlertTriangle, Radio } from "lucide-react";
import api from "../../lib/api";
import { Button } from "../ui/button";
import { Input } from "../ui/input";

const API_BASE = process.env.REACT_APP_BACKEND_URL;

function StatusBadge({ f }) {
  const map = {
    processing: ["bg-amber-100 text-amber-700", "wird geprüft…"],
    ready: ["bg-emerald-100 text-emerald-700", f.analysis?.noise_reduction ? "bereit · Rauschen entfernt · 0 dB" : "bereit · 0 dB"],
    ready_unprocessed: ["bg-gray-100 text-gray-600", "bereit (ungeprüft)"],
    failed: ["bg-red-100 text-red-700", "Fehler"],
  };
  const [cls, txt] = map[f.status] || map.failed;
  return <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${cls}`} data-testid={`order-audio-status-${f.id}`}>{txt}</span>;
}

function FileRow({ f, orderPk, kunde, onChange, onPlay, busy }) {
  const [edit, setEdit] = useState(false);
  const [name, setName] = useState(f.name);
  const token = localStorage.getItem("token");
  const ready = f.status === "ready" || f.status === "ready_unprocessed";
  const save = async () => {
    try { await api.patch(`/mbox/orders/${orderPk}/audio/${f.id}`, { name }); setEdit(false); onChange(); toast.success("Umbenannt"); }
    catch (e) { toast.error(e.response?.data?.detail || "Fehler"); }
  };
  const del = async () => {
    if (!window.confirm(`„${f.name}“ löschen? Die Datei wird von allen Masten entfernt.`)) return;
    try { await api.delete(`/mbox/orders/${orderPk}/audio/${f.id}`); onChange(); toast.success("Gelöscht"); }
    catch (e) { toast.error(e.response?.data?.detail || "Fehler"); }
  };
  return (
    <li className="py-3 border-b border-gray-100 last:border-0" data-testid={`order-audio-file-${f.id}`}>
      <div className="flex items-center gap-2 flex-wrap">
        {edit ? (
          <>
            <Input value={name} onChange={e => setName(e.target.value)} className="h-8 max-w-xs" data-testid={`order-audio-name-input-${f.id}`} />
            <Button size="sm" variant="outline" onClick={save} data-testid={`order-audio-name-save-${f.id}`}><Check className="w-4 h-4" /></Button>
          </>
        ) : (
          <>
            <span className="text-sm font-semibold text-gray-900" data-testid={`order-audio-name-${f.id}`}>{f.name}</span>
            <button type="button" onClick={() => setEdit(true)} className="text-gray-400 hover:text-fuchsia-600" title="Umbenennen" data-testid={`order-audio-rename-${f.id}`}><Pencil className="w-3.5 h-3.5" /></button>
          </>
        )}
        <StatusBadge f={f} />
        {f.duration_sec != null && <span className="text-[11px] text-gray-400">{Math.floor(f.duration_sec / 60)}:{String(Math.round(f.duration_sec % 60)).padStart(2, "0")} min</span>}
        <span className="text-[11px] text-gray-400 ml-auto">{f.uploaded_by} · {new Date(f.uploaded_at).toLocaleString("de-DE")}</span>
      </div>
      {f.status === "failed" && <p className="text-xs text-red-600 mt-1">{f.error}</p>}
      {f.warning && <p className="text-xs text-amber-600 mt-1">{f.warning}</p>}
      {f.analysis && (
        <p className="text-[11px] text-gray-400 mt-1" data-testid={`order-audio-analysis-${f.id}`}>
          Pegel {f.analysis.before?.max_volume_db ?? "–"} dB → {f.analysis.after?.max_volume_db ?? "–"} dB
          {f.analysis.before?.noise_floor_db != null && ` · Rauschteppich ${f.analysis.before.noise_floor_db.toFixed(1)} dB${f.analysis.noise_reduction ? " → gefiltert" : " (ok)"}`}
        </p>
      )}
      {ready && (
        <div className="flex items-center gap-2 mt-2 flex-wrap">
          <audio controls preload="none" className="h-8 max-w-xs" src={`${API_BASE}/api/mbox/orders/${orderPk}/audio/${f.id}/stream?token=${token}`} data-testid={`order-audio-preview-${f.id}`} />
          <Button size="sm" onClick={() => onPlay(f)} disabled={busy} className="bg-fuchsia-600 hover:bg-fuchsia-700" data-testid={`order-audio-play-${f.id}`}>
            <Play className="w-4 h-4 mr-1" /> Auf allen Masten starten
          </Button>
          {(!kunde || true) && <Button size="sm" variant="ghost" onClick={del} className="text-gray-400 hover:text-red-600" data-testid={`order-audio-delete-${f.id}`}><Trash2 className="w-4 h-4" /></Button>}
        </div>
      )}
    </li>
  );
}

export function OrderAudioPanel({ orderPk, compact = false }) {
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState(false);
  const [uploadName, setUploadName] = useState("");
  const [uploading, setUploading] = useState(false);
  const [countdown, setCountdown] = useState(null);
  const fileRef = useRef(null);

  const load = useCallback(() => api.get(`/mbox/orders/${orderPk}/audio`).then(r => setData(r.data)).catch(() => setData(d => d || { files: [], devices: [] })), [orderPk]);
  useEffect(() => { load(); const t = setInterval(load, 5000); return () => clearInterval(t); }, [load]);

  const upload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("name", uploadName || file.name.replace(/\.[^.]+$/, ""));
      await api.post(`/mbox/orders/${orderPk}/audio`, fd, { headers: { "Content-Type": "multipart/form-data" } });
      toast.success("Hochgeladen – wird geprüft und auf 0 dB gebracht");
      setUploadName("");
      load();
    } catch (err) { toast.error(err.response?.data?.detail || "Upload fehlgeschlagen"); }
    finally { setUploading(false); if (fileRef.current) fileRef.current.value = ""; }
  };

  const play = async (f) => {
    setBusy(true);
    try {
      const r = await api.post(`/mbox/orders/${orderPk}/audio/${f.id}/play`);
      let s = r.data.lead_sec;
      setCountdown(s);
      const t = setInterval(() => { s -= 1; setCountdown(s); if (s <= 0) { clearInterval(t); setCountdown(null); } }, 1000);
      toast.success(`„${f.name}“ startet in ${r.data.lead_sec} s auf ${r.data.devices} Mast(en)`);
      if (r.data.offline?.length) toast.warning(`Offline: ${r.data.offline.join(", ")} – Befehl verfällt nach 2 min`);
    } catch (err) { toast.error(err.response?.data?.detail || "Start fehlgeschlagen"); }
    finally { setBusy(false); load(); }
  };
  const stop = async () => {
    setBusy(true);
    try { await api.post(`/mbox/orders/${orderPk}/audio/stop`); toast.success("Stopp an alle Masten gesendet"); }
    catch (err) { toast.error(err.response?.data?.detail || "Fehler"); }
    finally { setBusy(false); load(); }
  };

  const files = data?.files || [];
  const devices = data?.devices || [];
  const playing = devices.filter(d => d.pi?.playing);
  return (
    <div className="space-y-4" data-testid="order-audio-panel">
      {/* Masten-Status */}
      <div className="flex flex-wrap items-center gap-2 text-xs" data-testid="order-audio-devices">
        <Radio className="w-4 h-4 text-gray-400" />
        {devices.length === 0 && <span className="text-gray-400">Aktuell kein Mast zugewiesen.</span>}
        {devices.map(d => (
          <span key={d.id} className={`px-2 py-1 rounded-full border ${d.pi?.playing ? "bg-fuchsia-50 border-fuchsia-200 text-fuchsia-700" : d.pi?.online ? "bg-emerald-50 border-emerald-200 text-emerald-700" : "bg-gray-50 border-gray-200 text-gray-500"}`} data-testid={`order-audio-device-${d.serial_number}`}>
            {d.name} · {d.pi?.playing ? `spielt ${d.pi.playing.label || d.pi.playing.file}` : d.pi?.online ? "bereit" : "offline"}
          </span>
        ))}
        {(playing.length > 0 || countdown != null) && (
          <Button size="sm" variant="outline" onClick={stop} disabled={busy} className="ml-auto text-red-600 border-red-200 hover:bg-red-50" data-testid="order-audio-stop-all">
            <Square className="w-4 h-4 mr-1" /> {countdown != null ? `Start in ${countdown} s – abbrechen` : "Alle stoppen"}
          </Button>
        )}
      </div>

      {/* Upload */}
      <div className="flex flex-wrap items-center gap-2 bg-gray-50 border border-dashed border-gray-300 rounded-lg p-3" data-testid="order-audio-upload">
        <Volume2 className="w-4 h-4 text-gray-400" />
        <Input value={uploadName} onChange={e => setUploadName(e.target.value)} placeholder="Name der Durchsage, z.B. Evakuierung" className="h-9 max-w-xs bg-white" data-testid="order-audio-upload-name" />
        <input ref={fileRef} type="file" accept=".mp3,.wav,.m4a,.ogg,.aac,.flac,audio/*" onChange={upload} className="hidden" id={`order-audio-file-${orderPk}`} data-testid="order-audio-upload-input" />
        <Button size="sm" variant="outline" disabled={uploading} onClick={() => fileRef.current?.click()} data-testid="order-audio-upload-btn">
          {uploading ? <Loader2 className="w-4 h-4 mr-1 animate-spin" /> : <Upload className="w-4 h-4 mr-1" />} Sprachdatei hochladen
        </Button>
        <span className="text-[11px] text-gray-400">MP3/WAV bis 25 MB · wird automatisch auf Rauschen geprüft und auf 0 dB normalisiert</span>
        {data && data.ffmpeg === false && <span className="text-[11px] text-amber-600 flex items-center gap-1"><AlertTriangle className="w-3 h-3" /> ffmpeg fehlt auf dem Server – Dateien werden ungeprüft übernommen</span>}
      </div>

      {/* Dateien */}
      {files.length === 0 ? (
        <p className="text-sm text-gray-400" data-testid="order-audio-empty">Noch keine Durchsagen hochgeladen.</p>
      ) : (
        <ul data-testid="order-audio-list">
          {files.map(f => <FileRow key={f.id} f={f} orderPk={orderPk} kunde={data?.kunde} onChange={load} onPlay={play} busy={busy} />)}
        </ul>
      )}
    </div>
  );
}
