import { useState, useEffect, useCallback } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import api from "../lib/api";
import { toast } from "sonner";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import {
  ArrowLeft, Clock, User, MapPin, Save, Palmtree, TrendingUp,
  Plus, Trash2, CalendarDays, ThermometerSun, ChevronDown, ChevronUp,
} from "lucide-react";

export default function AdminZeitDetailPage() {
  const { user } = useAuth();
  const { userId } = useParams();
  const navigate = useNavigate();
  const token = localStorage.getItem("token");
  const isAdmin = user?.role === "admin";

  const [userName, setUserName] = useState("");
  const year = new Date().getFullYear();
  const currentMonth = new Date().getMonth();

  // HR Data
  const [overtimeHours, setOvertimeHours] = useState("");
  const [vacationTotal, setVacationTotal] = useState("");
  const [hrData, setHrData] = useState(null);
  const [saving, setSaving] = useState(false);

  // Vacation entries
  const [vacationEntries, setVacationEntries] = useState([]);
  const [vacStart, setVacStart] = useState("");
  const [vacEnd, setVacEnd] = useState("");
  const [addingVac, setAddingVac] = useState(false);

  // Year data
  const [yearEntries, setYearEntries] = useState([]);
  const [timeOffRequests, setTimeOffRequests] = useState([]);
  const [expandedMonth, setExpandedMonth] = useState(null);

  const months = Array.from({ length: 12 }, (_, i) => {
    const m = String(i + 1).padStart(2, "0");
    return { key: `${year}-${m}`, label: new Date(year, i).toLocaleDateString("de-DE", { month: "long" }), idx: i };
  }).reverse();

  const loadHrData = useCallback(async () => {
    try {
      const res = await api.get(`/employee/hr-data/${userId}?token=${token}`);
      setHrData(res.data);
      setOvertimeHours(String(res.data.overtime_hours || 0));
      setVacationTotal(String(res.data.vacation_days_total || 0));
    } catch {}
  }, [token, userId]);

  const loadVacationEntries = useCallback(async () => {
    try {
      const res = await api.get(`/employee/vacation/${userId}?token=${token}`);
      setVacationEntries(res.data || []);
    } catch {}
  }, [token, userId]);

  useEffect(() => { loadHrData(); }, [loadHrData]);
  useEffect(() => { loadVacationEntries(); }, [loadVacationEntries]);

  // Load ALL time entries for the year
  useEffect(() => {
    api.get(`/employee/time/entries?token=${token}&user_id=${userId}&date_from=${year}-01-01&date_to=${year}-12-31`)
      .then(r => setYearEntries(r.data || [])).catch(() => {});
  }, [token, userId, year]);

  // Load time-off requests for this user
  useEffect(() => {
    api.get(`/employee/time-off?token=${token}&user_id=${userId}`)
      .then(r => setTimeOffRequests(r.data || [])).catch(() => {});
  }, [token, userId]);

  useEffect(() => {
    api.get(`/chat/users?token=${token}`).then(r => {
      const u = (r.data || []).find(u => u.id === userId);
      if (u) setUserName(u.name);
    }).catch(() => {});
  }, [token, userId]);

  const saveHrData = async () => {
    setSaving(true);
    try {
      const res = await api.put(`/employee/hr-data/${userId}?token=${token}`, {
        overtime_hours: parseFloat(overtimeHours) || 0,
        vacation_days_total: parseInt(vacationTotal) || 0,
      });
      setHrData(res.data);
      toast.success("Gespeichert");
    } catch { toast.error("Fehler beim Speichern"); }
    setSaving(false);
  };

  const addVacation = async () => {
    if (!vacStart || !vacEnd) { toast.error("Bitte Start- und Enddatum wählen"); return; }
    if (vacEnd < vacStart) { toast.error("Enddatum muss nach Startdatum liegen"); return; }
    setAddingVac(true);
    try {
      await api.post(`/employee/vacation/${userId}?token=${token}`, { start_date: vacStart, end_date: vacEnd });
      toast.success("Urlaub eingetragen");
      setVacStart(""); setVacEnd("");
      loadVacationEntries(); loadHrData();
    } catch (e) { toast.error(e.response?.data?.detail || "Fehler"); }
    setAddingVac(false);
  };

  const deleteVacation = async (entryId) => {
    try {
      await api.delete(`/employee/vacation/${userId}/${entryId}?token=${token}`);
      toast.success("Urlaub gelöscht");
      loadVacationEntries(); loadHrData();
    } catch { toast.error("Fehler beim Löschen"); }
  };

  if (!isAdmin) { navigate("/hub"); return null; }

  const vacUsed = hrData?.vacation_days_used || 0;
  const vacTotal = parseInt(vacationTotal) || 0;
  const vacRemaining = vacTotal - vacUsed;

  // Group entries by month
  const entriesByMonth = {};
  yearEntries.forEach(e => {
    const m = e.clock_in?.substring(0, 7);
    if (!m) return;
    if (!entriesByMonth[m]) entriesByMonth[m] = [];
    entriesByMonth[m].push(e);
  });

  const getMonthStats = (monthKey) => {
    const prefix = monthKey;
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

  const fmtH = (mins) => { const h = Math.floor(mins / 60); const m = Math.round(mins % 60); return h > 0 ? `${h}h ${m}m` : m > 0 ? `${m}m` : ""; };
  const formatTime = (iso) => new Date(iso).toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" });

  return (
    <div className="min-h-screen bg-gray-50" data-testid="admin-zeit-detail-page">
      <header className="bg-white border-b border-gray-200 sticky top-0 z-10">
        <div className="max-w-5xl mx-auto px-4 py-3 flex items-center gap-3">
          <button onClick={() => navigate("/verwaltung/zeiterfassung")} className="text-gray-500 hover:text-gray-700" data-testid="back-btn">
            <ArrowLeft className="w-5 h-5" />
          </button>
          <User className="w-5 h-5 text-green-600" />
          <h1 className="text-lg font-semibold text-gray-900">{userName || "Mitarbeiter"}</h1>
          <span className="text-gray-300">/</span>
          <span className="text-sm text-gray-500">Arbeitszeit</span>
          <span className="text-sm text-gray-400 ml-auto">{year}</span>
        </div>
      </header>

      <div className="max-w-5xl mx-auto px-4 py-5 space-y-4">
        {/* HR Data + Summary */}
        <div className="bg-white rounded-xl border border-gray-200 p-4" data-testid="hr-data-section">
          <div className="flex flex-col lg:flex-row gap-4">
            <div className="flex-1 space-y-3">
              <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider">Stammdaten bearbeiten</p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="text-xs text-gray-500 mb-1 block">Überstunden (Std.)</label>
                  <Input type="number" step="0.5" value={overtimeHours} onChange={e => setOvertimeHours(e.target.value)} data-testid="input-overtime" />
                </div>
                <div>
                  <label className="text-xs text-gray-500 mb-1 block">Urlaubstage (Gesamt/Jahr)</label>
                  <Input type="number" value={vacationTotal} onChange={e => setVacationTotal(e.target.value)} data-testid="input-vacation-total" />
                </div>
              </div>
              <Button onClick={saveHrData} disabled={saving} size="sm" className="bg-green-600 hover:bg-green-700" data-testid="save-hr-btn">
                <Save className="w-3.5 h-3.5 mr-1.5" /> {saving ? "Speichern..." : "Speichern"}
              </Button>
            </div>
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 flex-shrink-0">
              <div className="flex items-center gap-2 bg-amber-50 rounded-lg px-3 py-2.5">
                <TrendingUp className="w-4 h-4 text-amber-600 flex-shrink-0" />
                <div>
                  <p className="text-[10px] font-medium text-amber-600 uppercase">Stundenkonto</p>
                  <p className="text-lg font-bold text-amber-800">{parseFloat(overtimeHours) || 0} <span className="text-xs font-normal text-amber-500">Std.</span></p>
                </div>
              </div>
              <div className="flex items-center gap-2 bg-sky-50 rounded-lg px-3 py-2.5">
                <Palmtree className="w-4 h-4 text-sky-600 flex-shrink-0" />
                <div>
                  <p className="text-[10px] font-medium text-sky-600 uppercase">Genehmigt</p>
                  <p className="text-lg font-bold text-sky-800">{vacUsed} <span className="text-xs font-normal text-sky-500">Tage</span></p>
                </div>
              </div>
              <div className={`flex items-center gap-2 rounded-lg px-3 py-2.5 ${vacRemaining < 0 ? "bg-red-50" : "bg-green-50"}`}>
                <Palmtree className={`w-4 h-4 flex-shrink-0 ${vacRemaining < 0 ? "text-red-600" : "text-green-600"}`} />
                <div>
                  <p className={`text-[10px] font-medium uppercase ${vacRemaining < 0 ? "text-red-600" : "text-green-600"}`}>Resturlaub</p>
                  <p className={`text-lg font-bold ${vacRemaining < 0 ? "text-red-800" : "text-green-800"}`}>{vacRemaining} <span className={`text-xs font-normal ${vacRemaining < 0 ? "text-red-500" : "text-green-500"}`}>Tage</span></p>
                </div>
              </div>
              <div className="flex items-center gap-2 bg-red-50 rounded-lg px-3 py-2.5">
                <ThermometerSun className="w-4 h-4 text-red-500 flex-shrink-0" />
                <div>
                  <p className="text-[10px] font-medium text-red-500 uppercase">Krankheit</p>
                  <p className="text-lg font-bold text-red-800">{sickDaysYear} <span className="text-xs font-normal text-red-400">Tage</span></p>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Vacation Entries */}
        <div className="bg-white rounded-xl border border-gray-200 p-4" data-testid="vacation-section">
          <div className="flex items-center gap-2 mb-3">
            <CalendarDays className="w-4 h-4 text-sky-600" />
            <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider">Genehmigte Urlaube</p>
          </div>
          <div className="flex flex-wrap items-end gap-3 mb-3 pb-3 border-b border-gray-100">
            <div>
              <label className="text-xs text-gray-500 mb-1 block">Von</label>
              <input type="date" value={vacStart} onChange={e => setVacStart(e.target.value)} className="border border-gray-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-sky-400" data-testid="vac-start" />
            </div>
            <div>
              <label className="text-xs text-gray-500 mb-1 block">Bis</label>
              <input type="date" value={vacEnd} onChange={e => setVacEnd(e.target.value)} className="border border-gray-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-sky-400" data-testid="vac-end" />
            </div>
            <Button onClick={addVacation} disabled={addingVac} size="sm" className="bg-sky-600 hover:bg-sky-700" data-testid="add-vacation-btn">
              <Plus className="w-3.5 h-3.5 mr-1" /> Eintragen
            </Button>
          </div>
          {vacationEntries.length === 0 ? (
            <p className="text-xs text-gray-400">Keine Urlaubseinträge vorhanden</p>
          ) : (
            <div className="space-y-1.5">
              {vacationEntries.map(v => (
                <div key={v.id} className="flex items-center gap-3 bg-sky-50 rounded-lg px-3 py-2 text-sm">
                  <CalendarDays className="w-4 h-4 text-sky-500 flex-shrink-0" />
                  <span className="text-gray-700 font-medium">{new Date(v.start_date + "T00:00").toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit", year: "numeric" })}</span>
                  <span className="text-gray-400">—</span>
                  <span className="text-gray-700 font-medium">{new Date(v.end_date + "T00:00").toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit", year: "numeric" })}</span>
                  <span className="text-sky-700 font-bold ml-auto">{v.days} Tage</span>
                  <button onClick={() => deleteVacation(v.id)} className="text-gray-400 hover:text-red-500"><Trash2 className="w-3.5 h-3.5" /></button>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Monthly Breakdown */}
        <div className="space-y-2">
          {months.filter(m => m.idx <= currentMonth).map(m => {
            const stats = getMonthStats(m.key);
            const isOpen = expandedMonth === m.key;

            return (
              <div key={m.key} className="bg-white rounded-xl border border-gray-200 overflow-hidden" data-testid={`month-${m.key}`}>
                <button onClick={() => setExpandedMonth(isOpen ? null : m.key)} className="w-full text-left px-4 py-3 flex items-center gap-3 hover:bg-gray-50 transition-colors">
                  <CalendarDays className="w-4 h-4 text-gray-400 flex-shrink-0" />
                  <span className="text-sm font-semibold text-gray-900">{m.label}</span>
                  <div className="flex items-center gap-2 ml-auto">
                    {stats.totalMins > 0 && <span className="text-xs font-bold text-gray-700 bg-gray-100 px-2 py-0.5 rounded"><Clock className="w-3 h-3 inline mr-0.5 -mt-0.5" />{fmtH(stats.totalMins)}</span>}
                    {stats.vacDays > 0 && <span className="text-xs font-bold text-sky-700 bg-sky-50 px-2 py-0.5 rounded"><Palmtree className="w-3 h-3 inline mr-0.5 -mt-0.5" />{stats.vacDays}T</span>}
                    {stats.sickDays > 0 && <span className="text-xs font-bold text-red-600 bg-red-50 px-2 py-0.5 rounded"><ThermometerSun className="w-3 h-3 inline mr-0.5 -mt-0.5" />{stats.sickDays}T</span>}
                    {isOpen ? <ChevronUp className="w-4 h-4 text-gray-400" /> : <ChevronDown className="w-4 h-4 text-gray-400" />}
                  </div>
                </button>
                {isOpen && (
                  <div className="border-t border-gray-100 divide-y divide-gray-50">
                    {stats.vacs.map(v => (
                      <div key={v.id} className="px-4 py-2.5 flex items-center gap-3 bg-sky-50/50">
                        <Palmtree className="w-3.5 h-3.5 text-sky-500 flex-shrink-0" />
                        <span className="text-xs font-semibold text-sky-700">Urlaub</span>
                        <span className="text-xs text-sky-600">{new Date(v.start_date + "T00:00").toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit" })} — {new Date(v.end_date + "T00:00").toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit" })}</span>
                        <span className="text-xs font-bold text-sky-700 ml-auto">{v.days} Tage</span>
                      </div>
                    ))}
                    {stats.sicks.map(r => (
                      <div key={r.id} className="px-4 py-2.5 flex items-center gap-3 bg-red-50/50">
                        <ThermometerSun className="w-3.5 h-3.5 text-red-400 flex-shrink-0" />
                        <span className="text-xs font-semibold text-red-600">Krank</span>
                        <span className="text-xs text-red-500">{new Date(r.start_date + "T00:00").toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit" })}{r.end_date !== r.start_date && ` — ${new Date(r.end_date + "T00:00").toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit" })}`}</span>
                        <span className="text-xs font-bold text-red-600 ml-auto">{r.days} Tage</span>
                      </div>
                    ))}
                    {stats.offs.map(r => (
                      <div key={r.id} className="px-4 py-2.5 flex items-center gap-3 bg-amber-50/50">
                        <TrendingUp className="w-3.5 h-3.5 text-amber-500 flex-shrink-0" />
                        <span className="text-xs font-semibold text-amber-700">Überstundenabbau</span>
                        <span className="text-xs text-amber-600">{new Date(r.start_date + "T00:00").toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit" })}</span>
                      </div>
                    ))}
                    {stats.entries.map(e => (
                      <div key={e.id} className="px-4 py-2.5 flex items-center gap-3 text-xs">
                        <Clock className="w-3.5 h-3.5 text-gray-400 flex-shrink-0" />
                        <span className="font-medium text-gray-700 w-24 flex-shrink-0">{new Date(e.clock_in).toLocaleDateString("de-DE", { weekday: "short", day: "2-digit", month: "2-digit" })}</span>
                        <span className="text-green-600 font-medium">{formatTime(e.clock_in)}</span>
                        <span className="text-gray-300">—</span>
                        <span className={`font-medium ${e.clock_out ? "text-red-500" : "text-amber-500"}`}>{e.clock_out ? formatTime(e.clock_out) : "Aktiv"}</span>
                        <span className="font-bold text-gray-900 ml-auto">{e.duration_minutes > 0 ? fmtH(e.duration_minutes) : "—"}</span>
                        {e.clock_in_lat && <a href={`https://www.google.com/maps?q=${e.clock_in_lat},${e.clock_in_lng}`} target="_blank" rel="noreferrer" className="text-gray-400 hover:text-fuchsia-600" onClick={ev => ev.stopPropagation()}><MapPin className="w-3 h-3" /></a>}
                        {e.clock_out_lat && <a href={`https://www.google.com/maps?q=${e.clock_out_lat},${e.clock_out_lng}`} target="_blank" rel="noreferrer" className="text-gray-400 hover:text-green-600" onClick={ev => ev.stopPropagation()}><MapPin className="w-3 h-3" /></a>}
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
