import { useState } from "react";
import { toast } from "sonner";
import { Clock, Plus, Trash2, Repeat, Play } from "lucide-react";
import api from "../../lib/api";
import { Button } from "../ui/button";
import { Input } from "../ui/input";
import { Switch } from "../ui/switch";

const TAGE = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"];

function timerText(t, devices) {
  const wann = t.date ? `am ${t.date.split("-").reverse().join(".")}` : (t.days?.length ? t.days.map(d => TAGE[d]).join(", ") : "täglich");
  const wo = t.device_ids?.length ? devices.filter(d => t.device_ids.includes(d.id)).map(d => d.name).join(", ") || `${t.device_ids.length} Mast(en)` : "alle Masten";
  return `${wann} · ${wo}`;
}

function TimerForm({ orderPk, file, devices, defaultDevices, onDone }) {
  const [time, setTime] = useState("");
  const [modus, setModus] = useState("wochentage");
  const [days, setDays] = useState([]);
  const [date, setDate] = useState("");
  const [loop, setLoop] = useState(false);
  const [busy, setBusy] = useState(false);
  const save = async () => {
    if (!time) { toast.error("Bitte Uhrzeit wählen"); return; }
    if (modus === "datum" && !date) { toast.error("Bitte Datum wählen"); return; }
    setBusy(true);
    try {
      await api.post(`/mbox/orders/${orderPk}/audio/${file.id}/timers`, { time, days: modus === "wochentage" ? days : [], date: modus === "datum" ? date : null, loop, device_ids: defaultDevices });
      toast.success(`Timer ${time} Uhr angelegt`);
      onDone();
    } catch (e) { toast.error(e.response?.data?.detail || "Fehler"); }
    finally { setBusy(false); }
  };
  return (
    <div className="mt-2 p-3 rounded-lg border border-fuchsia-100 bg-fuchsia-50/40 space-y-3" data-testid={`timer-form-${file.id}`}>
      <div className="flex flex-wrap items-center gap-2">
        <label className="text-xs text-gray-600 flex items-center gap-1.5"><Clock className="w-3.5 h-3.5" /> Uhrzeit
          <Input type="time" value={time} onChange={e => setTime(e.target.value)} className="h-9 w-[7.5rem] bg-white" data-testid={`timer-time-${file.id}`} />
        </label>
        <div className="flex rounded-md border border-gray-200 overflow-hidden text-xs">
          <button type="button" onClick={() => setModus("wochentage")} className={`px-2.5 py-1.5 ${modus === "wochentage" ? "bg-fuchsia-600 text-white" : "bg-white text-gray-600"}`} data-testid={`timer-modus-wochentage-${file.id}`}>Wiederkehrend</button>
          <button type="button" onClick={() => setModus("datum")} className={`px-2.5 py-1.5 ${modus === "datum" ? "bg-fuchsia-600 text-white" : "bg-white text-gray-600"}`} data-testid={`timer-modus-datum-${file.id}`}>Einmalig</button>
        </div>
      </div>
      {modus === "wochentage" ? (
        <div className="flex flex-wrap items-center gap-1.5">
          {TAGE.map((t, i) => (
            <button key={t} type="button" onClick={() => setDays(d => d.includes(i) ? d.filter(x => x !== i) : [...d, i])} className={`w-9 h-8 rounded-md text-xs font-medium border ${days.includes(i) ? "bg-fuchsia-600 border-fuchsia-600 text-white" : "bg-white border-gray-200 text-gray-600"}`} data-testid={`timer-day-${i}-${file.id}`}>{t}</button>
          ))}
          <span className="text-[11px] text-gray-400 ml-1">{days.length === 0 ? "kein Tag gewählt = täglich" : ""}</span>
        </div>
      ) : (
        <Input type="date" value={date} onChange={e => setDate(e.target.value)} className="h-9 w-44 bg-white" data-testid={`timer-date-${file.id}`} />
      )}
      <div className="flex flex-wrap items-center gap-3">
        <label className="text-xs text-gray-600 flex items-center gap-2"><Switch checked={loop} onCheckedChange={setLoop} data-testid={`timer-loop-${file.id}`} /> {loop ? <><Repeat className="w-3.5 h-3.5" /> Schleife (bis Stopp)</> : <><Play className="w-3.5 h-3.5" /> einmal abspielen</>}</label>
        <span className="text-[11px] text-gray-400">Ziel: {defaultDevices.length ? `${defaultDevices.length} ausgewählte(r) Mast(en)` : "alle Masten des Auftrags"}</span>
        <div className="flex gap-2 ml-auto">
          <Button size="sm" variant="ghost" onClick={onDone} data-testid={`timer-cancel-${file.id}`}>Abbrechen</Button>
          <Button size="sm" onClick={save} disabled={busy} className="bg-fuchsia-600 hover:bg-fuchsia-700" data-testid={`timer-save-${file.id}`}><Plus className="w-4 h-4 mr-1" /> Timer anlegen</Button>
        </div>
      </div>
    </div>
  );
}

// Timer-Liste + Formular unter einer Durchsage
export function OrderAudioTimers({ orderPk, file, timers, devices, selectedDevices, onChange }) {
  const [open, setOpen] = useState(false);
  const toggle = async (t) => {
    try { await api.patch(`/mbox/orders/${orderPk}/timers/${t.id}`, { enabled: !t.enabled }); onChange(); }
    catch (e) { toast.error(e.response?.data?.detail || "Fehler"); }
  };
  const del = async (t) => {
    try { await api.delete(`/mbox/orders/${orderPk}/timers/${t.id}`); onChange(); toast.success("Timer gelöscht"); }
    catch (e) { toast.error(e.response?.data?.detail || "Fehler"); }
  };
  const testen = async (t) => {
    try { const r = await api.post(`/mbox/orders/${orderPk}/timers/${t.id}/run-now`); toast.success(`Timer-Test: „${t.file_name}“ startet in ${r.data.lead_sec} s auf ${r.data.devices} Mast(en)`); onChange(); }
    catch (e) { toast.error(e.response?.data?.detail || "Fehler"); }
  };
  return (
    <div className="mt-2" data-testid={`order-audio-timers-${file.id}`}>
      {timers.length > 0 && (
        <ul className="space-y-1">
          {timers.map(t => (
            <li key={t.id} className={`flex items-center gap-2 text-xs rounded-md px-2 py-1.5 ${t.enabled ? "bg-gray-50" : "bg-gray-50 opacity-60"}`} data-testid={`timer-row-${t.id}`}>
              <Switch checked={!!t.enabled} onCheckedChange={() => toggle(t)} className="scale-90" data-testid={`timer-toggle-${t.id}`} />
              <Clock className="w-3.5 h-3.5 text-fuchsia-600 shrink-0" />
              <span className="font-semibold text-gray-800">{t.time} Uhr</span>
              {t.loop && <Repeat className="w-3.5 h-3.5 text-gray-500" title="Schleife" />}
              <span className="text-gray-500 truncate">{timerText(t, devices)}</span>
              {t.last_result && <span className="text-gray-400 hidden sm:inline truncate" title={t.last_result}>· {t.last_result}</span>}
              <button type="button" onClick={() => testen(t)} className="ml-auto text-gray-400 hover:text-fuchsia-600 shrink-0" title="Jetzt testen" data-testid={`timer-run-${t.id}`}><Play className="w-3.5 h-3.5" /></button>
              <button type="button" onClick={() => del(t)} className="text-gray-400 hover:text-red-600 shrink-0" data-testid={`timer-delete-${t.id}`}><Trash2 className="w-3.5 h-3.5" /></button>
            </li>
          ))}
        </ul>
      )}
      {open ? (
        <TimerForm orderPk={orderPk} file={file} devices={devices} defaultDevices={selectedDevices} onDone={() => { setOpen(false); onChange(); }} />
      ) : (
        <button type="button" onClick={() => setOpen(true)} className="mt-1 text-xs text-fuchsia-700 hover:underline flex items-center gap-1" data-testid={`timer-add-${file.id}`}><Plus className="w-3.5 h-3.5" /> Timer hinzufügen</button>
      )}
    </div>
  );
}
