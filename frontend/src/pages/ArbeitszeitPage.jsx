import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import api from "../lib/api";
import {
  ArrowLeft, Clock, CalendarDays, CalendarOff, Palmtree, TrendingUp,
  ThermometerSun, ChevronDown, ChevronUp,
} from "lucide-react";

export default function ArbeitszeitPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const token = localStorage.getItem("token");

  const [hrData, setHrData] = useState(null);
  const [timeOffRequests, setTimeOffRequests] = useState([]);
  const [vacationEntries, setVacationEntries] = useState([]);
  const [allEntries, setAllEntries] = useState({});
  const [expandedMonth, setExpandedMonth] = useState(null);

  // Current year months
  const year = new Date().getFullYear();
  const currentMonth = new Date().getMonth(); // 0-based
  const months = Array.from({ length: 12 }, (_, i) => {
    const m = String(i + 1).padStart(2, "0");
    return { key: `${year}-${m}`, label: new Date(year, i).toLocaleDateString("de-DE", { month: "long" }), idx: i };
  }).reverse(); // newest first

  // Load HR data
  useEffect(() => {
    if (!user?.id) return;
    api.get(`/employee/hr-data/${user.id}?token=${token}`).then(r => setHrData(r.data)).catch(() => {});
  }, [token, user?.id]);

  // Load time-off requests
  useEffect(() => {
    api.get(`/employee/time-off?token=${token}`).then(r => setTimeOffRequests(r.data || [])).catch(() => {});
  }, [token]);

  // Load vacation entries
  useEffect(() => {
    if (!user?.id) return;
    api.get(`/employee/vacation/${user.id}?token=${token}`).then(r => setVacationEntries(r.data || [])).catch(() => {});
  }, [token, user?.id]);

  // Load entries for a month when expanded
  const loadMonth = useCallback(async (monthKey) => {
    if (allEntries[monthKey]) return;
    const [y, m] = monthKey.split("-");
    const from = `${y}-${m}-01`;
    const lastDay = new Date(parseInt(y), parseInt(m), 0).getDate();
    const to = `${y}-${m}-${String(lastDay).padStart(2, "0")}`;
    try {
      const res = await api.get(`/employee/time/entries?token=${token}&date_from=${from}&date_to=${to}`);
      setAllEntries(prev => ({ ...prev, [monthKey]: res.data || [] }));
    } catch {
      setAllEntries(prev => ({ ...prev, [monthKey]: [] }));
    }
  }, [token, allEntries]);

  const toggleMonth = (monthKey) => {
    if (expandedMonth === monthKey) {
      setExpandedMonth(null);
    } else {
      setExpandedMonth(monthKey);
      loadMonth(monthKey);
    }
  };

  // Calc sick days this year
  const sickDays = timeOffRequests
    .filter(r => r.type === "krank" && r.status === "approved" && r.start_date?.startsWith(String(year)))
    .reduce((s, r) => s + (r.days || 0), 0);

  const vacRemaining = hrData ? hrData.vacation_days_remaining : 0;
  const overtime = hrData ? hrData.overtime_hours : 0;

  const formatTime = (iso) => new Date(iso).toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" });
  const formatDur = (mins) => { if (!mins) return "—"; const h = Math.floor(mins / 60); const m = Math.round(mins % 60); return `${h}h ${m}m`; };

  // Get vacation/sick entries for a specific month
  const getMonthExtras = (monthKey) => {
    const [y, m] = monthKey.split("-");
    const prefix = `${y}-${m}`;
    const vacs = vacationEntries.filter(v => v.start_date?.startsWith(prefix) || v.end_date?.startsWith(prefix));
    const sicks = timeOffRequests.filter(r => r.type === "krank" && r.status === "approved" && (r.start_date?.startsWith(prefix) || r.end_date?.startsWith(prefix)));
    const offs = timeOffRequests.filter(r => r.type === "ueberstundenabbau" && r.status === "approved" && (r.start_date?.startsWith(prefix) || r.end_date?.startsWith(prefix)));
    return { vacs, sicks, offs };
  };

  // Check if a month has any data
  const monthHasData = (monthKey) => {
    const extras = getMonthExtras(monthKey);
    const entries = allEntries[monthKey];
    if (entries && entries.length > 0) return true;
    if (extras.vacs.length > 0 || extras.sicks.length > 0 || extras.offs.length > 0) return true;
    return false;
  };

  return (
    <div className="min-h-screen bg-gray-50" data-testid="arbeitszeit-page">
      <header className="bg-white border-b border-gray-200 sticky top-0 z-10">
        <div className="max-w-3xl mx-auto px-4 py-3 flex items-center gap-3">
          <button onClick={() => navigate("/hub")} className="text-gray-500 hover:text-gray-700" data-testid="back-btn">
            <ArrowLeft className="w-5 h-5" />
          </button>
          <Clock className="w-5 h-5 text-fuchsia-600" />
          <h1 className="text-lg font-semibold text-gray-900">Meine Arbeitszeit</h1>
          <span className="text-sm text-gray-400 ml-auto">{year}</span>
        </div>
      </header>

      <div className="max-w-3xl mx-auto px-4 py-5 space-y-4">
        {/* Summary Cards */}
        <div className="grid grid-cols-3 gap-3" data-testid="summary-cards">
          <div className="bg-white rounded-xl border border-gray-200 p-3 flex items-center gap-3" data-testid="card-vacation">
            <div className="w-9 h-9 rounded-lg bg-sky-100 flex items-center justify-center flex-shrink-0">
              <Palmtree className="w-4 h-4 text-sky-600" />
            </div>
            <div>
              <p className="text-[10px] font-medium text-sky-600 uppercase tracking-wider">Resturlaub</p>
              <p className="text-xl font-bold text-sky-800 leading-tight">{vacRemaining} <span className="text-xs font-normal text-sky-500">Tage</span></p>
            </div>
          </div>
          <div className="bg-white rounded-xl border border-gray-200 p-3 flex items-center gap-3" data-testid="card-overtime">
            <div className="w-9 h-9 rounded-lg bg-amber-100 flex items-center justify-center flex-shrink-0">
              <TrendingUp className="w-4 h-4 text-amber-600" />
            </div>
            <div>
              <p className="text-[10px] font-medium text-amber-600 uppercase tracking-wider">Überstunden</p>
              <p className="text-xl font-bold text-amber-800 leading-tight">{overtime} <span className="text-xs font-normal text-amber-500">Std.</span></p>
            </div>
          </div>
          <div className="bg-white rounded-xl border border-gray-200 p-3 flex items-center gap-3" data-testid="card-sick">
            <div className="w-9 h-9 rounded-lg bg-red-100 flex items-center justify-center flex-shrink-0">
              <ThermometerSun className="w-4 h-4 text-red-500" />
            </div>
            <div>
              <p className="text-[10px] font-medium text-red-500 uppercase tracking-wider">Krankheit</p>
              <p className="text-xl font-bold text-red-800 leading-tight">{sickDays} <span className="text-xs font-normal text-red-400">Tage</span></p>
            </div>
          </div>
        </div>

        {/* Pending Requests */}
        {timeOffRequests.filter(r => r.status === "pending").length > 0 && (
          <div className="bg-amber-50 rounded-xl border border-amber-200 p-3" data-testid="pending-requests">
            <div className="flex items-center gap-2 mb-1.5">
              <CalendarOff className="w-3.5 h-3.5 text-amber-600" />
              <span className="text-[10px] font-semibold text-amber-600 uppercase tracking-wider">Offene Anträge</span>
            </div>
            <div className="space-y-1">
              {timeOffRequests.filter(r => r.status === "pending").map(r => (
                <div key={r.id} className="flex items-center gap-2 text-sm text-amber-800">
                  <span className="font-medium">{r.type_label}</span>
                  <span>{new Date(r.start_date + "T00:00").toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit" })}{r.end_date !== r.start_date && ` — ${new Date(r.end_date + "T00:00").toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit" })}`}</span>
                  <span className="text-[10px] bg-amber-200 text-amber-800 px-1.5 py-0.5 rounded-full font-bold ml-auto">In Bearbeitung</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Monthly Breakdown */}
        <div className="space-y-2" data-testid="monthly-breakdown">
          {months.filter(m => m.idx <= currentMonth).map(m => {
            const isOpen = expandedMonth === m.key;
            const monthEntries = allEntries[m.key] || [];
            const extras = getMonthExtras(m.key);
            const totalMins = monthEntries.reduce((s, e) => s + (e.duration_minutes || 0), 0);
            const tH = Math.floor(totalMins / 60);
            const tM = Math.round(totalMins % 60);
            const hasContent = monthEntries.length > 0 || extras.vacs.length > 0 || extras.sicks.length > 0 || extras.offs.length > 0;

            return (
              <div key={m.key} className="bg-white rounded-xl border border-gray-200 overflow-hidden" data-testid={`month-${m.key}`}>
                <button
                  onClick={() => toggleMonth(m.key)}
                  className="w-full text-left px-4 py-3 flex items-center gap-3 hover:bg-gray-50 transition-colors"
                >
                  <CalendarDays className="w-4 h-4 text-gray-400 flex-shrink-0" />
                  <span className="text-sm font-semibold text-gray-900 flex-1">{m.label}</span>
                  {isOpen && totalMins > 0 && <span className="text-sm font-bold text-gray-700">{tH}h {tM}m</span>}
                  {isOpen ? <ChevronUp className="w-4 h-4 text-gray-400" /> : <ChevronDown className="w-4 h-4 text-gray-400" />}
                </button>

                {isOpen && (
                  <div className="border-t border-gray-100 divide-y divide-gray-50">
                    {/* Vacation entries for this month */}
                    {extras.vacs.map(v => (
                      <div key={v.id} className="px-4 py-2.5 flex items-center gap-3 bg-sky-50/50">
                        <Palmtree className="w-3.5 h-3.5 text-sky-500 flex-shrink-0" />
                        <span className="text-xs font-semibold text-sky-700">Urlaub</span>
                        <span className="text-xs text-sky-600">
                          {new Date(v.start_date + "T00:00").toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit" })} — {new Date(v.end_date + "T00:00").toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit" })}
                        </span>
                        <span className="text-xs font-bold text-sky-700 ml-auto">{v.days} Tage</span>
                      </div>
                    ))}

                    {/* Sick entries for this month */}
                    {extras.sicks.map(r => (
                      <div key={r.id} className="px-4 py-2.5 flex items-center gap-3 bg-red-50/50">
                        <ThermometerSun className="w-3.5 h-3.5 text-red-400 flex-shrink-0" />
                        <span className="text-xs font-semibold text-red-600">Krank</span>
                        <span className="text-xs text-red-500">
                          {new Date(r.start_date + "T00:00").toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit" })}{r.end_date !== r.start_date && ` — ${new Date(r.end_date + "T00:00").toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit" })}`}
                        </span>
                        <span className="text-xs font-bold text-red-600 ml-auto">{r.days} Tage</span>
                      </div>
                    ))}

                    {/* Overtime reduction */}
                    {extras.offs.map(r => (
                      <div key={r.id} className="px-4 py-2.5 flex items-center gap-3 bg-amber-50/50">
                        <TrendingUp className="w-3.5 h-3.5 text-amber-500 flex-shrink-0" />
                        <span className="text-xs font-semibold text-amber-700">Überstundenabbau</span>
                        <span className="text-xs text-amber-600">
                          {new Date(r.start_date + "T00:00").toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit" })}{r.end_date !== r.start_date && ` — ${new Date(r.end_date + "T00:00").toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit" })}`}
                        </span>
                        {r.days > 0 && <span className="text-xs font-bold text-amber-700 ml-auto">{r.days} Tage</span>}
                      </div>
                    ))}

                    {/* Time entries */}
                    {monthEntries.map(e => (
                      <div key={e.id} className="px-4 py-2.5 flex items-center gap-3 text-xs" data-testid={`entry-${e.id}`}>
                        <Clock className="w-3.5 h-3.5 text-gray-400 flex-shrink-0" />
                        <span className="font-medium text-gray-700 w-24 flex-shrink-0">
                          {new Date(e.clock_in).toLocaleDateString("de-DE", { weekday: "short", day: "2-digit", month: "2-digit" })}
                        </span>
                        <span className="text-green-600 font-medium">{formatTime(e.clock_in)}</span>
                        <span className="text-gray-300">—</span>
                        <span className={`font-medium ${e.clock_out ? "text-red-500" : "text-amber-500 animate-pulse"}`}>
                          {e.clock_out ? formatTime(e.clock_out) : "Aktiv"}
                        </span>
                        <span className="font-bold text-gray-900 ml-auto">{formatDur(e.duration_minutes)}</span>
                      </div>
                    ))}

                    {!hasContent && (
                      <div className="px-4 py-4 text-center text-xs text-gray-400">Keine Einträge</div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
