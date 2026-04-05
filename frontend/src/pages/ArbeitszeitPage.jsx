import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import api from "../lib/api";
import {
  ArrowLeft, Clock, Calendar, MapPin, ChevronDown, ChevronUp,
} from "lucide-react";

export default function ArbeitszeitPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const token = localStorage.getItem("token");

  const [entries, setEntries] = useState([]);
  const [month, setMonth] = useState(() => {
    const now = new Date();
    return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
  });

  const loadEntries = useCallback(async () => {
    const [y, m] = month.split("-");
    const from = `${y}-${m}-01`;
    const lastDay = new Date(parseInt(y), parseInt(m), 0).getDate();
    const to = `${y}-${m}-${String(lastDay).padStart(2, "0")}`;
    try {
      const res = await api.get(`/employee/time/entries?token=${token}&date_from=${from}&date_to=${to}`);
      setEntries(res.data);
    } catch {}
  }, [token, month]);

  useEffect(() => { loadEntries(); }, [loadEntries]);

  const totalMinutes = entries.reduce((sum, e) => sum + (e.duration_minutes || 0), 0);
  const totalHours = Math.floor(totalMinutes / 60);
  const totalMins = Math.round(totalMinutes % 60);

  const formatTime = (iso) => {
    if (!iso) return "—";
    return new Date(iso).toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" });
  };
  const formatDuration = (mins) => {
    if (!mins) return "—";
    const h = Math.floor(mins / 60);
    const m = Math.round(mins % 60);
    return `${h}h ${m}m`;
  };

  const monthLabel = new Date(month + "-01").toLocaleDateString("de-DE", { month: "long", year: "numeric" });

  return (
    <div className="min-h-screen bg-gray-50" data-testid="arbeitszeit-page">
      <header className="bg-white border-b border-gray-200 sticky top-0 z-10">
        <div className="max-w-3xl mx-auto px-4 py-3 flex items-center gap-3">
          <button onClick={() => navigate("/hub")} className="text-gray-500 hover:text-gray-700" data-testid="back-btn">
            <ArrowLeft className="w-5 h-5" />
          </button>
          <Clock className="w-5 h-5 text-fuchsia-600" />
          <h1 className="text-lg font-semibold text-gray-900">Meine Arbeitszeit</h1>
        </div>
      </header>

      <div className="max-w-3xl mx-auto px-4 py-5 space-y-4">
        {/* Month Selector + Total */}
        <div className="flex items-center justify-between">
          <input
            type="month"
            value={month}
            onChange={e => setMonth(e.target.value)}
            className="border border-gray-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-fuchsia-400"
            data-testid="month-picker"
          />
          <div className="text-right">
            <p className="text-2xl font-bold text-gray-900" data-testid="total-hours">{totalHours}h {totalMins}m</p>
            <p className="text-xs text-gray-500">{entries.filter(e => e.clock_out).length} Einträge in {monthLabel}</p>
          </div>
        </div>

        {/* Entries */}
        {entries.length === 0 ? (
          <div className="bg-white rounded-xl border border-gray-200 p-8 text-center">
            <Clock className="w-8 h-8 text-gray-300 mx-auto mb-2" />
            <p className="text-sm text-gray-400">Keine Einträge in diesem Monat</p>
          </div>
        ) : (
          <div className="space-y-2">
            {entries.map(e => (
              <div key={e.id} className="bg-white rounded-xl border border-gray-200 px-4 py-3" data-testid={`time-entry-${e.id}`}>
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-gray-900">
                      {new Date(e.clock_in).toLocaleDateString("de-DE", { weekday: "short", day: "2-digit", month: "2-digit", year: "numeric" })}
                    </p>
                    <div className="flex items-center gap-3 mt-1 text-xs text-gray-500">
                      <span className="text-green-600 font-medium">{formatTime(e.clock_in)}</span>
                      <span>—</span>
                      <span className={`font-medium ${e.clock_out ? "text-red-500" : "text-amber-500 animate-pulse"}`}>
                        {e.clock_out ? formatTime(e.clock_out) : "Aktiv"}
                      </span>
                    </div>
                  </div>
                  <div className="text-right">
                    <p className="text-sm font-semibold text-gray-900">{formatDuration(e.duration_minutes)}</p>
                  </div>
                </div>
                {/* GPS */}
                {(e.clock_in_lat || e.clock_out_lat) && (
                  <div className="mt-2 flex gap-4 text-[10px] text-gray-400">
                    {e.clock_in_lat && (
                      <a
                        href={`https://www.google.com/maps?q=${e.clock_in_lat},${e.clock_in_lng}`}
                        target="_blank" rel="noreferrer"
                        className="flex items-center gap-0.5 hover:text-fuchsia-600"
                      >
                        <MapPin className="w-2.5 h-2.5" /> Ein: {e.clock_in_lat?.toFixed(4)}, {e.clock_in_lng?.toFixed(4)}
                      </a>
                    )}
                    {e.clock_out_lat && (
                      <a
                        href={`https://www.google.com/maps?q=${e.clock_out_lat},${e.clock_out_lng}`}
                        target="_blank" rel="noreferrer"
                        className="flex items-center gap-0.5 hover:text-fuchsia-600"
                      >
                        <MapPin className="w-2.5 h-2.5" /> Aus: {e.clock_out_lat?.toFixed(4)}, {e.clock_out_lng?.toFixed(4)}
                      </a>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
