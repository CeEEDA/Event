import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { ArrowLeft, Check, Radio, Trash2, RefreshCw, Power } from "lucide-react";
import api, { getErrorMsg } from "../../lib/api";
import { Button } from "../ui/button";
import { Input } from "../ui/input";
import { Switch } from "../ui/switch";
import { Karte } from "../mbox/MBoxUi";
import { useConfirm } from "../mbox/MBoxUi";
import { MesseAudio } from "./MesseAudio";
import { MesseQr } from "./MesseQr";

export function MesseDetail({ messeId, onBack }) {
  const [m, setM] = useState(null);
  const [alleMasten, setAlleMasten] = useState([]);
  const [form, setForm] = useState(null);
  const { confirm, dialog } = useConfirm();

  const load = useCallback(async () => {
    try {
      const [r1, r2] = await Promise.all([api.get(`/messe/${messeId}`), api.get("/mbox/devices")]);
      setM(r1.data);
      setForm({ name: r1.data.name, location: r1.data.location || "", start_date: r1.data.start_date || "", end_date: r1.data.end_date || "", note: r1.data.note || "" });
      setAlleMasten(r2.data.devices || []);
    } catch (e) {
      toast.error(getErrorMsg(e, "Messe nicht ladbar"));
    }
  }, [messeId]);

  useEffect(() => { load(); }, [load]);

  const patch = async (body, okText) => {
    try {
      const r = await api.patch(`/messe/${messeId}`, body);
      setM(r.data);
      if (okText) toast.success(okText);
    } catch (e) {
      toast.error(getErrorMsg(e, "Speichern fehlgeschlagen"));
    }
  };

  const toggleMast = (id) => {
    const ids = m.device_ids.includes(id) ? m.device_ids.filter(x => x !== id) : [...m.device_ids, id];
    patch({ device_ids: ids });
  };

  const neuerLink = async () => {
    if (!(await confirm("Neuen Link erzeugen? Alle bisher gedruckten QR-Codes dieser Messe werden ungültig."))) return;
    try {
      const r = await api.post(`/messe/${messeId}/new-link`);
      setM(r.data);
      toast.success("Neuer Link erzeugt – QR-Codes neu drucken");
    } catch (e) {
      toast.error(getErrorMsg(e));
    }
  };

  const loeschen = async () => {
    if (!(await confirm(`Messe „${m.name}“ archivieren? Die QR-Codes funktionieren danach nicht mehr.`))) return;
    try {
      await api.delete(`/messe/${messeId}`);
      toast.success("Messe archiviert");
      onBack();
    } catch (e) {
      toast.error(getErrorMsg(e));
    }
  };

  if (!m || !form) return <div className="min-h-screen bg-gray-50 flex items-center justify-center text-sm text-gray-400">Laden …</div>;

  return (
    <div className="min-h-screen bg-gray-50" data-testid="messe-detail">
      {dialog}
      <header className="sticky top-0 z-10 bg-white border-b border-gray-200">
        <div className="max-w-5xl mx-auto px-4 py-3 flex items-center gap-3">
          <Button variant="ghost" size="sm" onClick={onBack} className="text-gray-600 hover:text-fuchsia-600" data-testid="messe-detail-back">
            <ArrowLeft className="w-4 h-4 mr-1" /> Messen
          </Button>
          <div className="h-5 w-px bg-gray-200" />
          <h1 className="text-base font-semibold text-gray-900 truncate flex-1">{m.name}</h1>
          <label className="flex items-center gap-2 text-xs text-gray-600" title="Deaktiviert = QR-Codes zeigen 'nicht freigeschaltet'">
            <Power className={`w-4 h-4 ${m.active ? "text-emerald-500" : "text-gray-400"}`} />
            <span className="hidden sm:inline">{m.active ? "freigeschaltet" : "gesperrt"}</span>
            <Switch checked={!!m.active} onCheckedChange={v => patch({ active: v }, v ? "Messe freigeschaltet" : "Messe gesperrt – QR-Codes zeigen Hinweis")} data-testid="messe-active-switch" />
          </label>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-4 py-6 grid gap-4 lg:grid-cols-2">
        <Karte titel="Messe" testId="messe-stammdaten">
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="sm:col-span-2">
              <label className="text-xs text-gray-500">Name</label>
              <Input value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} onBlur={() => form.name.trim() && form.name !== m.name && patch({ name: form.name }, "Gespeichert")} data-testid="messe-detail-name" />
            </div>
            <div className="sm:col-span-2">
              <label className="text-xs text-gray-500">Ort / Halle / Stand</label>
              <Input value={form.location} onChange={e => setForm({ ...form, location: e.target.value })} onBlur={() => form.location !== (m.location || "") && patch({ location: form.location }, "Gespeichert")} data-testid="messe-detail-location" />
            </div>
            <div>
              <label className="text-xs text-gray-500">Von</label>
              <Input type="date" value={form.start_date} onChange={e => { setForm({ ...form, start_date: e.target.value }); patch({ start_date: e.target.value }); }} data-testid="messe-detail-start" />
            </div>
            <div>
              <label className="text-xs text-gray-500">Bis</label>
              <Input type="date" value={form.end_date} onChange={e => { setForm({ ...form, end_date: e.target.value }); patch({ end_date: e.target.value }); }} data-testid="messe-detail-end" />
            </div>
          </div>
          <div className="flex flex-wrap gap-2 mt-4 pt-3 border-t border-gray-100">
            <Button variant="outline" size="sm" onClick={neuerLink} data-testid="messe-new-link-btn"><RefreshCw className="w-4 h-4 mr-1" /> Neuen Link erzeugen</Button>
            <Button variant="outline" size="sm" onClick={loeschen} className="text-red-700 border-red-200 hover:bg-red-50" data-testid="messe-delete-btn"><Trash2 className="w-4 h-4 mr-1" /> Messe archivieren</Button>
          </div>
        </Karte>

        <Karte titel={`M-Boxen aus dem Gerätestamm (${m.device_ids.length} ausgewählt)`} testId="messe-masten">
          {alleMasten.length === 0 && <p className="text-sm text-gray-400">Keine M-Box im Gerätestamm angelegt.</p>}
          <div className="space-y-1.5 max-h-80 overflow-y-auto pr-1">
            {alleMasten.map(d => {
              const on = m.device_ids.includes(d.id);
              const name = d.user_field || d.serial_number;
              return (
                <button key={d.id} type="button" onClick={() => toggleMast(d.id)} data-testid={`messe-mast-${d.serial_number}`}
                  className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg border text-left transition-colors ${on ? "bg-fuchsia-50 border-fuchsia-300" : "bg-white border-gray-200 hover:border-fuchsia-200"}`}>
                  <span className={`w-5 h-5 rounded-md border flex items-center justify-center ${on ? "bg-fuchsia-600 border-fuchsia-600 text-white" : "border-gray-300"}`}>{on && <Check className="w-3.5 h-3.5" />}</span>
                  <Radio className={`w-4 h-4 ${d.pi?.online ? "text-emerald-500" : "text-gray-300"}`} />
                  <span className="flex-1 min-w-0">
                    <span className="block text-sm font-medium text-gray-900 truncate">{name}</span>
                    <span className="block text-xs text-gray-400 truncate">{d.serial_number !== name ? `${d.serial_number} · ` : ""}{d.pi?.online ? "Pi online" : d.pi?.configured ? "Pi offline" : "Pi nicht eingerichtet"}</span>
                  </span>
                </button>
              );
            })}
          </div>
          <p className="text-xs text-gray-500 mt-3">Nur ausgewählte Masten sind über die QR-Codes bedienbar. Die Testdurchsagen werden automatisch auf die Pis dieser Masten verteilt.</p>
        </Karte>

        <MesseAudio messeId={messeId} audio={m.audio} onChange={load} />
        <MesseQr messe={m} />
      </main>
    </div>
  );
}
