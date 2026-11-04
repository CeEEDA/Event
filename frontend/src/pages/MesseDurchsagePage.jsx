import { useEffect, useRef, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import axios from "axios";
import { toast } from "sonner";
import { ArrowLeft, Check, Radio, Volume2, Square, Megaphone, Play } from "lucide-react";
import { Shell, Hinweis, PUBLIC_BASE as base, errText } from "../components/messe/MessePublicShell";

export default function MesseDurchsagePage() {
  const { token } = useParams();
  const navigate = useNavigate();
  const [messe, setMesse] = useState(null);
  const [error, setError] = useState(null);
  const [sel, setSel] = useState([]);
  const [fid, setFid] = useState(null);
  const [busy, setBusy] = useState(false);
  const [run, setRun] = useState(null);   // { target(ms, client clock), label, devices, offline }
  const [rest, setRest] = useState(null);
  const tick = useRef(null);

  useEffect(() => {
    axios.get(`${base}/${token}`).then(r => {
      setMesse(r.data);
      setSel(r.data.devices.map(d => d.id));
      setFid(r.data.audio[0]?.id || null);
    }).catch(e => setError(errText(e, "Seite nicht erreichbar")));
  }, [token]);

  useEffect(() => {
    if (!run) return;
    const upd = () => setRest(Math.max(0, Math.ceil((run.target - Date.now()) / 1000)));
    upd();
    tick.current = setInterval(upd, 100);
    return () => clearInterval(tick.current);
  }, [run]);

  const toggle = (id) => setSel(s => s.includes(id) ? s.filter(x => x !== id) : [...s, id]);
  const alle = messe && sel.length === messe.devices.length;

  const start = async () => {
    if (!fid) { toast.error("Bitte Durchsage wählen"); return; }
    if (sel.length === 0) { toast.error("Mindestens ein Gerät wählen"); return; }
    setBusy(true);
    try {
      const r = await axios.post(`${base}/${token}/group-play`, { fid, device_ids: sel }, { timeout: 30000 });
      const offset = Date.parse(r.data.server_time) - Date.now();   // Serveruhr -> Handyuhr
      setRun({ target: Date.parse(r.data.start_at) - offset, label: r.data.label, devices: r.data.devices, offline: r.data.offline || [] });
      if (r.data.offline?.length) toast.warning(`Offline: ${r.data.offline.join(", ")} – startet, sobald wieder erreichbar`);
    } catch (e) {
      toast.error(errText(e, "Start fehlgeschlagen"));
    } finally {
      setBusy(false);
    }
  };

  const stop = async () => {
    setBusy(true);
    try {
      await axios.post(`${base}/${token}/group-stop`, { device_ids: sel }, { timeout: 30000 });
      setRun(null);
      toast.success("Gestoppt");
    } catch (e) {
      toast.error(errText(e, "Stopp fehlgeschlagen"));
    } finally {
      setBusy(false);
    }
  };

  if (error) return <Shell><Hinweis titel={error} text="Bitte wenden Sie sich an das Standpersonal von Eventenergie." /></Shell>;
  if (!messe) return <Shell><p className="text-center text-sm text-gray-400 py-12">Laden …</p></Shell>;

  const audio = messe.audio.find(f => f.id === fid);

  return (
    <Shell messe={messe}>
      {run && <Countdown rest={rest} run={run} onStop={stop} onClose={() => setRun(null)} busy={busy} />}
      <div className="space-y-5" data-testid="messe-durchsage-page">
        <div className="flex items-center gap-3">
          <button onClick={() => navigate(`/messe/${token}`)} className="text-gray-500 flex items-center gap-1 text-sm" data-testid="messe-durchsage-back"><ArrowLeft className="w-4 h-4" /> Zurück</button>
          <h2 className="text-xl font-bold text-gray-900 flex items-center gap-2 flex-1 justify-end"><Megaphone className="w-5 h-5 text-fuchsia-600" /> Durchsage</h2>
        </div>

        <section className="bg-white rounded-2xl border border-gray-200 p-5 shadow-sm" data-testid="messe-durchsage-audio">
          <h3 className="text-xs font-bold uppercase tracking-widest text-gray-500 mb-3 flex items-center gap-2"><Volume2 className="w-4 h-4 text-fuchsia-500" /> Was abspielen?</h3>
          {messe.audio.length === 0 && <p className="text-sm text-gray-400">Keine Durchsage hinterlegt.</p>}
          <div className="space-y-2">
            {messe.audio.map(f => {
              const on = f.id === fid;
              return (
                <button key={f.id} type="button" onClick={() => setFid(f.id)} data-testid={`messe-durchsage-file-${f.id}`}
                  className={`w-full h-12 rounded-xl border-2 flex items-center gap-3 px-3 text-left transition ${on ? "border-fuchsia-500 bg-fuchsia-50" : "border-gray-200 bg-white"}`}>
                  <span className={`w-5 h-5 rounded-full border-2 flex items-center justify-center ${on ? "border-fuchsia-600 bg-fuchsia-600 text-white" : "border-gray-300"}`}>{on && <Check className="w-3 h-3" />}</span>
                  <span className="flex-1 truncate font-medium text-gray-900">{f.name}</span>
                  {f.duration_sec && <span className="text-xs text-gray-400">{Math.round(f.duration_sec)} s</span>}
                </button>
              );
            })}
          </div>
        </section>

        <section className="bg-white rounded-2xl border border-gray-200 p-5 shadow-sm" data-testid="messe-durchsage-devices">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-xs font-bold uppercase tracking-widest text-gray-500 flex items-center gap-2"><Radio className="w-4 h-4 text-emerald-500" /> Abspielgeräte</h3>
            <button type="button" onClick={() => setSel(alle ? [] : messe.devices.map(d => d.id))} className="text-xs text-fuchsia-600 underline" data-testid="messe-durchsage-select-all">{alle ? "keine" : "alle"}</button>
          </div>
          <div className="grid grid-cols-2 gap-2">
            {messe.devices.map(d => {
              const on = sel.includes(d.id);
              return (
                <button key={d.id} type="button" onClick={() => toggle(d.id)} data-testid={`messe-durchsage-device-${d.id}`}
                  className={`h-14 rounded-xl border-2 flex items-center gap-2 px-3 text-left transition ${on ? "border-fuchsia-500 bg-fuchsia-50" : "border-gray-200 bg-white"}`}>
                  <span className={`w-5 h-5 rounded-md border-2 flex items-center justify-center shrink-0 ${on ? "border-fuchsia-600 bg-fuchsia-600 text-white" : "border-gray-300"}`}>{on && <Check className="w-3 h-3" />}</span>
                  <span className="min-w-0">
                    <span className="block text-sm font-semibold text-gray-900 truncate">{d.name}</span>
                    <span className={`block text-[11px] ${d.pi_online ? "text-emerald-600" : "text-gray-400"}`}>{d.pi_online ? "bereit" : "offline"}</span>
                  </span>
                </button>
              );
            })}
          </div>
        </section>

        <button type="button" disabled={busy || !fid || sel.length === 0} onClick={start} data-testid="messe-durchsage-start"
          className="w-full h-16 rounded-2xl bg-fuchsia-600 text-white font-bold text-lg flex items-center justify-center gap-3 shadow-lg shadow-fuchsia-600/30 active:scale-[0.98] disabled:opacity-40 transition">
          <Play className="w-6 h-6 fill-white" /> Start auf {sel.length} Gerät{sel.length === 1 ? "" : "en"}
        </button>
        {audio && <p className="text-center text-xs text-gray-400">„{audio.name}“ startet nach einem 5-Sekunden-Countdown auf allen gewählten Geräten gleichzeitig.</p>}
        <button type="button" disabled={busy} onClick={stop} data-testid="messe-durchsage-stop"
          className="w-full h-12 rounded-xl bg-white border border-gray-300 text-gray-800 font-semibold flex items-center justify-center gap-2 active:scale-[0.98] disabled:opacity-40 transition">
          <Square className="w-4 h-4" /> Stopp
        </button>
      </div>
    </Shell>
  );
}

function Countdown({ rest, run, onStop, onClose, busy }) {
  const laeuft = rest === 0;
  return (
    <div className="fixed inset-0 z-50 bg-gray-950/95 text-white flex flex-col items-center justify-center px-6" data-testid="messe-countdown">
      <p className="text-xs uppercase tracking-[0.3em] text-fuchsia-400 font-semibold mb-6">{laeuft ? "Durchsage läuft" : "Start in"}</p>
      <div key={rest} className={`font-black tabular-nums leading-none ${laeuft ? "text-5xl" : "text-[9rem]"} messe-count-pop`} data-testid="messe-countdown-value">
        {laeuft ? <span className="flex items-center gap-3"><Volume2 className="w-12 h-12 text-fuchsia-400" /> {run.label}</span> : rest}
      </div>
      {!laeuft && <p className="mt-6 text-sm text-gray-400">„{run.label}“ auf {run.devices} Gerät{run.devices === 1 ? "" : "en"}</p>}
      {run.offline.length > 0 && <p className="mt-2 text-xs text-amber-300">offline: {run.offline.join(", ")}</p>}
      <div className="mt-12 flex gap-3">
        <button type="button" disabled={busy} onClick={onStop} className="h-12 px-6 rounded-xl bg-white text-gray-900 font-semibold flex items-center gap-2 disabled:opacity-40" data-testid="messe-countdown-stop"><Square className="w-4 h-4" /> Stopp</button>
        {laeuft && <button type="button" onClick={onClose} className="h-12 px-6 rounded-xl border border-gray-600 text-gray-200 font-semibold" data-testid="messe-countdown-close">Schließen</button>}
      </div>
      <style>{`@keyframes messePop{0%{transform:scale(1.35);opacity:.2}100%{transform:scale(1);opacity:1}} .messe-count-pop{animation:messePop .45s cubic-bezier(.2,.8,.2,1)}`}</style>
    </div>
  );
}
