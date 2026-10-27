import { Radio, Check } from "lucide-react";

// Auswahl der Ziel-Masten: "Alle" oder einzelne. selected = [] bedeutet alle.
export function MastAuswahl({ devices, selected, onChange, compact = false }) {
  const alle = selected.length === 0;
  const toggle = (id) => {
    if (alle) { onChange(devices.filter(d => d.id !== id).map(d => d.id)); return; }
    const next = selected.includes(id) ? selected.filter(x => x !== id) : [...selected, id];
    onChange(next.length === devices.length ? [] : next);
  };
  const chip = (on, extra = "") => `inline-flex items-center gap-1 px-2.5 py-1.5 rounded-full border text-xs font-medium transition-colors ${on ? "bg-fuchsia-600 border-fuchsia-600 text-white" : "bg-white border-gray-200 text-gray-600 hover:border-fuchsia-300"} ${extra}`;
  return (
    <div className="flex flex-wrap items-center gap-1.5" data-testid="mast-auswahl">
      <Radio className="w-4 h-4 text-gray-400 shrink-0" />
      {!compact && <span className="text-xs text-gray-500 mr-1">Ziel:</span>}
      {devices.length === 0 && <span className="text-xs text-gray-400">Aktuell kein Mast zugewiesen.</span>}
      {devices.length > 0 && (
        <button type="button" onClick={() => onChange([])} className={chip(alle)} data-testid="mast-auswahl-alle">
          {alle && <Check className="w-3 h-3" />} Alle Masten ({devices.length})
        </button>
      )}
      {devices.map(d => {
        const on = alle || selected.includes(d.id);
        const dot = d.pi?.playing ? "bg-fuchsia-300" : d.pi?.online ? "bg-emerald-400" : "bg-gray-300";
        return (
          <button key={d.id} type="button" onClick={() => toggle(d.id)} className={chip(on && !alle, alle ? "opacity-80" : "")} title={d.pi?.playing ? `spielt ${d.pi.playing.label || d.pi.playing.file}${d.pi.playing.loop ? " (Schleife)" : ""}` : d.pi?.online ? "bereit" : "offline"} data-testid={`mast-auswahl-${d.serial_number}`}>
            <span className={`w-2 h-2 rounded-full ${dot}`} />
            {d.name}
            {d.pi?.playing && <span className="opacity-80">· spielt{d.pi.playing.loop ? " ∞" : ""}</span>}
            {!d.pi?.online && <span className="opacity-70">· offline</span>}
          </button>
        );
      })}
    </div>
  );
}
