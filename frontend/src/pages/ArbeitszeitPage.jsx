import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import api from "../lib/api";
import {
  ArrowLeft, Clock, CalendarDays, CalendarOff, Palmtree, TrendingUp,
  ThermometerSun, ChevronDown, ChevronUp, Archive,
} from "lucide-react";

export default function ArbeitszeitPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const token = localStorage.getItem("token");

  const [hrData, setHrData] = useState(null);
  const [timeOffRequests, setTimeOffRequests] = useState([]);
  const [vacationEntries, setVacationEntries] = useState([]);
  const [yearEntries, setYearEntries] = useState([]);
  const [expandedMonth, setExpandedMonth] = useState(null);
  const [archiveOpen, setArchiveOpen] = useState(null);

  const year = new Date().getFullYear();
  const currentMonth = new Date().getMonth();
  const months = Array.from({ length: 12 }, (_, i) => {
    const m = String(i + 1).padStart(2, "0");
    return { key: `${year}-${m}`, label: new Date(year, i).toLocaleDateString("de-DE", { month: "long" }), idx: i };
  }).reverse();

  useEffect(() => {
    if (!user?.id) return;
    api.get(`/employee/hr-data/${user.id}?token=${token}`).then(r => setHrData(r.data)).catch(() => {});
  }, [token, user?.id]);

  useEffect(() => {
    api.get(`/employee/time-off?token=${token}`).then(r => setTimeOffRequests(r.data || [])).catch(() => {});
  }, [token]);

  useEffect(() => {
    if (!user?.id) return;
    api.get(`/employee/vacation/${user.id}?token=${token}`).then(r => setVacationEntries(r.data || [])).catch(() => {});
  }, [token, user?.id]);

  // Load ALL time entries for the year at once
  useEffect(() => {
    const from = `${year}-01-01`;
    const to = `${year}-12-31`;
    api.get(`/employee/time/entries?token=${token}&date_from=${from}&date_to=${to}`).then(r => setYearEntries(r.data || [])).catch(() => {});
  }, [token, year]);

  // Group entries by month
  const entriesByMonth = {};
  yearEntries.forEach(e => {
    const m = e.clock_in?.substring(0, 7); // "2026-04"
    if (!m) return;
    if (!entriesByMonth[m]) entriesByMonth[m] = [];
    entriesByMonth[m].push(e);
  });

  const getMonthStats = (monthKey) => {
    const [y, m] = monthKey.split("-");
    const prefix = `${y}-${m}`;
    const entries = entriesByMonth[monthKey] || [];
    const totalMins = entries.reduce((s, e) => s + (e.duration_minutes || 0), 0);
    const vacs = vacationEntries.filter(v => v.start_date?.startsWith(prefix) || v.end_date?.startsWith(prefix));
    const vacDays = vacs.reduce((s, v) => s + (v.days || 0), 0);
    const sicks = timeOffRequests.filter(r => r.type === "krank" && r.status === "approved" && (r.start_date?.startsWith(prefix) || r.end_date?.startsWith(prefix)));
    const sickDays = sicks.reduce((s, r) => s + (r.days || 0), 0);
    const offs = timeOffRequests.filter(r => r.type === "ueberstundenabbau" && r.status === "approved" && (r.start_date?.startsWith(prefix) || r.end_date?.startsWith(prefix)));
    return { entries, totalMins, vacs, vacDays, sicks, sickDays, offs };
  };

  const sickDaysYear = timeOffRequests
    .filter(r => r.type === "krank" && r.status === "approved" && r.start_date?.startsWith(String(year)))
    .reduce((s, r) => s + (r.days || 0), 0);

  const formatTime = (iso) => new Date(iso).toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" });
  const formatDur = (mins) => { if (!mins) return "—"; const h = Math.floor(mins / 60); const m = Math.round(mins % 60); return `${h}h ${m}m`; };
  const fmtH = (mins) => { const h = Math.floor(mins / 60); const m = Math.round(mins % 60); return h > 0 ? `${h}h ${m}m` : m > 0 ? `${m}m` : ""; };

  return (
    <div className="min-h-screen bg-gray-50" data-testid="arbeitszeit-page">
      <header className="bg-white border-b border-gray-200 sticky top-0 z-10">
        <div className="max-w-3xl mx-auto px-4 py-3 flex items-center gap-3">
          <button onClick={() => navigate("/mitarbeiter-daten")} className="text-gray-500 hover:text-gray-700" data-testid="back-btn">
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
          <div className="bg-white rounded-xl border border-gray-200 p-3 flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-sky-100 flex items-center justify-center flex-shrink-0">
              <Palmtree className="w-4 h-4 text-sky-600" />
            </div>
            <div>
              <p className="text-[10px] font-medium text-sky-600 uppercase tracking-wider">Resturlaub</p>
              <p className="text-xl font-bold text-sky-800 leading-tight">{hrData?.vacation_days_remaining ?? 0} <span className="text-xs font-normal text-sky-500">Tage</span></p>
            </div>
          </div>
          <div className="bg-white rounded-xl border border-gray-200 p-3 flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-amber-100 flex items-center justify-center flex-shrink-0">
              <TrendingUp className="w-4 h-4 text-amber-600" />
            </div>
            <div>
              <p className="text-[10px] font-medium text-amber-600 uppercase tracking-wider">Überstunden</p>
              <p className="text-xl font-bold text-amber-800 leading-tight">{hrData?.overtime_hours ?? 0} <span className="text-xs font-normal text-amber-500">Std.</span></p>
            </div>
          </div>
          <div className="bg-white rounded-xl border border-gray-200 p-3 flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-red-100 flex items-center justify-center flex-shrink-0">
              <ThermometerSun className="w-4 h-4 text-red-500" />
            </div>
            <div>
              <p className="text-[10px] font-medium text-red-500 uppercase tracking-wider">Krankheit</p>
              <p className="text-xl font-bold text-red-800 leading-tight">{sickDaysYear} <span className="text-xs font-normal text-red-400">Tage</span></p>
            </div>
          </div>
        </div>

        {/* Genehmigte Urlaube & Überstundenabbau Übersicht */}
        {(vacationEntries.length > 0 || timeOffRequests.filter(r => r.type === "ueberstundenabbau" && r.status === "approved").length > 0) && (
          <div className="bg-white rounded-xl border border-gray-200 p-4 space-y-3" data-testid="approved-overview">
            {vacationEntries.length > 0 && (
              <div>
                <div className="flex items-center gap-2 mb-1.5">
                  <Palmtree className="w-3.5 h-3.5 text-sky-600" />
                  <span className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider">Genehmigte Urlaube</span>
                  <span className="text-xs font-bold text-sky-700 ml-auto">{vacationEntries.reduce((s, v) => s + (v.days || 0), 0)} Tage</span>
                </div>
                <div className="space-y-1">
                  {vacationEntries.map(v => (
                    <div key={v.id} className="flex items-center gap-2 bg-sky-50 rounded-lg px-3 py-1.5 text-sm">
                      <span className="text-sky-700">{new Date(v.start_date + "T00:00").toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit", year: "numeric" })}</span>
                      <span className="text-gray-400">—</span>
                      <span className="text-sky-700">{new Date(v.end_date + "T00:00").toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit", year: "numeric" })}</span>
                      <span className="text-sky-700 font-bold ml-auto">{v.days} Tage</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
            {timeOffRequests.filter(r => r.type === "ueberstundenabbau" && r.status === "approved").length > 0 && (
              <div>
                <div className="flex items-center gap-2 mb-1.5">
                  <TrendingUp className="w-3.5 h-3.5 text-amber-600" />
                  <span className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider">Überstundenabbau</span>
                </div>
                <div className="space-y-1">
                  {timeOffRequests.filter(r => r.type === "ueberstundenabbau" && r.status === "approved").map(r => (
                    <div key={r.id} className="flex items-center gap-2 bg-amber-50 rounded-lg px-3 py-1.5 text-sm">
                      <span className="text-amber-700">{new Date(r.start_date + "T00:00").toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit", year: "numeric" })}</span>
                      {r.end_date !== r.start_date && <><span className="text-gray-400">—</span><span className="text-amber-700">{new Date(r.end_date + "T00:00").toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit", year: "numeric" })}</span></>}
                      {r.days > 0 && <span className="text-amber-700 font-bold ml-auto">{r.days} Tage</span>}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Pending Requests */}
        {timeOffRequests.filter(r => r.status === "pending").length > 0 && (
          <div className="bg-amber-50 rounded-xl border border-amber-200 p-3">
            <div className="flex items-center gap-2 mb-1.5">
              <CalendarOff className="w-3.5 h-3.5 text-amber-600" />
              <span className="text-[10px] font-semibold text-amber-600 uppercase tracking-wider">Offene Anträge</span>
            </div>
            {timeOffRequests.filter(r => r.status === "pending").map(r => (
              <div key={r.id} className="flex items-center gap-2 text-sm text-amber-800">
                <span className="font-medium">{r.type_label}</span>
                <span>{new Date(r.start_date + "T00:00").toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit" })}{r.end_date !== r.start_date && ` — ${new Date(r.end_date + "T00:00").toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit" })}`}</span>
                <span className="text-[10px] bg-amber-200 text-amber-800 px-1.5 py-0.5 rounded-full font-bold ml-auto">In Bearbeitung</span>
              </div>
            ))}
          </div>
        )}

        {/* Rejected / Withdrawn Requests - current year + archive */}
        {(() => {
          const currentYearStr = String(year);
          const currentYearItems = timeOffRequests.filter(r =>
            (r.status === "rejected" || r.status === "withdrawn") && r.start_date?.startsWith(currentYearStr)
          );
          const archiveItems = timeOffRequests.filter(r =>
            (r.status === "rejected" || r.status === "withdrawn") && !r.start_date?.startsWith(currentYearStr)
          );
          const archiveYears = [...new Set(archiveItems.map(r => r.start_date?.slice(0, 4)))].sort((a, b) => b - a);

          return (
            <>
              {currentYearItems.length > 0 && (
                <div className="bg-gray-50 rounded-xl border border-gray-200 p-3">
                  <div className="flex items-center gap-2 mb-1.5">
                    <CalendarOff className="w-3.5 h-3.5 text-gray-400" />
                    <span className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider">Abgelehnt / Zurückgezogen ({currentYearStr})</span>
                  </div>
                  {currentYearItems.map(r => (
                    <div key={r.id} className="flex items-center gap-2 text-sm text-gray-500">
                      <span className="font-medium">{r.type_label}</span>
                      <span>{new Date(r.start_date + "T00:00").toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit" })}{r.end_date !== r.start_date && ` — ${new Date(r.end_date + "T00:00").toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit" })}`}</span>
                      <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-bold ml-auto ${r.status === "rejected" ? "bg-red-100 text-red-600" : "bg-gray-200 text-gray-600"}`}>
                        {r.status === "rejected" ? "Abgelehnt" : "Zurückgezogen"}
                      </span>
                    </div>
                  ))}
                </div>
              )}

              {archiveYears.length > 0 && (
                <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
                  <div className="flex items-center gap-2 px-3 py-2">
                    <Archive className="w-3.5 h-3.5 text-gray-400" />
                    <span className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider">Archiv — Abgelehnt / Zurückgezogen</span>
                  </div>
                  {archiveYears.map(ay => {
                    const items = archiveItems.filter(r => r.start_date?.startsWith(ay));
                    const isOpen = archiveOpen === ay;
                    return (
                      <div key={ay} className="border-t border-gray-100">
                        <button onClick={() => setArchiveOpen(isOpen ? null : ay)} className="w-full text-left px-3 py-2 flex items-center gap-2 hover:bg-gray-50 transition-colors">
                          <span className="text-sm font-semibold text-gray-700">{ay}</span>
                          <span className="text-xs text-gray-400 ml-1">({items.length})</span>
                          <div className="ml-auto">{isOpen ? <ChevronUp className="w-3.5 h-3.5 text-gray-400" /> : <ChevronDown className="w-3.5 h-3.5 text-gray-400" />}</div>
                        </button>
                        {isOpen && (
                          <div className="px-3 pb-2.5 space-y-0.5">
                            {items.map(r => (
                              <div key={r.id} className="flex items-center gap-2 text-sm text-gray-500">
                                <span className="font-medium">{r.type_label}</span>
                                <span>{new Date(r.start_date + "T00:00").toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit" })}{r.end_date !== r.start_date && ` — ${new Date(r.end_date + "T00:00").toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit" })}`}</span>
                                <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-bold ml-auto ${r.status === "rejected" ? "bg-red-100 text-red-600" : "bg-gray-200 text-gray-600"}`}>
                                  {r.status === "rejected" ? "Abgelehnt" : "Zurückgezogen"}
                                </span>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </>
          );
        })()}

        {/* Monthly Breakdown */}
        <div className="space-y-2">
          {months.filter(m => m.idx <= currentMonth).map(m => {
            const stats = getMonthStats(m.key);
            const isOpen = expandedMonth === m.key;
            const hasHours = stats.totalMins > 0;
            const hasVac = stats.vacDays > 0;
            const hasSick = stats.sickDays > 0;

            return (
              <div key={m.key} className="bg-white rounded-xl border border-gray-200 overflow-hidden" data-testid={`month-${m.key}`}>
                <button
                  onClick={() => setExpandedMonth(isOpen ? null : m.key)}
                  className="w-full text-left px-4 py-3 flex items-center gap-3 hover:bg-gray-50 transition-colors"
                >
                  <CalendarDays className="w-4 h-4 text-gray-400 flex-shrink-0" />
                  <span className="text-sm font-semibold text-gray-900">{m.label}</span>
                  <div className="flex items-center gap-2 ml-auto">
                    {hasHours && (
                      <span className="text-xs font-bold text-gray-700 bg-gray-100 px-2 py-0.5 rounded">
                        <Clock className="w-3 h-3 inline mr-0.5 -mt-0.5" />{fmtH(stats.totalMins)}
                      </span>
                    )}
                    {hasVac && (
                      <span className="text-xs font-bold text-sky-700 bg-sky-50 px-2 py-0.5 rounded">
                        <Palmtree className="w-3 h-3 inline mr-0.5 -mt-0.5" />{stats.vacDays}T
                      </span>
                    )}
                    {hasSick && (
                      <span className="text-xs font-bold text-red-600 bg-red-50 px-2 py-0.5 rounded">
                        <ThermometerSun className="w-3 h-3 inline mr-0.5 -mt-0.5" />{stats.sickDays}T
                      </span>
                    )}
                    {isOpen ? <ChevronUp className="w-4 h-4 text-gray-400" /> : <ChevronDown className="w-4 h-4 text-gray-400" />}
                  </div>
                </button>

                {isOpen && (
                  <div className="border-t border-gray-100 divide-y divide-gray-50">
                    {stats.vacs.map(v => (
                      <div key={v.id} className="px-4 py-2.5 flex items-center gap-3 bg-sky-50/50">
                        <Palmtree className="w-3.5 h-3.5 text-sky-500 flex-shrink-0" />
                        <span className="text-xs font-semibold text-sky-700">Urlaub</span>
                        <span className="text-xs text-sky-600">
                          {new Date(v.start_date + "T00:00").toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit" })} — {new Date(v.end_date + "T00:00").toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit" })}
                        </span>
                        <span className="text-xs font-bold text-sky-700 ml-auto">{v.days} Tage</span>
                      </div>
                    ))}
                    {stats.sicks.map(r => (
                      <div key={r.id} className="px-4 py-2.5 flex items-center gap-3 bg-red-50/50">
                        <ThermometerSun className="w-3.5 h-3.5 text-red-400 flex-shrink-0" />
                        <span className="text-xs font-semibold text-red-600">Krank</span>
                        <span className="text-xs text-red-500">
                          {new Date(r.start_date + "T00:00").toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit" })}{r.end_date !== r.start_date && ` — ${new Date(r.end_date + "T00:00").toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit" })}`}
                        </span>
                        <span className="text-xs font-bold text-red-600 ml-auto">{r.days} Tage</span>
                      </div>
                    ))}
                    {stats.offs.map(r => (
                      <div key={r.id} className="px-4 py-2.5 flex items-center gap-3 bg-amber-50/50">
                        <TrendingUp className="w-3.5 h-3.5 text-amber-500 flex-shrink-0" />
                        <span className="text-xs font-semibold text-amber-700">Überstundenabbau</span>
                        <span className="text-xs text-amber-600">
                          {new Date(r.start_date + "T00:00").toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit" })}{r.end_date !== r.start_date && ` — ${new Date(r.end_date + "T00:00").toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit" })}`}
                        </span>
                        {r.days > 0 && <span className="text-xs font-bold text-amber-700 ml-auto">{r.days} Tage</span>}
                      </div>
                    ))}
                    {stats.entries.map(e => (
                      <div key={e.id} className="px-4 py-2.5 flex items-center gap-3 text-xs">
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
                    {stats.entries.length === 0 && stats.vacs.length === 0 && stats.sicks.length === 0 && stats.offs.length === 0 && (
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
