import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { Upload, Play, Square, Trash2, Pencil, Check, Volume2, Loader2, AlertTriangle, Repeat, CalendarClock } from "lucide-react";
import api from "../../lib/api";
import { Button } from "../ui/button";
import { Input } from "../ui/input";
import { MastAuswahl } from "./MastAuswahl";
import { OrderAudioTimers } from "./OrderAudioTimers";

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

function FileRow({ f, orderPk, devices, selected, timers, active, onChange, onPlay, onStop, busy }) {
  const [edit, setEdit] = useState(false);
  const [name, setName] = useState(f.name);
  const token = localStorage.getItem("token");
  const ready = f.status === "ready" || f.status === "ready_unprocessed";
  const spielt = devices.filter(d => d.pi?.playing?.file === f.stored);
  const save = async () => {
    try { await api.patch(`/mbox/orders/${orderPk}/audio/${f.id}`, { name }); setEdit(false); onChange(); toast.success("Umbenannt"); }
    catch (e) { toast.error(e.response?.data?.detail || "Fehler"); }
  };
  const del = async () => {
    if (!window.confirm(`„${f.name}“ löschen? Die Datei und ihre Timer werden von allen Masten entfernt.`)) return;
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
        {spielt.length > 0 && <span className="text-[10px] px-1.5 py-0.5 rounded bg-fuchsia-100 text-fuchsia-700 font-medium animate-pulse" data-testid={`order-audio-playing-${f.id}`}>läuft auf {spielt.length} Mast(en){spielt[0].pi.playing.loop ? " · Schleife" : ""}</span>}
        <span className="text-[11px] text-gray-400 sm:ml-auto w-full sm:w-auto">{f.uploaded_by} · {new Date(f.uploaded_at).toLocaleString("de-DE")}</span>
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
        <div className="mt-2 space-y-2">
          <audio controls preload="none" className="h-9 w-full sm:max-w-md" src={`${API_BASE}/api/mbox/orders/${orderPk}/audio/${f.id}/stream?token=${token}`} data-testid={`order-audio-preview-${f.id}`} />
          <div className="grid grid-cols-2 sm:flex sm:flex-wrap items-center gap-2">
            <Button size="sm" onClick={() => onPlay(f, false)} disabled={busy || !active || devices.length === 0} className="bg-fuchsia-600 hover:bg-fuchsia-700 h-10 sm:h-9" data-testid={`order-audio-play-${f.id}`}>
              <Play className="w-4 h-4 mr-1" /> Einmal abspielen
            </Button>
            <Button size="sm" onClick={() => onPlay(f, true)} disabled={busy || !active || devices.length === 0} variant="outline" className="border-fuchsia-300 text-fuchsia-700 hover:bg-fuchsia-50 h-10 sm:h-9" data-testid={`order-audio-loop-${f.id}`}>
              <Repeat className="w-4 h-4 mr-1" /> Schleife
            </Button>
            <Button size="sm" onClick={onStop} disabled={busy || !active || devices.length === 0} variant="outline" className="text-red-600 border-red-200 hover:bg-red-50 h-10 sm:h-9" data-testid={`order-audio-stop-${f.id}`}>
              <Square className="w-4 h-4 mr-1" /> Stopp
            </Button>
            <Button size="sm" variant="ghost" onClick={del} className="text-gray-400 hover:text-red-600 h-10 sm:h-9 justify-self-end" data-testid={`order-audio-delete-${f.id}`}><Trash2 className="w-4 h-4" /><span className="sm:hidden ml-1">Löschen</span></Button>
          </div>
          <OrderAudioTimers orderPk={orderPk} file={f} timers={timers} devices={devices} selectedDevices={selected} onChange={onChange} />
        </div>
      )}
    </li>
  );
}

export function OrderAudioPanel({ orderPk }) {
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState(false);
  const [selected, setSelected] = useState([]); // [] = alle Masten
  const [uploadName, setUploadName] = useState("");
  const [uploading, setUploading] = useState(false);
  const [countdown, setCountdown] = useState(null);
  const fileRef = useRef(null);
  const countdownRef = useRef(null);

  const clearCountdown = () => { if (countdownRef.current) { clearInterval(countdownRef.current); countdownRef.current = null; } setCountdown(null); };
  useEffect(() => () => { if (countdownRef.current) clearInterval(countdownRef.current); }, []);

  const load = useCallback(() => api.get(`/mbox/orders/${orderPk}/audio`).then(r => setData(r.data)).catch(() => setData(d => d || { files: [], devices: [], timers: [] })), [orderPk]);
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

  const zielText = () => selected.length ? `${selected.length} Mast(en)` : "allen Masten";
  const play = async (f, loop) => {
    setBusy(true);
    try {
      const r = await api.post(`/mbox/orders/${orderPk}/audio/${f.id}/play`, { loop, device_ids: selected });
      clearCountdown();
      let s = r.data.lead_sec;
      setCountdown(s);
      countdownRef.current = setInterval(() => { s -= 1; setCountdown(s); if (s <= 0) clearCountdown(); }, 1000);
      toast.success(`„${f.name}“ startet in ${r.data.lead_sec} s auf ${r.data.devices} Mast(en)${loop ? " – Schleife bis Stopp" : ""}`);
      if (r.data.offline?.length) toast.warning(`Offline: ${r.data.offline.join(", ")} – Befehl verfällt nach 2 min`);
    } catch (err) { toast.error(err.response?.data?.detail || "Start fehlgeschlagen"); }
    finally { setBusy(false); load(); }
  };
  const stop = async () => {
    setBusy(true);
    try { await api.post(`/mbox/orders/${orderPk}/audio/stop`, { device_ids: selected }); clearCountdown(); toast.success(`Stopp an ${zielText()} gesendet`); }
    catch (err) { toast.error(err.response?.data?.detail || "Fehler"); }
    finally { setBusy(false); load(); }
  };

  const files = data?.files || [];
  const devices = data?.devices || [];
  const timers = data?.timers || [];
  const phase = data?.phase || "active";
  // Kunde darf nur waehrend Lieferung..Abholung bedienen; Mitarbeiter immer (z.B. Test vor Ort)
  const active = !data || !data.kunde || phase === "active";
  const banner = {
    upcoming: "Diese Veranstaltung liegt noch vor Ihnen: Durchsagen können bereits hochgeladen, benannt und vorgehört werden. Die Masten lassen sich ab Lieferung bedienen.",
    past: "Diese Veranstaltung ist beendet. Die Durchsagen bleiben zum Nachhören erhalten; Masten werden nicht mehr angesteuert.",
    unknown: "Dieser Auftrag hat keinen Dispo-Zeitraum (Lieferung/Abholung). Er gilt für Kunden erst als laufend, sobald ein Mast manuell zugewiesen oder ein Kunde freigegeben wurde.",
  }[phase];
  const playing = devices.filter(d => d.pi?.playing);
  return (
    <div className="space-y-4" data-testid="order-audio-panel">
      {banner && (
        <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-md px-3 py-2" data-testid="order-audio-inactive">{banner}</p>
      )}
      {/* Ziel-Masten */}
      <div className="flex flex-wrap items-start gap-2" data-testid="order-audio-devices">
        <div className="flex-1 min-w-0">{data ? <MastAuswahl devices={devices} selected={selected} onChange={setSelected} /> : <span className="text-xs text-gray-400">Lade Masten…</span>}</div>
        {(playing.length > 0 || countdown != null) && (
          <Button size="sm" variant="outline" onClick={stop} disabled={busy} className="text-red-600 border-red-200 hover:bg-red-50 w-full sm:w-auto" data-testid="order-audio-stop-all">
            <Square className="w-4 h-4 mr-1" /> {countdown != null ? `Start in ${countdown} s – abbrechen` : `Stopp (${zielText()})`}
          </Button>
        )}
      </div>

      {/* Upload */}
      <div className="flex flex-col sm:flex-row sm:flex-wrap sm:items-center gap-2 bg-gray-50 border border-dashed border-gray-300 rounded-lg p-3" data-testid="order-audio-upload">
        <div className="flex items-center gap-2 flex-1 min-w-0">
          <Volume2 className="w-4 h-4 text-gray-400 shrink-0" />
          <Input value={uploadName} onChange={e => setUploadName(e.target.value)} placeholder="Name der Durchsage, z.B. Evakuierung" className="h-10 sm:h-9 sm:max-w-xs bg-white" data-testid="order-audio-upload-name" />
        </div>
        <input ref={fileRef} type="file" accept=".mp3,.wav,.m4a,.ogg,.aac,.flac,audio/*" onChange={upload} className="hidden" id={`order-audio-file-${orderPk}`} data-testid="order-audio-upload-input" />
        <Button size="sm" variant="outline" disabled={uploading} onClick={() => fileRef.current?.click()} className="h-10 sm:h-9 bg-white" data-testid="order-audio-upload-btn">
          {uploading ? <Loader2 className="w-4 h-4 mr-1 animate-spin" /> : <Upload className="w-4 h-4 mr-1" />} Sprachdatei hochladen
        </Button>
        <span className="text-[11px] text-gray-400 w-full sm:w-auto">MP3/WAV bis 25 MB · wird automatisch auf Rauschen geprüft und auf 0 dB normalisiert</span>
        {data && data.ffmpeg === false && <span className="text-[11px] text-amber-600 flex items-center gap-1"><AlertTriangle className="w-3 h-3" /> ffmpeg fehlt auf dem Server – Dateien werden ungeprüft übernommen</span>}
      </div>

      {/* Dateien */}
      {files.length === 0 ? (
        <p className="text-sm text-gray-400" data-testid="order-audio-empty">Noch keine Durchsagen hochgeladen.</p>
      ) : (
        <ul data-testid="order-audio-list">
          {files.map(f => <FileRow key={f.id} f={f} orderPk={orderPk} devices={devices} selected={selected} timers={timers.filter(t => t.file_id === f.id)} active={active} onChange={load} onPlay={play} onStop={stop} busy={busy} />)}
        </ul>
      )}
      {timers.length > 0 && (
        <p className="text-[11px] text-gray-400 flex items-center gap-1" data-testid="order-audio-timers-hint"><CalendarClock className="w-3.5 h-3.5" /> {timers.filter(t => t.enabled).length} aktive(r) Timer · Uhrzeiten in deutscher Zeit, nur während Lieferung bis Abholung</p>
      )}
    </div>
  );
}
