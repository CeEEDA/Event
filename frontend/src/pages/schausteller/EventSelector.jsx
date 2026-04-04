import { CalendarDays, MapPin, ArrowLeft } from "lucide-react";

export function EventSelector({ events, onSelect, onBack }) {
  return (
    <div data-testid="event-step">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-bold text-gray-900">Veranstaltung wählen</h2>
        <button onClick={onBack} className="text-sm text-fuchsia-600 hover:text-fuchsia-700 flex items-center gap-1" data-testid="back-dashboard-btn">
          <ArrowLeft className="w-4 h-4" /> Mein Bereich
        </button>
      </div>
      {events.length === 0 ? (
        <div className="bg-white border border-gray-200 rounded-xl p-8 text-center text-gray-400">Aktuell keine Veranstaltungen verfügbar</div>
      ) : (
        <div className="space-y-3">
          {events.map(event => (
            <button key={event.id} onClick={() => onSelect(event)} className="w-full bg-white border border-gray-200 rounded-xl p-4 text-left hover:border-fuchsia-400 transition-colors" data-testid={`select-event-${event.id}`}>
              <h3 className="font-semibold text-gray-900 mb-1">{event.name}</h3>
              <div className="flex flex-wrap gap-3 text-xs text-gray-500">
                {event.location && <span className="flex items-center gap-1"><MapPin className="w-3 h-3" /> {event.location}</span>}
                <span className="flex items-center gap-1"><CalendarDays className="w-3 h-3" />{new Date(event.start_date).toLocaleDateString("de-DE")} – {new Date(event.end_date).toLocaleDateString("de-DE")}</span>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
