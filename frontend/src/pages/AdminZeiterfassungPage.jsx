import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import api from "../lib/api";
import {
  ArrowLeft, Clock, User, MapPin, ChevronDown, ChevronUp, Search,
} from "lucide-react";
import { Input } from "../components/ui/input";

export default function AdminZeiterfassungPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const token = localStorage.getItem("token");
  const isAdmin = user?.role === "admin";

  const [timeReport, setTimeReport] = useState([]);
  const [search, setSearch] = useState("");
  const [month, setMonth] = useState(() => {
    const now = new Date();
    return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
  });
  const [expandedUser, setExpandedUser] = useState(null);

  const loadReport = useCallback(async () => {
    const [y, m] = month.split("-");
    const from = `${y}-${m}-01`;
    const lastDay = new Date(parseInt(y), parseInt(m), 0).getDate();
    const to = `${y}-${m}-${String(lastDay).padStart(2, "0")}`;
    try {
      const res = await api.get(`/employee/time/report?token=${token}&date_from=${from}&date_to=${to}`);
      setTimeReport(res.data);
    } catch {}
  }, [token, month]);

  useEffect(() => { loadReport(); }, [loadReport]);

  if (!isAdmin) { navigate("/hub"); return null; }

  const filtered = timeReport.filter(emp => {
    if (!search.trim()) return true;
    return emp.user_name?.toLowerCase().includes(search.toLowerCase());
  });

  const totalAllMinutes = filtered.reduce((s, e) => s + (e.total_minutes || 0), 0);
  const totalH = Math.floor(totalAllMinutes / 60);
  const totalM = Math.round(totalAllMinutes % 60);

  return (
    <div className="min-h-screen bg-gray-50" data-testid="admin-zeiterfassung-page">
      <header className="bg-white border-b border-gray-200 sticky top-0 z-10">
        <div className="max-w-5xl mx-auto px-4 py-3 flex items-center gap-3">
          <button onClick={() => navigate("/verwaltung")} className="text-gray-500 hover:text-gray-700" data-testid="back-btn">
            <ArrowLeft className="w-5 h-5" />
          </button>
          <Clock className="w-5 h-5 text-green-600" />
          <h1 className="text-lg font-semibold text-gray-900">Arbeitszeiterfassung</h1>
        </div>
      </header>

      <div className="max-w-5xl mx-auto px-4 py-5 space-y-4">
        {/* Controls */}
        <div className="flex flex-col sm:flex-row gap-3 items-start sm:items-center justify-between">
          <div className="flex items-center gap-3">
            <input
              type="month"
              value={month}
              onChange={e => setMonth(e.target.value)}
              className="border border-gray-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-green-400"
              data-testid="time-month-picker"
            />
            <div className="relative">
              <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
              <Input
                value={search}
                onChange={e => setSearch(e.target.value)}
                placeholder="Mitarbeiter suchen..."
                className="pl-10 w-[220px]"
                data-testid="time-search"
              />
            </div>
          </div>
          <div className="text-right">
            <p className="text-xs text-gray-500">{filtered.length} Mitarbeiter &middot; Gesamt: <span className="font-bold text-gray-900">{totalH}h {totalM}m</span></p>
          </div>
        </div>

        {/* Employee Cards */}
        {filtered.length === 0 ? (
          <div className="bg-white rounded-xl border border-gray-200 p-8 text-center">
            <Clock className="w-8 h-8 text-gray-300 mx-auto mb-2" />
            <p className="text-sm text-gray-400">Keine Zeiteinträge in diesem Monat</p>
          </div>
        ) : (
          <div className="space-y-3">
            {filtered.map(emp => {
              const hours = Math.floor(emp.total_minutes / 60);
              const mins = Math.round(emp.total_minutes % 60);
              const isOpen = expandedUser === emp.user_id;
              return (
                <div key={emp.user_id} className="bg-white rounded-xl border border-gray-200 overflow-hidden" data-testid={`time-user-${emp.user_id}`}>
                  <button
                    onClick={() => setExpandedUser(isOpen ? null : emp.user_id)}
                    className="w-full text-left px-4 py-3 flex items-center gap-3 hover:bg-gray-50 transition-colors"
                  >
                    <User className="w-5 h-5 text-gray-400 flex-shrink-0" />
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-gray-900">{emp.user_name}</p>
                      <p className="text-xs text-gray-500">{emp.entries.length} Einträge</p>
                    </div>
                    <span className="text-lg font-bold text-gray-900">{hours}h {mins}m</span>
                    {isOpen ? <ChevronUp className="w-4 h-4 text-gray-400" /> : <ChevronDown className="w-4 h-4 text-gray-400" />}
                  </button>
                  {isOpen && (
                    <div className="border-t border-gray-100 divide-y divide-gray-50">
                      {emp.entries.map(e => {
                        const dur = e.duration_minutes || 0;
                        const dH = Math.floor(dur / 60);
                        const dM = Math.round(dur % 60);
                        return (
                          <div key={e.id} className="px-4 py-2.5 flex items-center gap-3 text-xs" data-testid={`time-entry-${e.id}`}>
                            <span className="font-medium text-gray-700 w-24 flex-shrink-0">
                              {new Date(e.clock_in).toLocaleDateString("de-DE", { weekday: "short", day: "2-digit", month: "2-digit" })}
                            </span>
                            <span className="text-green-600 font-medium">
                              {new Date(e.clock_in).toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" })}
                            </span>
                            <span className="text-gray-400">—</span>
                            <span className="text-red-500 font-medium">
                              {e.clock_out ? new Date(e.clock_out).toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" }) : "Aktiv"}
                            </span>
                            <span className="font-semibold text-gray-900 ml-auto">
                              {dur > 0 ? (dH > 0 ? `${dH}h ${dM}m` : `${dM}m`) : "—"}
                            </span>
                            {e.clock_in_lat && (
                              <a
                                href={`https://www.google.com/maps?q=${e.clock_in_lat},${e.clock_in_lng}`}
                                target="_blank" rel="noreferrer"
                                className="text-gray-400 hover:text-fuchsia-600"
                                title={`Ein: ${e.clock_in_lat?.toFixed(4)}, ${e.clock_in_lng?.toFixed(4)}`}
                                onClick={ev => ev.stopPropagation()}
                              >
                                <MapPin className="w-3 h-3" />
                              </a>
                            )}
                            {e.clock_out_lat && (
                              <a
                                href={`https://www.google.com/maps?q=${e.clock_out_lat},${e.clock_out_lng}`}
                                target="_blank" rel="noreferrer"
                                className="text-gray-400 hover:text-green-600"
                                title={`Aus: ${e.clock_out_lat?.toFixed(4)}, ${e.clock_out_lng?.toFixed(4)}`}
                                onClick={ev => ev.stopPropagation()}
                              >
                                <MapPin className="w-3 h-3" />
                              </a>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
