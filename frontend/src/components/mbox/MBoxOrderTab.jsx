import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { Lightbulb, MapPin, Plus, X, RotateCcw, ExternalLink, Satellite } from "lucide-react";
import api from "../../lib/api";
import { Button } from "../ui/button";
import { Input } from "../ui/input";

// Kachel im Auftrag: automatische Umkreis-Zuweisung + manuelle Korrektur
export function MBoxOrderTab({ orderPk }) {
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [expected, setExpected] = useState("");
  const [addId, setAddId] = useState("");
  const [busy, setBusy] = useState(false);

  const laden = useCallback(async () => {
    try {
      const r = await api.get(`/mbox/orders/${orderPk}`);
      setData(r.data);
      setExpected(String(r.data.expected_count || ""));
    } catch (e) { toast.error(e.response?.data?.detail || "M-Box Zuweisung nicht ladbar"); }
  }, [orderPk]);
  useEffect(() => { laden(); }, [laden]);

  const run = async (fn, msg) => {
    setBusy(true);
    try { const r = await fn(); setData(r.data); if (msg) toast.success(msg); }
    catch (e) { toast.error(e.response?.data?.detail || "Fehler"); }
    finally { setBusy(false); }
  };
  const override = (device_id, action, msg) => run(() => api.post(`/mbox/orders/${orderPk}/override`, { device_id, action }), msg);
  const saveExpected = () => run(() => api.put(`/mbox/orders/${orderPk}/config`, { expected_count: parseInt(expected) || 0 }), "Mastanzahl gespeichert");

  if (!data) return <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-5 text-sm text-gray-500">Lade M-Box Zuweisung…</div>;
  const assigned = new Set(data.devices.map(d => d.id));
  const freie = data.candidates.filter(c => !assigned.has(c.id));

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-5" data-testid="mbox-order-section">
      <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
        <h3 className="text-base font-semibold text-gray-900 flex items-center gap-2">
          <Lightbulb className="w-5 h-5 text-amber-500" />
          M-Box Lichtmasten
          <span className="text-xs font-normal text-gray-400">{data.devices.length} zugewiesen</span>
        </h3>
        <div className="text-xs text-gray-500 flex items-center gap-1 flex-wrap">
          <MapPin className="w-3.5 h-3.5" />
          {data.center ? <>Umkreis {data.radius_km} km{data.radius_used_km > data.radius_km ? <> → automatisch auf <b>{data.radius_used_km} km</b> erweitert</> : null}</> : <span className="text-amber-600">Auftrag hat noch keine Koordinaten (Adresse geocodieren)</span>}
        </div>
      </div>

      <div className="flex items-end gap-3 flex-wrap mb-4 bg-gray-50 rounded-lg border border-gray-200 p-3">
        <div>
          <label className="text-[11px] text-gray-500 block mb-1">Masten laut Auftrag</label>
          <Input type="number" min={0} value={expected} onChange={e => setExpected(e.target.value)} className="h-8 w-28 text-sm" placeholder="z.B. 4" data-testid="mbox-order-expected-input" />
        </div>
        <Button size="sm" variant="outline" onClick={saveExpected} disabled={busy} data-testid="mbox-order-expected-save">Speichern</Button>
        <p className="text-[11px] text-gray-400 flex-1 min-w-[200px]">Stehen weniger Masten im 1-km-Umkreis als hier angegeben, wächst der Umkreis in 500-m-Schritten (max. 10 km), bis die Anzahl erreicht ist. Zuweisung gilt von Lieferung bis Abholung und wird live geprüft.</p>
      </div>

      {data.devices.length === 0 ? (
        <p className="text-sm text-gray-500 mb-4" data-testid="mbox-order-empty">Aktuell steht kein Lichtmast im Umkreis der Veranstaltungsadresse.</p>
      ) : (
        <ul className="divide-y divide-gray-100 mb-4" data-testid="mbox-order-list">
          {data.devices.map(d => (
            <li key={d.id} className="py-2.5 flex items-center gap-3 flex-wrap" data-testid={`mbox-order-row-${d.serial_number}`}>
              <span className={`w-2.5 h-2.5 rounded-full shrink-0 ${d.pi?.online ? "bg-emerald-500" : "bg-gray-300"}`} title={d.pi?.online ? "Pi online" : "Pi offline"} />
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium text-gray-900 truncate">{d.name} <span className="text-gray-400 font-normal">· {d.serial_number}</span></p>
                <p className="text-[11px] text-gray-400 flex items-center gap-2">
                  {d.distance_km != null ? `${d.distance_km} km entfernt` : "keine Position"}
                  {d.pi?.gps?.fix && <Satellite className="w-3 h-3 text-emerald-600" />}
                  <span className={`px-1.5 py-0.5 rounded ${d.mode === "manuell" ? "bg-violet-100 text-violet-700" : "bg-emerald-100 text-emerald-700"}`}>{d.mode === "manuell" ? "manuell" : "automatisch"}</span>
                </p>
              </div>
              <Button size="sm" variant="ghost" onClick={() => navigate(`/mbox/${d.id}`)} title="Fernbedienung" data-testid={`mbox-order-open-${d.serial_number}`}><ExternalLink className="w-4 h-4" /></Button>
              {d.mode === "manuell" ? (
                <Button size="sm" variant="ghost" onClick={() => override(d.id, "reset", "Manuelle Zuweisung entfernt")} disabled={busy} title="Manuelle Zuweisung entfernen" data-testid={`mbox-order-reset-${d.serial_number}`}><RotateCcw className="w-4 h-4" /></Button>
              ) : (
                <Button size="sm" variant="ghost" className="text-red-600" onClick={() => override(d.id, "remove", "Mast für diesen Auftrag ausgeschlossen")} disabled={busy} title="Ausschließen" data-testid={`mbox-order-remove-${d.serial_number}`}><X className="w-4 h-4" /></Button>
              )}
            </li>
          ))}
        </ul>
      )}

      {data.blocked_ids.length > 0 && (
        <div className="mb-4 text-xs text-gray-500" data-testid="mbox-order-blocked">
          Ausgeschlossen: {data.blocked_ids.map(id => {
            const c = data.candidates.find(x => x.id === id);
            return <button key={id} type="button" onClick={() => override(id, "reset", "Ausschluss aufgehoben")} className="ml-1 underline hover:text-fuchsia-600" data-testid={`mbox-order-unblock-${id}`}>{c?.name || id} ↺</button>;
          })}
        </div>
      )}

      <div className="flex items-center gap-2 flex-wrap border-t border-gray-100 pt-3">
        <select value={addId} onChange={e => setAddId(e.target.value)} className="h-8 px-2 border border-gray-200 rounded-md text-sm bg-white min-w-[220px]" data-testid="mbox-order-add-select">
          <option value="">Mast manuell zuweisen…</option>
          {freie.map(c => <option key={c.id} value={c.id}>{c.name}{c.distance_km != null ? ` (${c.distance_km} km)` : ""}</option>)}
        </select>
        <Button size="sm" onClick={() => { if (addId) { override(addId, "add", "Mast manuell zugewiesen"); setAddId(""); } }} disabled={!addId || busy} className="bg-fuchsia-600 hover:bg-fuchsia-700" data-testid="mbox-order-add-btn"><Plus className="w-4 h-4 mr-1" />Zuweisen</Button>
      </div>
    </div>
  );
}
