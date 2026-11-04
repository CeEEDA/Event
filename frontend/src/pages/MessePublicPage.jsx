import { useCallback, useEffect, useRef, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import axios from "axios";
import { toast } from "sonner";
import { Lightbulb, Volume2, Square, Radio, AlertCircle, ChevronRight, WifiOff } from "lucide-react";
import { BACKEND_URL } from "../lib/api";
import { Logo } from "../components/Logo";

const base = `${BACKEND_URL}/api/messe/public`;
const errText = (e, fb) => e.response?.data?.detail || fb;

export default function MessePublicPage() {
  const { token, deviceId } = useParams();
  const navigate = useNavigate();
  const [messe, setMesse] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    axios.get(`${base}/${token}`).then(r => setMesse(r.data)).catch(e => setError(errText(e, "Seite nicht erreichbar")));
  }, [token]);

  if (error) return <Shell><Hinweis icon={AlertCircle} titel={error} text="Bitte wenden Sie sich an das Standpersonal von Eventenergie." /></Shell>;
  if (!messe) return <Shell><p className="text-center text-sm text-gray-400 py-12">Laden …</p></Shell>;

  if (!deviceId) {
    return (
      <Shell messe={messe}>
        <h2 className="text-sm font-semibold uppercase tracking-widest text-gray-400 mb-3">Lichtmast wählen</h2>
        <div className="space-y-2" data-testid="messe-public-device-list">
          {messe.devices.map(d => (
            <button key={d.id} onClick={() => navigate(`/messe/${token}/${d.id}`)} data-testid={`messe-public-device-${d.id}`}
              className="w-full bg-white border border-gray-200 rounded-2xl px-4 py-4 flex items-center gap-3 text-left hover:border-fuchsia-400 active:scale-[0.99] transition">
              <Radio className={`w-5 h-5 ${d.pi_online ? "text-emerald-500" : "text-gray-300"}`} />
              <span className="flex-1 font-semibold text-gray-900">{d.name}</span>
              <ChevronRight className="w-5 h-5 text-gray-400" />
            </button>
          ))}
          {messe.devices.length === 0 && <p className="text-sm text-gray-400">Aktuell ist kein Lichtmast freigeschaltet.</p>}
        </div>
      </Shell>
    );
  }

  if (!messe.devices.some(d => d.id === deviceId)) {
    return <Shell messe={messe}><Hinweis icon={AlertCircle} titel="Dieser Lichtmast gehört nicht zur Messe" text="Bitte den QR-Code am Mast erneut scannen." /></Shell>;
  }

  return <Shell messe={messe}><MastSteuerung token={token} deviceId={deviceId} audio={messe.audio} mehrere={messe.devices.length > 1} /></Shell>;
}

function Shell({ messe, children }) {
  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 flex flex-col" data-testid="messe-public-page">
      <header className="px-5 pt-6 pb-4">
        <div className="bg-white rounded-2xl px-4 py-3 inline-flex"><Logo size="small" /></div>
        {messe && (
          <div className="mt-4">
            <p className="text-xs uppercase tracking-[0.2em] text-fuchsia-400 font-semibold">Messe-Demo</p>
            <h1 className="text-2xl font-bold leading-tight mt-1" data-testid="messe-public-title">{messe.name}</h1>
            {messe.location && <p className="text-sm text-gray-400">{messe.location}</p>}
            {messe.note && <p className="text-sm text-gray-300 mt-2 bg-gray-900 border border-gray-800 rounded-xl px-3 py-2" data-testid="messe-public-note">{messe.note}</p>}
          </div>
        )}
      </header>
      <main className="flex-1 bg-gray-50 text-gray-900 rounded-t-3xl px-5 pt-6 pb-10">{children}</main>
      <footer className="bg-gray-50 text-center text-[11px] text-gray-400 pb-5">Eventenergie Deutschland GmbH &amp; Co. KG · M-Box Lichtmast</footer>
    </div>
  );
}

function Hinweis({ icon: Icon, titel, text }) {
  return (
    <div className="text-center py-10" data-testid="messe-public-error">
      <Icon className="w-12 h-12 text-red-400 mx-auto mb-3" />
      <h2 className="text-lg font-semibold text-gray-900">{titel}</h2>
      <p className="text-sm text-gray-500 mt-1">{text}</p>
    </div>
  );
}

function MastSteuerung({ token, deviceId, audio, mehrere }) {
  const navigate = useNavigate();
  const [st, setSt] = useState(null);
  const [busy, setBusy] = useState(null);
  const laeuft = useRef(false);

  const refresh = useCallback(async () => {
    if (laeuft.current) return;
    laeuft.current = true;
    try {
      const r = await axios.get(`${base}/${token}/${deviceId}/status`, { timeout: 20000 });
      setSt(r.data);
    } catch (e) {
      setSt(prev => ({ ...(prev || {}), sps_ok: false, sps_fehler: errText(e, "Status nicht abrufbar") }));
    } finally {
      laeuft.current = false;
    }
  }, [token, deviceId]);

  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 3000);
    return () => clearInterval(t);
  }, [refresh]);

  const send = async (key, path, body) => {
    setBusy(key);
    try {
      const r = await axios.post(`${base}/${token}/${deviceId}/${path}`, body || {}, { timeout: 30000 });
      if (r.data?.ok === false) toast.error(r.data.fehler || "Befehl nicht ausgeführt");
      else if (r.data?.hinweis) toast.warning(r.data.hinweis);
      else toast.success("Gesendet");
      setTimeout(refresh, 500);
    } catch (e) {
      toast.error(errText(e, "Befehl fehlgeschlagen"));
    } finally {
      setBusy(null);
    }
  };

  const lampen = st?.lampen || [];
  const ausw = st?.lampen_auswahl || [];
  const spsOk = !!st?.sps_ok;

  return (
    <div className="space-y-5" data-testid="messe-public-control">
      <div className="flex items-center gap-3">
        <div className="flex-1">
          <p className="text-xs text-gray-400">Lichtmast</p>
          <h2 className="text-xl font-bold text-gray-900" data-testid="messe-public-device-name">{st?.name || "…"}</h2>
        </div>
        {mehrere && <button onClick={() => navigate(`/messe/${token}`)} className="text-xs text-fuchsia-600 underline" data-testid="messe-public-switch-device">anderer Mast</button>}
        <span className={`text-[11px] px-2 py-1 rounded-full font-medium ${spsOk ? "bg-emerald-100 text-emerald-700" : "bg-gray-200 text-gray-500"}`} data-testid="messe-public-sps-state">
          {st ? (spsOk ? "verbunden" : "Steuerung offline") : "verbinde …"}
        </span>
      </div>

      {st && !spsOk && st.sps_fehler && (
        <p className="text-xs text-amber-800 bg-amber-50 border border-amber-200 rounded-xl px-3 py-2 flex items-start gap-2" data-testid="messe-public-sps-error"><WifiOff className="w-4 h-4 shrink-0 mt-0.5" /> {st.sps_fehler}</p>
      )}

      <section className="bg-white rounded-2xl border border-gray-200 p-5 shadow-sm" data-testid="messe-public-lampen">
        <h3 className="text-xs font-bold uppercase tracking-widest text-gray-500 flex items-center gap-2 mb-4"><Lightbulb className="w-4 h-4 text-amber-500" /> Lampen</h3>
        <div className="grid grid-cols-5 gap-2 mb-4">
          {[1, 2, 3, 4, 5].map(i => {
            const an = !!lampen[i - 1];
            return (
              <button key={i} type="button" disabled={!spsOk || busy !== null} onClick={() => send(`l${i}`, "lampe", { index: i })} data-testid={`messe-lampe-${i}`}
                className={`aspect-square rounded-2xl border-2 flex flex-col items-center justify-center gap-1 font-bold text-lg transition-all active:scale-95 disabled:opacity-40 ${an ? "bg-amber-300 border-amber-500 text-gray-900 shadow-[0_0_24px_rgba(251,191,36,0.6)]" : "bg-gray-100 border-gray-200 text-gray-500"}`}>
                <Lightbulb className={`w-5 h-5 ${an ? "fill-amber-500 text-amber-700" : ""}`} />
                {i}
                {ausw[i - 1] === false && <span className="w-1.5 h-1.5 rounded-full bg-gray-400" />}
              </button>
            );
          })}
        </div>
        <div className="grid grid-cols-2 gap-2">
          <button type="button" disabled={!spsOk || busy !== null} onClick={() => send("ein", "lampe", { action: "ein" })} data-testid="messe-lampen-ein"
            className="h-12 rounded-xl bg-fuchsia-600 text-white font-semibold active:scale-[0.98] disabled:opacity-40 transition">Alle ein</button>
          <button type="button" disabled={!spsOk || busy !== null} onClick={() => send("aus", "lampe", { action: "aus" })} data-testid="messe-lampen-aus"
            className="h-12 rounded-xl bg-white border border-gray-300 text-gray-800 font-semibold active:scale-[0.98] disabled:opacity-40 transition">Alle aus</button>
        </div>
        <p className="text-xs text-gray-400 mt-3">Lampe antippen = einzeln ein/aus.</p>
      </section>

      <section className="bg-white rounded-2xl border border-gray-200 p-5 shadow-sm" data-testid="messe-public-audio">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-xs font-bold uppercase tracking-widest text-gray-500 flex items-center gap-2"><Volume2 className="w-4 h-4 text-fuchsia-500" /> Testdurchsage</h3>
          <span className={`text-[11px] px-2 py-1 rounded-full font-medium ${st?.pi_online ? "bg-emerald-100 text-emerald-700" : "bg-gray-200 text-gray-500"}`} data-testid="messe-public-pi-state">
            {st?.playing ? `spielt: ${st.playing.label || st.playing.file}` : st?.pi_online ? "bereit" : "Lautsprecher offline"}
          </span>
        </div>
        {audio.length === 0 && <p className="text-sm text-gray-400">Keine Durchsage hinterlegt.</p>}
        <div className="space-y-2">
          {audio.map(f => (
            <button key={f.id} type="button" disabled={busy !== null} onClick={() => send(f.id, "play", { fid: f.id })} data-testid={`messe-play-${f.id}`}
              className="w-full h-14 rounded-xl bg-gray-900 text-white font-semibold flex items-center gap-3 px-4 active:scale-[0.98] disabled:opacity-40 transition">
              <span className="w-9 h-9 rounded-full bg-fuchsia-600 flex items-center justify-center"><Volume2 className="w-4 h-4" /></span>
              <span className="flex-1 text-left truncate">{f.name}</span>
              {f.duration_sec && <span className="text-xs text-gray-400">{Math.round(f.duration_sec)} s</span>}
            </button>
          ))}
          {audio.length > 0 && (
            <button type="button" disabled={busy !== null} onClick={() => send("stop", "stop")} data-testid="messe-stop"
              className="w-full h-12 rounded-xl bg-white border border-gray-300 text-gray-800 font-semibold flex items-center justify-center gap-2 active:scale-[0.98] disabled:opacity-40 transition">
              <Square className="w-4 h-4" /> Stopp
            </button>
          )}
        </div>
      </section>
    </div>
  );
}
