import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { Lightbulb, MapPin, Plus, X, RotateCcw, ExternalLink, Satellite, Users, Volume2, Search } from "lucide-react";
import api from "../../lib/api";
import { Button } from "../ui/button";
import { Input } from "../ui/input";
import { OrderAudioPanel } from "./OrderAudioPanel";

// Kunden, die diesen Auftrag (Masten + Durchsagen) sehen und bedienen duerfen
function KundenFreigabe({ orderPk }) {
  const [kunden, setKunden] = useState([]);
  const [sel, setSel] = useState([]);
  const [auto, setAuto] = useState([]);
  const [open, setOpen] = useState(false);
  const [suche, setSuche] = useState("");
  useEffect(() => {
    api.get("/mbox/customers").then(r => setKunden(r.data)).catch(() => {});
    api.get(`/mbox/orders/${orderPk}/customers`).then(r => { setSel(r.data.user_ids || []); setAuto(r.data.auto_by_customer_no || []); }).catch(() => {});
  }, [orderPk]);
  const toggle = async (id) => {
    const next = sel.includes(id) ? sel.filter(x => x !== id) : [...sel, id];
    setSel(next);
    try { await api.put(`/mbox/orders/${orderPk}/customers`, { user_ids: next }); toast.success("Kundenzugang gespeichert"); }
    catch (e) { toast.error(e.response?.data?.detail || "Fehler"); }
  };
  const namen = [...auto.map(a => a.name), ...kunden.filter(k => sel.includes(k.id) && !auto.some(a => a.id === k.id)).map(k => k.name)];
  const q = suche.trim().toLowerCase();
  const gefiltert = kunden.filter(k => !q || `${k.name} ${k.email} ${k.customer_no || ""}`.toLowerCase().includes(q));
  return (
    <div className="bg-gray-50 rounded-lg border border-gray-200 p-3 mb-4" data-testid="mbox-order-customers">
      <div className="flex items-center gap-2 flex-wrap">
        <Users className="w-4 h-4 text-gray-400" />
        <span className="text-xs font-medium text-gray-700">Kundenzugang:</span>
        <span className="text-xs text-gray-500" data-testid="mbox-order-customers-summary">{namen.length ? namen.join(", ") : "noch kein Kunde freigegeben"}</span>
        <Button size="sm" variant="outline" onClick={() => setOpen(o => !o)} className="ml-auto h-7 text-xs" data-testid="mbox-order-customers-toggle">{open ? "Schließen" : "Kunden auswählen"}</Button>
      </div>
      {open && (
        <div className="mt-3">
          <div className="relative mb-2">
            <Search className="w-4 h-4 text-gray-400 absolute left-2.5 top-1/2 -translate-y-1/2" />
            <Input value={suche} onChange={e => setSuche(e.target.value)} placeholder="Kunde suchen (Name, E-Mail, Kundennummer)…" className="h-9 pl-8 bg-white" autoFocus data-testid="mbox-order-customers-search" />
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-1 max-h-60 overflow-y-auto" data-testid="mbox-order-customers-list">
            {kunden.length === 0 && <p className="text-xs text-gray-400">Keine Kunden-Logins vorhanden (Benutzerverwaltung → Rolle Kunde).</p>}
            {kunden.length > 0 && gefiltert.length === 0 && <p className="text-xs text-gray-400" data-testid="mbox-order-customers-nohit">Kein Kunde passt zu „{suche}“.</p>}
            {gefiltert.map(k => {
              const viaNo = auto.some(a => a.id === k.id);
              return (
                <label key={k.id} className={`flex items-center gap-2 text-sm px-2 py-1.5 rounded hover:bg-white cursor-pointer ${viaNo ? "opacity-70" : ""}`}>
                  <input type="checkbox" checked={viaNo || sel.includes(k.id)} disabled={viaNo} onChange={() => toggle(k.id)} className="accent-fuchsia-600" data-testid={`mbox-order-customer-${k.id}`} />
                  <span className="flex-1 truncate">{k.name} <span className="text-gray-400 text-xs">{k.email}{k.customer_no ? ` · Kd-Nr. ${k.customer_no}` : ""}</span></span>
                  {viaNo && <span className="text-[10px] text-gray-400">automatisch (Kundennr.)</span>}
                </label>
              );
            })}
          </div>
        </div>
      )}
      <p className="text-[11px] text-gray-400 mt-2">Freigegebene Kunden sehen den Auftrag unter „Durchsagen“ (Upload + Vorhören schon vorab, Bedienen von Lieferung bis Abholung). Kunden mit passender EpiRent-Kundennummer sind automatisch dabei.</p>
    </div>
  );
}

// Kachel im Auftrag: automatische Umkreis-Zuweisung + manuelle Korrektur
export function MBoxOrderTab({ orderPk }) {
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [addId, setAddId] = useState("");
  const [busy, setBusy] = useState(false);

  const laden = useCallback(async () => {
    try {
      const r = await api.get(`/mbox/orders/${orderPk}`);
      setData(r.data);
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
          {data.center ? <>Umkreis {data.radius_km} km · Zuweisung von Lieferung bis Abholung, live geprüft</> : <span className="text-amber-600">Auftrag hat noch keine Koordinaten (Adresse geocodieren)</span>}
        </div>
      </div>

      <KundenFreigabe orderPk={orderPk} />

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

      <div className="border-t border-gray-100 mt-5 pt-4" data-testid="mbox-order-audio">
        <h4 className="text-sm font-semibold text-gray-900 flex items-center gap-2 mb-3"><Volume2 className="w-4 h-4 text-fuchsia-600" /> Durchsagen für diesen Auftrag</h4>
        <OrderAudioPanel orderPk={orderPk} />
      </div>
    </div>
  );
}
