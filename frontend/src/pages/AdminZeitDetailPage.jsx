import { useState, useEffect, useCallback } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import api from "../lib/api";
import { toast } from "sonner";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import {
  ArrowLeft, Clock, User, MapPin, Save, Palmtree, TrendingUp,
  Plus, Trash2, CalendarDays, ThermometerSun, ChevronDown, ChevronUp, CalendarOff, Archive, Briefcase,
  DollarSign, Download, Moon, Sun, StickyNote,
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
  const [archiveOpen, setArchiveOpen] = useState(null);

  // Work Schedule
  const WEEKDAYS = ["montag", "dienstag", "mittwoch", "donnerstag", "freitag", "samstag"];
  const WEEKDAY_LABELS = { montag: "Montag", dienstag: "Dienstag", mittwoch: "Mittwoch", donnerstag: "Donnerstag", freitag: "Freitag", samstag: "Samstag" };
  const [schedule, setSchedule] = useState({});
  const [savingSchedule, setSavingSchedule] = useState(false);
  const [hourlyWage, setHourlyWage] = useState("");
  const [surcharges, setSurcharges] = useState({ sunday: 50, holiday: 125, special_holiday: 150, night: 25 });
  const [payroll, setPayroll] = useState(null);
  const [payrollMonth, setPayrollMonth] = useState(() => {
    const now = new Date();
    return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
  });
  const [loadingPayroll, setLoadingPayroll] = useState(false);

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

  // Load work schedule
  const loadSchedule = useCallback(async () => {
    try {
      const res = await api.get(`/employee/work-schedule/${userId}?token=${token}`);
      setSchedule(res.data?.days || {});
      if (res.data?.hourly_wage) setHourlyWage(res.data.hourly_wage);
      if (res.data?.surcharges) setSurcharges(prev => ({ ...prev, ...res.data.surcharges }));
    } catch {}
  }, [token, userId]);
  useEffect(() => { loadSchedule(); }, [loadSchedule]);

  const updateDay = (day, field, value) => {
    setSchedule(prev => ({ ...prev, [day]: { ...(prev[day] || {}), [field]: value } }));
  };

  const calcDayHours = (day) => {
    const d = schedule[day];
    if (!d?.start || !d?.end) return null;
    const [sh, sm] = d.start.split(":").map(Number);
    const [eh, em] = d.end.split(":").map(Number);
    const totalMin = (eh * 60 + em) - (sh * 60 + sm) - (parseInt(d.break_min) || 0);
    return totalMin > 0 ? totalMin : 0;
  };

  const weeklyTotalMin = WEEKDAYS.reduce((sum, d) => sum + (calcDayHours(d) || 0), 0);

  const saveSchedule = async () => {
    setSavingSchedule(true);
    try {
      await api.put(`/employee/work-schedule/${userId}?token=${token}`, {
        days: schedule,
        hourly_wage: parseFloat(hourlyWage) || 0,
        surcharges,
      });
      toast.success("Regelarbeitszeit & Lohndaten gespeichert");
    } catch { toast.error("Fehler"); }
    setSavingSchedule(false);
  };

  const loadPayroll = useCallback(async () => {
    if (!payrollMonth) return;
    setLoadingPayroll(true);
    try {
      const res = await api.get(`/employee/payroll/${userId}?month=${payrollMonth}&token=${token}`);
      setPayroll(res.data);
    } catch { toast.error("Fehler beim Laden der Lohnabrechnung"); }
    setLoadingPayroll(false);
  }, [token, userId, payrollMonth]);

  const downloadCsv = async () => {
    const url = `${process.env.REACT_APP_BACKEND_URL}/api/employee/payroll/${userId}/csv?month=${payrollMonth}&token=${token}`;
    window.open(url, "_blank");
  };

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
          <div className="ml-auto flex items-center gap-2">
            <Button onClick={() => navigate(`/verwaltung/zeiterfassung/${userId}/notizen`)} size="sm" variant="outline" className="text-amber-700 border-amber-300 hover:bg-amber-50" data-testid="notes-btn">
              <StickyNote className="w-3.5 h-3.5 mr-1.5" /> Notizen
            </Button>
            <span className="text-sm text-gray-400">{year}</span>
          </div>
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

        {/* Regelarbeitszeit */}
        <div className="bg-white rounded-xl border border-gray-200 p-4" data-testid="work-schedule-section">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <Briefcase className="w-4 h-4 text-indigo-600" />
              <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider">Regelarbeitszeit</p>
            </div>
            <div className="text-xs text-gray-500">Woche: <span className="font-bold text-indigo-700">{Math.floor(weeklyTotalMin / 60)}h {weeklyTotalMin % 60 > 0 ? `${weeklyTotalMin % 60}m` : ""}</span></div>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-[10px] text-gray-400 uppercase tracking-wider">
                  <th className="text-left pb-2 pr-2 font-semibold w-28">Tag</th>
                  <th className="text-left pb-2 px-2 font-semibold">Beginn</th>
                  <th className="text-left pb-2 px-2 font-semibold">Ende</th>
                  <th className="text-left pb-2 px-2 font-semibold">Pause (Min.)</th>
                  <th className="text-right pb-2 pl-2 font-semibold">Netto</th>
                </tr>
              </thead>
              <tbody>
                {WEEKDAYS.map(day => {
                  const d = schedule[day] || {};
                  const mins = calcDayHours(day);
                  const h = mins !== null ? Math.floor(mins / 60) : null;
                  const m = mins !== null ? mins % 60 : null;
                  return (
                    <tr key={day} className="border-t border-gray-50">
                      <td className="py-1.5 pr-2 font-medium text-gray-700">{WEEKDAY_LABELS[day]}</td>
                      <td className="py-1.5 px-2">
                        <input type="time" value={d.start || ""} onChange={e => updateDay(day, "start", e.target.value)}
                          className="border border-gray-200 rounded px-2 py-1 text-sm w-24 focus:outline-none focus:ring-1 focus:ring-indigo-400" data-testid={`schedule-${day}-start`} />
                      </td>
                      <td className="py-1.5 px-2">
                        <input type="time" value={d.end || ""} onChange={e => updateDay(day, "end", e.target.value)}
                          className="border border-gray-200 rounded px-2 py-1 text-sm w-24 focus:outline-none focus:ring-1 focus:ring-indigo-400" data-testid={`schedule-${day}-end`} />
                      </td>
                      <td className="py-1.5 px-2">
                        <input type="number" min="0" step="5" value={d.break_min || ""} onChange={e => updateDay(day, "break_min", e.target.value)}
                          placeholder="0" className="border border-gray-200 rounded px-2 py-1 text-sm w-20 focus:outline-none focus:ring-1 focus:ring-indigo-400" data-testid={`schedule-${day}-break`} />
                      </td>
                      <td className="py-1.5 pl-2 text-right">
                        {mins !== null ? (
                          <span className="font-bold text-indigo-700">{h}h{m > 0 ? ` ${m}m` : ""}</span>
                        ) : (
                          <span className="text-gray-300">—</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          {/* Hourly wage & surcharges */}
          <div className="mt-4 pt-3 border-t border-gray-100 space-y-3">
            <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
              <div>
                <label className="text-[10px] text-gray-400 font-semibold uppercase block mb-1">Stundenlohn (EUR)</label>
                <input type="number" step="0.01" min="0" value={hourlyWage} onChange={e => setHourlyWage(e.target.value)}
                  className="border border-gray-200 rounded px-2 py-1.5 text-sm w-full focus:outline-none focus:ring-1 focus:ring-indigo-400" data-testid="hourly-wage" placeholder="0.00" />
              </div>
              <div>
                <label className="text-[10px] text-gray-400 font-semibold uppercase block mb-1">Sonntagszuschlag %</label>
                <input type="number" min="0" value={surcharges.sunday} onChange={e => setSurcharges(p => ({ ...p, sunday: parseFloat(e.target.value) || 0 }))}
                  className="border border-gray-200 rounded px-2 py-1.5 text-sm w-full focus:outline-none focus:ring-1 focus:ring-indigo-400" data-testid="surcharge-sunday" />
              </div>
              <div>
                <label className="text-[10px] text-gray-400 font-semibold uppercase block mb-1">Feiertagszuschlag %</label>
                <input type="number" min="0" value={surcharges.holiday} onChange={e => setSurcharges(p => ({ ...p, holiday: parseFloat(e.target.value) || 0 }))}
                  className="border border-gray-200 rounded px-2 py-1.5 text-sm w-full focus:outline-none focus:ring-1 focus:ring-indigo-400" data-testid="surcharge-holiday" />
              </div>
              <div>
                <label className="text-[10px] text-gray-400 font-semibold uppercase block mb-1">Bes. Feiertag %</label>
                <input type="number" min="0" value={surcharges.special_holiday} onChange={e => setSurcharges(p => ({ ...p, special_holiday: parseFloat(e.target.value) || 0 }))}
                  className="border border-gray-200 rounded px-2 py-1.5 text-sm w-full focus:outline-none focus:ring-1 focus:ring-indigo-400" data-testid="surcharge-special" />
              </div>
              <div>
                <label className="text-[10px] text-gray-400 font-semibold uppercase block mb-1">Nachtzuschlag %</label>
                <input type="number" min="0" value={surcharges.night} onChange={e => setSurcharges(p => ({ ...p, night: parseFloat(e.target.value) || 0 }))}
                  className="border border-gray-200 rounded px-2 py-1.5 text-sm w-full focus:outline-none focus:ring-1 focus:ring-indigo-400" data-testid="surcharge-night" />
              </div>
            </div>
            <p className="text-[10px] text-gray-400">Bes. Feiertage: 24.12. ab 14 Uhr, 25./26.12., 1. Mai | Nacht: 20:00–06:00 Uhr</p>
          </div>

          <div className="mt-3 pt-3 border-t border-gray-100">
            <Button onClick={saveSchedule} disabled={savingSchedule} size="sm" className="bg-indigo-600 hover:bg-indigo-700" data-testid="save-schedule-btn">
              <Save className="w-3.5 h-3.5 mr-1.5" /> {savingSchedule ? "Speichern..." : "Speichern"}
            </Button>
          </div>
        </div>

        {/* Payroll / Lohnabrechnung */}
        <div className="bg-white rounded-xl border border-gray-200 p-4" data-testid="payroll-section">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <DollarSign className="w-4 h-4 text-emerald-600" />
              <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider">Lohnabrechnung</p>
            </div>
            <div className="flex items-center gap-2">
              <input type="month" value={payrollMonth} onChange={e => setPayrollMonth(e.target.value)}
                className="border border-gray-200 rounded px-2 py-1 text-sm focus:outline-none focus:ring-1 focus:ring-emerald-400" data-testid="payroll-month" />
              <Button onClick={loadPayroll} size="sm" variant="outline" disabled={loadingPayroll} data-testid="calc-payroll-btn">
                {loadingPayroll ? "Berechne..." : "Berechnen"}
              </Button>
              {payroll && (
                <Button onClick={downloadCsv} size="sm" variant="outline" className="text-emerald-700 border-emerald-300 hover:bg-emerald-50" data-testid="download-csv-btn">
                  <Download className="w-3.5 h-3.5 mr-1" /> CSV
                </Button>
              )}
            </div>
          </div>
          {payroll && (
            <>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-[10px] text-gray-400 uppercase tracking-wider">
                      <th className="text-left pb-2 pr-1 font-semibold">Datum</th>
                      <th className="text-left pb-2 px-1 font-semibold">Tag</th>
                      <th className="text-left pb-2 px-1 font-semibold">Von</th>
                      <th className="text-left pb-2 px-1 font-semibold">Bis</th>
                      <th className="text-right pb-2 px-1 font-semibold">Std.</th>
                      <th className="text-left pb-2 px-1 font-semibold">Typ</th>
                      <th className="text-right pb-2 px-1 font-semibold">Nacht</th>
                      <th className="text-right pb-2 px-1 font-semibold">Grund</th>
                      <th className="text-right pb-2 px-1 font-semibold">Zuschlag</th>
                      <th className="text-right pb-2 pl-1 font-semibold">Gesamt</th>
                    </tr>
                  </thead>
                  <tbody>
                    {payroll.rows.map((r, i) => {
                      const typeColors = {
                        regular: "text-gray-500", sunday: "text-orange-600", holiday: "text-red-600", special: "text-red-700 font-bold",
                      };
                      const typeLabels = { regular: "Normal", sunday: "Sonntag", holiday: "Feiertag", special: "Bes. Feiertag" };
                      return (
                        <tr key={i} className="border-t border-gray-50">
                          <td className="py-1 pr-1 text-gray-700">{new Date(r.date + "T00:00").toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit" })}</td>
                          <td className="py-1 px-1 text-gray-500">{r.weekday}</td>
                          <td className="py-1 px-1">{r.clock_in}</td>
                          <td className="py-1 px-1">{r.clock_out}</td>
                          <td className="py-1 px-1 text-right font-medium">{r.total_hours.toFixed(1)}</td>
                          <td className={`py-1 px-1 text-[10px] font-semibold ${typeColors[r.surcharge_type]}`}>
                            {typeLabels[r.surcharge_type]}{r.holiday_name ? ` (${r.holiday_name})` : ""}
                          </td>
                          <td className="py-1 px-1 text-right">{r.night_min > 0 ? <span className="text-violet-600">{Math.round(r.night_min / 6) / 10}h</span> : "—"}</td>
                          <td className="py-1 px-1 text-right">{r.base_wage.toFixed(2)}€</td>
                          <td className="py-1 px-1 text-right text-orange-600">{(r.surcharge_wage + r.night_wage) > 0 ? `+${(r.surcharge_wage + r.night_wage).toFixed(2)}€` : "—"}</td>
                          <td className="py-1 pl-1 text-right font-bold">{r.total_wage.toFixed(2)}€</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
              <div className="mt-3 pt-3 border-t border-gray-200 grid grid-cols-2 sm:grid-cols-3 gap-2">
                <div className="bg-gray-50 rounded-lg p-2.5 text-center">
                  <p className="text-[10px] text-gray-400 uppercase font-semibold">Grundlohn</p>
                  <p className="text-lg font-bold text-gray-800">{payroll.totals.regular_wage?.toFixed(2)}€</p>
                </div>
                <div className="bg-orange-50 rounded-lg p-2.5 text-center">
                  <p className="text-[10px] text-orange-500 uppercase font-semibold">Zuschläge</p>
                  <p className="text-lg font-bold text-orange-700">
                    {((payroll.totals.sunday_wage || 0) + (payroll.totals.holiday_wage || 0) + (payroll.totals.special_wage || 0) + (payroll.totals.night_wage || 0)).toFixed(2)}€
                  </p>
                </div>
                <div className="bg-emerald-50 rounded-lg p-2.5 text-center">
                  <p className="text-[10px] text-emerald-500 uppercase font-semibold">Brutto Gesamt</p>
                  <p className="text-lg font-bold text-emerald-700">{payroll.total_gross?.toFixed(2)}€</p>
                </div>
              </div>
            </>
          )}
          {!payroll && !loadingPayroll && (
            <p className="text-sm text-gray-400 text-center py-4">Monat auswählen und "Berechnen" klicken</p>
          )}
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

        {/* Pending Time-Off Requests */}
        {timeOffRequests.filter(r => r.status === "pending").length > 0 && (
          <div className="bg-amber-50 rounded-xl border border-amber-200 p-4">
            <div className="flex items-center gap-2 mb-2">
              <CalendarOff className="w-4 h-4 text-amber-600" />
              <span className="text-[10px] font-semibold text-amber-600 uppercase tracking-wider">Offene Anträge</span>
            </div>
            {timeOffRequests.filter(r => r.status === "pending").map(r => (
              <div key={r.id} className="flex items-center gap-2 text-sm text-amber-800 py-0.5">
                <span className="font-medium">{r.type_label}</span>
                <span>{new Date(r.start_date + "T00:00").toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit" })}{r.end_date !== r.start_date && ` — ${new Date(r.end_date + "T00:00").toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit" })}`}</span>
                <span className="text-[10px] bg-amber-200 text-amber-800 px-1.5 py-0.5 rounded-full font-bold ml-auto">In Bearbeitung</span>
              </div>
            ))}
          </div>
        )}

        {/* Rejected / Withdrawn Time-Off Requests - current year only */}
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
                <div className="bg-gray-50 rounded-xl border border-gray-200 p-4">
                  <div className="flex items-center gap-2 mb-2">
                    <CalendarOff className="w-4 h-4 text-gray-400" />
                    <span className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider">Abgelehnt / Zurückgezogen ({currentYearStr})</span>
                  </div>
                  {currentYearItems.map(r => (
                    <div key={r.id} className="flex items-center gap-2 text-sm text-gray-500 py-0.5">
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
                  <div className="flex items-center gap-2 px-4 py-2.5">
                    <Archive className="w-4 h-4 text-gray-400" />
                    <span className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider">Archiv — Abgelehnt / Zurückgezogen</span>
                  </div>
                  {archiveYears.map(ay => {
                    const items = archiveItems.filter(r => r.start_date?.startsWith(ay));
                    const isOpen = archiveOpen === ay;
                    return (
                      <div key={ay} className="border-t border-gray-100">
                        <button onClick={() => setArchiveOpen(isOpen ? null : ay)} className="w-full text-left px-4 py-2.5 flex items-center gap-2 hover:bg-gray-50 transition-colors">
                          <span className="text-sm font-semibold text-gray-700">{ay}</span>
                          <span className="text-xs text-gray-400 ml-1">({items.length})</span>
                          <div className="ml-auto">{isOpen ? <ChevronUp className="w-4 h-4 text-gray-400" /> : <ChevronDown className="w-4 h-4 text-gray-400" />}</div>
                        </button>
                        {isOpen && (
                          <div className="px-4 pb-3 space-y-0.5">
                            {items.map(r => (
                              <div key={r.id} className="flex items-center gap-2 text-sm text-gray-500 py-0.5">
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
