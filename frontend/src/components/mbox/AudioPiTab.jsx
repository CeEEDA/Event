import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { Play, Square, Volume2, Satellite, Cpu } from "lucide-react";
import api from "../../lib/api";
import { Karte, Zeile, Tab, Dot, Btn } from "./MBoxUi";

const fmtSize = (b) => (b > 1e6 ? (b / 1e6).toFixed(1) + " MB" : Math.round(b / 1e3) + " kB");
const fmtTime = (iso) => (iso ? new Date(iso).toLocaleString("de-DE") : "–");

// Reiter "Audio": Testdurchsage auf dem Pi im Lichtmast starten/stoppen (Datei liegt auf dem Pi)
export function AudioPiTab({ deviceId, darf, isAdmin, kunde }) {
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState(null);
  const [vol, setVol] = useState(null);

  const laden = useCallback(async () => {
    try {
      const r = await api.get(`/mbox/${deviceId}/audio`);
      setData(r.data);
      if (vol === null && r.data?.pi?.volume != null) setVol(r.data.pi.volume);
    } catch (e) { toast.error(e.response?.data?.detail || "Audio-Status nicht ladbar"); }
  }, [deviceId, vol]);

  useEffect(() => { laden(); const t = setInterval(laden, 3000); return () => clearInterval(t); }, [laden]);

  const cmd = async (label, fn) => {
    setBusy(label);
    try {
      const r = await fn();
      if (r.data?.hinweis) toast.warning(r.data.hinweis); else toast.success(label);
      setTimeout(laden, 1200);
    } catch (e) { toast.error(e.response?.data?.detail || "Fehler"); }
    finally { setBusy(null); }
  };

  const pi = data?.pi || {};
  const files = data?.files || [];
  const playing = pi.playing;
  const onPi = new Set(pi.files || []);

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4" data-testid="mbox-tab-audio">
      <Karte titel="Durchsagen" testId="mbox-audio-files">
        {!pi.configured && (
          <p className="text-sm text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 mb-3" data-testid="mbox-audio-not-configured">
            Der Pi dieses Masts ist noch nicht eingerichtet{isAdmin ? " – Geräteverwaltung → M-Box → „Pi-Setup generieren“." : "."}
          </p>
        )}
        {files.length === 0 && <p className="text-sm text-gray-500">Keine Audiodateien vorhanden.</p>}
        <ul className="divide-y divide-gray-100">
          {files.map(f => {
            const aktiv = playing?.file === f.name;
            return (
              <li key={f.name} className="py-2.5 flex items-center gap-3 flex-wrap" data-testid={`mbox-audio-file-${f.name}`}>
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium text-gray-900 truncate flex items-center gap-2">
                    {aktiv && <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />}
                    {f.name.replace(/\.(mp3|wav|ogg)$/i, "")}
                  </p>
                  <p className="text-[11px] text-gray-400">{fmtSize(f.size)} · {onPi.has(f.name) ? "auf dem Pi" : pi.configured ? "wird auf den Pi geladen…" : "noch nicht übertragen"}</p>
                </div>
                {aktiv ? (
                  <Btn variant="gefahr" disabled={!darf || busy} onClick={() => cmd("Durchsage gestoppt", () => api.post(`/mbox/${deviceId}/audio/stop`))} testId={`mbox-audio-stop-${f.name}`}>
                    <Square className="w-3.5 h-3.5 inline mr-1 -mt-0.5" />Stopp
                  </Btn>
                ) : (
                  <Btn variant="haupt" disabled={!darf || !!busy} onClick={() => cmd("Durchsage gestartet", () => api.post(`/mbox/${deviceId}/audio/play`, { file: f.name }))} testId={`mbox-audio-play-${f.name}`}>
                    <Play className="w-3.5 h-3.5 inline mr-1 -mt-0.5" />Abspielen
                  </Btn>
                )}
              </li>
            );
          })}
        </ul>
        {playing && (
          <div className="mt-3 flex items-center justify-between gap-2 bg-emerald-50 border border-emerald-200 rounded-lg px-3 py-2" data-testid="mbox-audio-playing">
            <span className="text-sm text-emerald-800">Läuft: <b>{playing.file}</b>{playing.loop ? " (Schleife)" : ""}</span>
            <Btn variant="gefahr" disabled={!darf || !!busy} onClick={() => cmd("Durchsage gestoppt", () => api.post(`/mbox/${deviceId}/audio/stop`))} testId="mbox-audio-stop-all">Stopp</Btn>
          </div>
        )}
        {!darf && <p className="text-xs text-gray-500 mt-3">Nur Lese-Zugriff – Abspielen ist gesperrt.</p>}
        {!kunde && darf && (
          <div className="mt-4 pt-3 border-t border-gray-100 flex items-center gap-3">
            <Volume2 className="w-4 h-4 text-gray-400" />
            <input type="range" min={0} max={100} value={vol ?? 85} onChange={e => setVol(parseInt(e.target.value))} className="flex-1 accent-fuchsia-600" data-testid="mbox-audio-volume" />
            <span className="text-xs text-gray-600 w-10 text-right">{vol ?? 85}%</span>
            <Btn disabled={!!busy} onClick={() => cmd(`Lautstärke ${vol}%`, () => api.post(`/mbox/${deviceId}/audio/volume`, { volume: vol }))} testId="mbox-audio-volume-btn">Setzen</Btn>
          </div>
        )}
      </Karte>

      <Karte titel="Pi im Lichtmast" testId="mbox-audio-pi">
        {pi.last_error && (
          <p className="text-xs text-red-700 bg-red-50 border border-red-200 rounded-lg px-3 py-2 mb-3 break-words" data-testid="mbox-audio-last-error">
            <b>Letzter Audio-Fehler auf dem Pi:</b> {pi.last_error}
          </p>
        )}
        {pi.configured && pi.version && !pi.script_current && (
          <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 mb-3" data-testid="mbox-audio-old-script">
            Pi-Skript v{pi.version} ist veraltet – bitte das Setup auf dem Pi einmal neu einspielen (danach aktualisiert sich der Pi selbst).
          </p>
        )}
        <Tab>
          <Zeile label="Verbindung"><Dot on={pi.online} farbe="gruen" />{pi.configured ? (pi.online ? "online" : "offline") : "nicht eingerichtet"}</Zeile>
          <Zeile label="Letzte Meldung">{fmtTime(pi.last_seen)}</Zeile>
          <Zeile label="Wiedergabe">{playing ? `${playing.file}${playing.device ? ` → ${playing.device}` : ""}` : "–"}</Zeile>
          <Zeile label="GPS (USB-Antenne)">
            {pi.gps?.fix ? (
              <span className="inline-flex items-center gap-1"><Satellite className="w-3.5 h-3.5 text-emerald-600" />{pi.gps.lat.toFixed(5)}, {pi.gps.lon.toFixed(5)}{pi.gps.sats != null ? ` · ${pi.gps.sats} Sat.` : ""}</span>
            ) : "kein Fix"}
          </Zeile>
          {!kunde && <Zeile label="Hostname / Version"><span className="inline-flex items-center gap-1"><Cpu className="w-3.5 h-3.5 text-gray-400" />{pi.hostname || "–"} · v{pi.version || "–"}</span></Zeile>}
          {!kunde && <Zeile label="Dateien auf dem Pi">{(pi.files || []).length}</Zeile>}
        </Tab>
        {!kunde && data?.commands?.length > 0 && (
          <div className="mt-4 pt-3 border-t border-gray-100">
            <p className="text-[11px] uppercase tracking-wide text-gray-400 mb-1.5">Letzte Befehle</p>
            <ul className="space-y-1">
              {data.commands.slice(0, 5).map(c => (
                <li key={c.id} className="text-xs text-gray-600 flex items-center gap-2">
                  <span className={`w-1.5 h-1.5 rounded-full ${c.status === "done" ? "bg-emerald-500" : c.status === "failed" ? "bg-red-500" : "bg-amber-400"}`} />
                  <span className="font-medium">{c.command}</span>{c.params?.file ? ` ${c.params.file}` : ""} · {c.user_name} · {fmtTime(c.created_at)}{c.message ? ` – ${c.message}` : ""}
                </li>
              ))}
            </ul>
          </div>
        )}
      </Karte>
    </div>
  );
}
