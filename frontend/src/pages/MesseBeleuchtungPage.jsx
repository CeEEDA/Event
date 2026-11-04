import { useCallback, useEffect, useRef, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import axios from "axios";
import { toast } from "sonner";
import { ArrowLeft, Check, Radio, Lightbulb } from "lucide-react";
import { Shell, Hinweis, PUBLIC_BASE as base, errText, useMesseSession, withSession } from "../components/messe/MessePublicShell";

export default function MesseBeleuchtungPage() {
  const { token } = useParams();
  const navigate = useNavigate();
  const [messe, setMesse] = useState(null);
  const [error, setError] = useState(null);
  const session = useMesseSession(token);
  const [sel, setSel] = useState([]);
  const [status, setStatus] = useState({});
  const [busy, setBusy] = useState(null);
  const laeuft = useRef(false);

  useEffect(() => {
    axios.get(`${base}/${token}`).then(r => { setMesse(r.data); setSel(r.data.devices.map(d => d.id)); })
      .catch(e => setError(errText(e, "Seite nicht erreichbar")));
  }, [token]);

  const refresh = useCallback(async () => {
    if (laeuft.current) return;
    laeuft.current = true;
    try {
      const r = await axios.get(`${base}/${token}/group-status`, { timeout: 25000 });
      setStatus(Object.fromEntries(r.data.devices.map(d => [d.id, d])));
    } catch { /* naechster Versuch */ } finally { laeuft.current = false; }
  }, [token]);

  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 4000);
    return () => clearInterval(t);
  }, [refresh]);

  const toggle = (id) => setSel(s => s.includes(id) ? s.filter(x => x !== id) : [...s, id]);
  const alle = messe && sel.length === messe.devices.length;
  const online = sel.some(id => status[id]?.sps_ok);

  const send = async (key, body) => {
    if (sel.length === 0) { toast.error("Mindestens ein Gerät wählen"); return; }
    setBusy(key);
    try {
      const r = await axios.post(`${base}/${token}/group-lampe`, { ...body, device_ids: sel }, withSession(token, { timeout: 30000 }));
      const bad = (r.data.results || []).filter(x => !x.ok);
      if (bad.length === 0) toast.success("Gesendet");
      else toast.error(`Nicht erreicht: ${bad.map(x => x.name).join(", ")}`);
      setTimeout(refresh, 500);
    } catch (e) {
      toast.error(errText(e, "Befehl fehlgeschlagen"));
    } finally {
      setBusy(null);
    }
  };

  if (error) return <Shell><Hinweis titel={error} text="Bitte wenden Sie sich an das Standpersonal von Eventenergie." /></Shell>;
  if (!messe) return <Shell><p className="text-center text-sm text-gray-400 py-12">Laden …</p></Shell>;

  // Lampe gilt als "an", wenn sie auf allen gewaehlten (erreichbaren) Geraeten an ist
  const lampeAn = (i) => { const ds = sel.map(id => status[id]).filter(d => d?.sps_ok); return ds.length > 0 && ds.every(d => d.lampen?.[i - 1]); };
  const gesperrt = session.locked || busy !== null || !online;

  return (
    <Shell messe={messe} session={session}>
      <div className="space-y-5" data-testid="messe-beleuchtung-page">
        <div className="flex items-center gap-3">
          <button onClick={() => navigate(`/messe/${token}`)} className="text-gray-500 flex items-center gap-1 text-sm" data-testid="messe-beleuchtung-back"><ArrowLeft className="w-4 h-4" /> Zurück</button>
          <h2 className="text-xl font-bold text-gray-900 flex items-center gap-2 flex-1 justify-end"><Lightbulb className="w-5 h-5 text-amber-500" /> Beleuchtung</h2>
        </div>

        <section className="bg-white rounded-2xl border border-gray-200 p-5 shadow-sm" data-testid="messe-beleuchtung-devices">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-xs font-bold uppercase tracking-widest text-gray-500 flex items-center gap-2"><Radio className="w-4 h-4 text-emerald-500" /> Geräte</h3>
            <button type="button" onClick={() => setSel(alle ? [] : messe.devices.map(d => d.id))} className="text-xs text-fuchsia-600 underline" data-testid="messe-beleuchtung-select-all">{alle ? "keine" : "alle"}</button>
          </div>
          <div className="grid grid-cols-2 gap-2">
            {messe.devices.map(d => {
              const on = sel.includes(d.id);
              const st = status[d.id];
              const anzahl = (st?.lampen || []).filter(Boolean).length;
              return (
                <button key={d.id} type="button" onClick={() => toggle(d.id)} data-testid={`messe-beleuchtung-device-${d.id}`}
                  className={`h-14 rounded-xl border-2 flex items-center gap-2 px-3 text-left transition ${on ? "border-fuchsia-500 bg-fuchsia-50" : "border-gray-200 bg-white"}`}>
                  <span className={`w-5 h-5 rounded-md border-2 flex items-center justify-center shrink-0 ${on ? "border-fuchsia-600 bg-fuchsia-600 text-white" : "border-gray-300"}`}>{on && <Check className="w-3 h-3" />}</span>
                  <span className="min-w-0">
                    <span className="block text-sm font-semibold text-gray-900 truncate">{d.name}</span>
                    <span className={`block text-[11px] ${st?.sps_ok ? "text-emerald-600" : "text-gray-400"}`}>{st ? (st.sps_ok ? `${anzahl} von 5 an` : "Steuerung offline") : "…"}</span>
                  </span>
                </button>
              );
            })}
          </div>
        </section>

        <section className="bg-white rounded-2xl border border-gray-200 p-5 shadow-sm" data-testid="messe-beleuchtung-lampen">
          <h3 className="text-xs font-bold uppercase tracking-widest text-gray-500 flex items-center gap-2 mb-4"><Lightbulb className="w-4 h-4 text-amber-500" /> Lampen auf {sel.length} Gerät{sel.length === 1 ? "" : "en"}</h3>
          <div className="grid grid-cols-5 gap-2 mb-4">
            {[1, 2, 3, 4, 5].map(i => {
              const an = lampeAn(i);
              return (
                <button key={i} type="button" disabled={gesperrt} onClick={() => send(`l${i}`, { index: i })} data-testid={`messe-beleuchtung-lampe-${i}`}
                  className={`aspect-square rounded-2xl border-2 flex flex-col items-center justify-center gap-1 font-bold text-lg transition-all active:scale-95 disabled:opacity-40 ${an ? "bg-amber-300 border-amber-500 text-gray-900 shadow-[0_0_24px_rgba(251,191,36,0.6)]" : "bg-gray-100 border-gray-200 text-gray-500"}`}>
                  <Lightbulb className={`w-5 h-5 ${an ? "fill-amber-500 text-amber-700" : ""}`} />{i}
                </button>
              );
            })}
          </div>
          <div className="grid grid-cols-2 gap-2">
            <button type="button" disabled={gesperrt} onClick={() => send("ein", { action: "ein" })} data-testid="messe-beleuchtung-ein"
              className="h-14 rounded-xl bg-fuchsia-600 text-white font-semibold text-base active:scale-[0.98] disabled:opacity-40 transition">Alle ein</button>
            <button type="button" disabled={gesperrt} onClick={() => send("aus", { action: "aus" })} data-testid="messe-beleuchtung-aus"
              className="h-14 rounded-xl bg-white border border-gray-300 text-gray-800 font-semibold text-base active:scale-[0.98] disabled:opacity-40 transition">Alle aus</button>
          </div>
          {!online && Object.keys(status).length > 0 && <p className="text-xs text-amber-700 mt-3" data-testid="messe-beleuchtung-offline">Kein gewähltes Gerät ist aktuell erreichbar.</p>}
        </section>
      </div>
    </Shell>
  );
}
