import { useState } from "react";
import { Link } from "react-router-dom";
import { Activity, Lightbulb, Radio, ExternalLink } from "lucide-react";
import api, { getErrorMsg } from "../../lib/api";
import { Button } from "../ui/button";
import { Karte } from "../mbox/MBoxUi";

export function MesseSpsCheck({ messeId, deviceCount }) {
  const [res, setRes] = useState(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);

  const check = async () => {
    setBusy(true); setErr(null);
    try {
      const r = await api.get(`/messe/${messeId}/sps-check`);
      setRes(r.data);
    } catch (e) {
      setErr(getErrorMsg(e, "Prüfung fehlgeschlagen"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Karte titel="Verbindungscheck Lichtsteuerung" testId="messe-sps-check">
      <p className="text-xs text-gray-500 mb-3">Prüft, ob der Server die SPS (OPC-UA) jedes Messe-Masts erreicht. Nur wenn das klappt, können Besucher die Lampen schalten – der Pi (Audio) ist davon unabhängig.</p>
      <Button size="sm" variant="outline" onClick={check} disabled={busy || deviceCount === 0} data-testid="messe-sps-check-btn">
        <Activity className={`w-4 h-4 mr-1 ${busy ? "animate-pulse" : ""}`} /> {busy ? "Prüfe … (bis 15 s)" : "Jetzt prüfen"}
      </Button>
      {err && <p className="text-sm text-red-600 mt-3" data-testid="messe-sps-check-error">{err}</p>}
      {res && (
        <div className="mt-3 space-y-2" data-testid="messe-sps-check-result">
          {res.devices.map(d => (
            <div key={d.id} className={`rounded-lg border p-3 text-sm ${d.sps_ok ? "border-emerald-200 bg-emerald-50" : "border-amber-300 bg-amber-50"}`} data-testid={`messe-sps-check-${d.id}`}>
              <div className="flex items-center gap-2 flex-wrap">
                <span className="font-semibold text-gray-900">{d.name}</span>
                <span className={`inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full ${d.sps_ok ? "bg-emerald-600 text-white" : "bg-amber-600 text-white"}`}><Lightbulb className="w-3 h-3" /> Steuerung {d.sps_ok ? "erreichbar" : "nicht erreichbar"}</span>
                <span className={`inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full ${d.pi_online ? "bg-emerald-100 text-emerald-800" : "bg-gray-200 text-gray-600"}`}><Radio className="w-3 h-3" /> Pi {d.pi_online ? "online" : "offline"}</span>
                <Link to={`/mbox/${d.id}`} className="ml-auto text-xs text-fuchsia-700 underline inline-flex items-center gap-1" data-testid={`messe-sps-check-open-${d.id}`}>Fernbedienung <ExternalLink className="w-3 h-3" /></Link>
              </div>
              <p className="text-xs text-gray-500 mt-1 font-mono">{d.endpoint || "keine SPS-Adresse"}</p>
              {!d.sps_ok && <p className="text-xs text-amber-900 mt-1">Fehler: {d.sps_fehler || "keine Antwort"}</p>}
              {!d.sps_ok && /Verbinden/.test(d.sps_fehler || "") && (
                <p className="text-xs text-amber-800 mt-1">Port 4840 der SPS ist vom Server aus nicht erreichbar: VPN/Router am Mast prüfen, SPS eingeschaltet? Am Server: <code>Test-NetConnection &lt;IP&gt; -Port 4840</code>.</p>
              )}
            </div>
          ))}
        </div>
      )}
    </Karte>
  );
}
