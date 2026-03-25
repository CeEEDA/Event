import { useState, useEffect } from "react";
import api from "../lib/api";
import { FileText, MapPin, AlertTriangle, Play, Square, Zap, ZapOff, RotateCcw, ChevronDown } from "lucide-react";

const EVENT_ICONS = {
  engine_start: { Icon: Play, color: "text-emerald-500", bg: "bg-emerald-50" },
  engine_stop: { Icon: Square, color: "text-red-500", bg: "bg-red-50" },
  overtemp: { Icon: AlertTriangle, color: "text-orange-500", bg: "bg-orange-50" },
  low_oil_pressure: { Icon: AlertTriangle, color: "text-amber-500", bg: "bg-amber-50" },
  low_battery: { Icon: AlertTriangle, color: "text-yellow-600", bg: "bg-yellow-50" },
  under_frequency: { Icon: AlertTriangle, color: "text-purple-500", bg: "bg-purple-50" },
  over_frequency: { Icon: AlertTriangle, color: "text-purple-500", bg: "bg-purple-50" },
  emergency_stop: { Icon: AlertTriangle, color: "text-red-600", bg: "bg-red-100" },
  modbus_disconnect: { Icon: AlertTriangle, color: "text-gray-500", bg: "bg-gray-50" },
  gen_switch_on: { Icon: Zap, color: "text-blue-500", bg: "bg-blue-50" },
  gen_switch_off: { Icon: ZapOff, color: "text-orange-500", bg: "bg-orange-50" },
  command_sent: { Icon: RotateCcw, color: "text-indigo-500", bg: "bg-indigo-50" },
};

/**
 * Reusable Event Log component for Generator/Device event history.
 * @param {string} generatorId - fetch events by generator ID (e.g. "dev-xxx")
 * @param {string} deviceId - fetch events by device ID
 * @param {boolean} compact - compact layout for embedded views (default false)
 * One of generatorId or deviceId must be provided.
 */
export default function EventLog({ generatorId, deviceId, compact = false }) {
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [total, setTotal] = useState(0);
  const [showMore, setShowMore] = useState(false);

  useEffect(() => {
    const load = async () => {
      try {
        const limit = showMore ? 100 : compact ? 10 : 20;
        let url;
        if (deviceId) {
          url = `/generators/events-by-device/${deviceId}?limit=${limit}`;
        } else if (generatorId) {
          url = `/generators/events/${generatorId}?limit=${limit}`;
        } else return;

        const res = await api.get(url);
        setEvents(res.data.events || []);
        setTotal(res.data.total || 0);
      } catch {
        /* no events yet */
      }
      setLoading(false);
    };
    load();
    const iv = setInterval(load, 30000);
    return () => clearInterval(iv);
  }, [generatorId, deviceId, showMore, compact]);

  if (loading) return null;
  if (events.length === 0) return null;

  const defaultLimit = compact ? 10 : 20;

  return (
    <div
      className={`bg-white border border-gray-200 ${compact ? "rounded-lg" : "rounded-xl"} overflow-hidden`}
      data-testid="event-log"
    >
      <div className="px-4 py-3 border-b border-gray-100 flex items-center justify-between">
        <h2 className={`${compact ? "text-xs" : "text-sm"} font-semibold text-gray-900 flex items-center gap-2`}>
          <FileText className={`${compact ? "w-3.5 h-3.5" : "w-4 h-4"} text-fuchsia-500`} />
          Ereignisprotokoll ({total})
        </h2>
      </div>
      <div className={`divide-y divide-gray-50 ${compact ? "max-h-[260px]" : "max-h-[400px]"} overflow-y-auto`}>
        {events.map((ev) => {
          const cfg = EVENT_ICONS[ev.event_type] || { Icon: AlertTriangle, color: "text-gray-500", bg: "bg-gray-50" };
          const { Icon } = cfg;
          return (
            <div
              key={ev.id}
              className={`px-4 ${compact ? "py-2" : "py-2.5"} flex items-start gap-3 hover:bg-gray-50/50`}
              data-testid="event-row"
            >
              <div className={`${compact ? "w-6 h-6" : "w-7 h-7"} rounded-full ${cfg.bg} flex items-center justify-center shrink-0 mt-0.5`}>
                <Icon className={`${compact ? "w-3 h-3" : "w-3.5 h-3.5"} ${cfg.color}`} />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className={`${compact ? "text-[11px]" : "text-xs"} font-medium text-gray-900`}>
                    {ev.event_label || ev.event_type}
                  </span>
                  {ev.active === false && (
                    <span className="text-[9px] px-1.5 py-0.5 bg-emerald-100 text-emerald-700 rounded-full">
                      behoben
                    </span>
                  )}
                </div>
                <p className={`${compact ? "text-[10px]" : "text-[11px]"} text-gray-500 mt-0.5 truncate`}>
                  {ev.description}
                </p>
                <div className="flex items-center gap-3 mt-0.5">
                  <span className="text-[10px] text-gray-400">
                    {new Date(ev.timestamp).toLocaleString("de-DE")}
                  </span>
                  {ev.latitude && ev.longitude && (
                    <span className="text-[10px] text-gray-400 flex items-center gap-0.5">
                      <MapPin className="w-2.5 h-2.5" />
                      {Number(ev.latitude).toFixed(4)}, {Number(ev.longitude).toFixed(4)}
                    </span>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>
      {total > defaultLimit && !showMore && (
        <div className="px-4 py-2 border-t border-gray-100">
          <button
            onClick={() => setShowMore(true)}
            className="text-xs text-fuchsia-600 hover:text-fuchsia-700 font-medium flex items-center gap-1"
            data-testid="show-more-events"
          >
            <ChevronDown className="w-3 h-3" />
            Alle {total} Ereignisse anzeigen
          </button>
        </div>
      )}
    </div>
  );
}
