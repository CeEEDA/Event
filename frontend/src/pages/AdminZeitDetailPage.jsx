import { useState, useEffect, useCallback } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import api from "../lib/api";
import { toast } from "sonner";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { ArrowLeft, Clock, User, MapPin, Save, Palmtree, TrendingUp } from "lucide-react";

export default function AdminZeitDetailPage() {
  const { user } = useAuth();
  const { userId } = useParams();
  const navigate = useNavigate();
  const token = localStorage.getItem("token");
  const isAdmin = user?.role === "admin";

  const [entries, setEntries] = useState([]);
  const [userName, setUserName] = useState("");
  const [month, setMonth] = useState(() => {
    const now = new Date();
    return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
  });

  // HR Data
  const [overtimeHours, setOvertimeHours] = useState("");
  const [vacationTotal, setVacationTotal] = useState("");
  const [vacationUsed, setVacationUsed] = useState("");
  const [hrData, setHrData] = useState(null);
  const [saving, setSaving] = useState(false);

  const loadEntries = useCallback(async () => {
    const [y, m] = month.split("-");
    const from = `${y}-${m}-01`;
    const lastDay = new Date(parseInt(y), parseInt(m), 0).getDate();
    const to = `${y}-${m}-${String(lastDay).padStart(2, "0")}`;
    try {
      const res = await api.get(`/employee/time/entries?token=${token}&user_id=${userId}&date_from=${from}&date_to=${to}`);
      setEntries(res.data || []);
    } catch {}
  }, [token, userId, month]);

  const loadHrData = useCallback(async () => {
    try {
      const res = await api.get(`/employee/hr-data/${userId}?token=${token}`);
      setHrData(res.data);
      setOvertimeHours(String(res.data.overtime_hours || 0));
      setVacationTotal(String(res.data.vacation_days_total || 0));
      setVacationUsed(String(res.data.vacation_days_used || 0));
    } catch {}
  }, [token, userId]);

  useEffect(() => { loadEntries(); }, [loadEntries]);
  useEffect(() => { loadHrData(); }, [loadHrData]);

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
        vacation_days_used: parseInt(vacationUsed) || 0,
      });
      setHrData(res.data);
      toast.success("Gespeichert");
    } catch {
      toast.error("Fehler beim Speichern");
    }
    setSaving(false);
  };

  if (!isAdmin) { navigate("/hub"); return null; }

  const completed = entries.filter(e => e.clock_out);
  const totalMinutes = completed.reduce((s, e) => s + (e.duration_minutes || 0), 0);
  const totalH = Math.floor(totalMinutes / 60);
  const totalM = Math.round(totalMinutes % 60);

  const vacationRemaining = (parseInt(vacationTotal) || 0) - (parseInt(vacationUsed) || 0);

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
        </div>
      </header>

      <div className="max-w-5xl mx-auto px-4 py-5 space-y-4">
        {/* HR Data Section */}
        <div className="bg-white rounded-xl border border-gray-200 p-4" data-testid="hr-data-section">
          <div className="flex flex-col sm:flex-row gap-4">
            {/* Editable Fields */}
            <div className="flex-1 space-y-3">
              <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider">Stammdaten bearbeiten</p>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div>
                  <label className="text-xs text-gray-500 mb-1 block">Überstunden (Std.)</label>
                  <Input
                    type="number"
                    step="0.5"
                    value={overtimeHours}
                    onChange={e => setOvertimeHours(e.target.value)}
                    data-testid="input-overtime"
                  />
                </div>
                <div>
                  <label className="text-xs text-gray-500 mb-1 block">Urlaubstage (Gesamt/Jahr)</label>
                  <Input
                    type="number"
                    value={vacationTotal}
                    onChange={e => setVacationTotal(e.target.value)}
                    data-testid="input-vacation-total"
                  />
                </div>
                <div>
                  <label className="text-xs text-gray-500 mb-1 block">Genehmigter Urlaub (Tage)</label>
                  <Input
                    type="number"
                    value={vacationUsed}
                    onChange={e => setVacationUsed(e.target.value)}
                    data-testid="input-vacation-used"
                  />
                </div>
              </div>
              <Button onClick={saveHrData} disabled={saving} size="sm" className="bg-green-600 hover:bg-green-700" data-testid="save-hr-btn">
                <Save className="w-3.5 h-3.5 mr-1.5" /> {saving ? "Speichern..." : "Speichern"}
              </Button>
            </div>

            {/* Calculated Summary */}
            <div className="flex flex-row sm:flex-col gap-3 flex-shrink-0 sm:min-w-[180px]">
              <div className="flex items-center gap-3 bg-amber-50 rounded-lg px-3 py-2.5 flex-1" data-testid="summary-overtime">
                <div className="w-8 h-8 rounded-lg bg-amber-100 flex items-center justify-center flex-shrink-0">
                  <TrendingUp className="w-4 h-4 text-amber-600" />
                </div>
                <div>
                  <p className="text-[10px] font-medium text-amber-600 uppercase tracking-wider">Stundenkonto</p>
                  <p className="text-lg font-bold text-amber-800 leading-tight">{parseFloat(overtimeHours) || 0} <span className="text-xs font-normal text-amber-500">Std.</span></p>
                </div>
              </div>
              <div className="flex items-center gap-3 bg-sky-50 rounded-lg px-3 py-2.5 flex-1" data-testid="summary-vacation-used">
                <div className="w-8 h-8 rounded-lg bg-sky-100 flex items-center justify-center flex-shrink-0">
                  <Palmtree className="w-4 h-4 text-sky-600" />
                </div>
                <div>
                  <p className="text-[10px] font-medium text-sky-600 uppercase tracking-wider">Genehmigt</p>
                  <p className="text-lg font-bold text-sky-800 leading-tight">{parseInt(vacationUsed) || 0} <span className="text-xs font-normal text-sky-500">Tage</span></p>
                </div>
              </div>
              <div className={`flex items-center gap-3 rounded-lg px-3 py-2.5 flex-1 ${vacationRemaining < 0 ? "bg-red-50" : "bg-green-50"}`} data-testid="summary-vacation-remaining">
                <div className={`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 ${vacationRemaining < 0 ? "bg-red-100" : "bg-green-100"}`}>
                  <Palmtree className={`w-4 h-4 ${vacationRemaining < 0 ? "text-red-600" : "text-green-600"}`} />
                </div>
                <div>
                  <p className={`text-[10px] font-medium uppercase tracking-wider ${vacationRemaining < 0 ? "text-red-600" : "text-green-600"}`}>Resturlaub</p>
                  <p className={`text-lg font-bold leading-tight ${vacationRemaining < 0 ? "text-red-800" : "text-green-800"}`}>{vacationRemaining} <span className={`text-xs font-normal ${vacationRemaining < 0 ? "text-red-500" : "text-green-500"}`}>Tage</span></p>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Time Entries */}
        <div className="flex items-center justify-between">
          <input
            type="month"
            value={month}
            onChange={e => setMonth(e.target.value)}
            className="border border-gray-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-green-400"
            data-testid="detail-month-picker"
          />
          <div className="text-right">
            <p className="text-xs text-gray-500">{completed.length} Einträge</p>
            <p className="text-lg font-bold text-gray-900">{totalH}h {totalM}m</p>
          </div>
        </div>

        {completed.length === 0 ? (
          <div className="bg-white rounded-xl border border-gray-200 p-8 text-center">
            <Clock className="w-8 h-8 text-gray-300 mx-auto mb-2" />
            <p className="text-sm text-gray-400">Keine Einträge in diesem Monat</p>
          </div>
        ) : (
          <div className="bg-white rounded-xl border border-gray-200 divide-y divide-gray-100">
            {completed.map(e => {
              const cin = new Date(e.clock_in);
              const cout = new Date(e.clock_out);
              const dur = e.duration_minutes || 0;
              const dH = Math.floor(dur / 60);
              const dM = Math.round(dur % 60);
              return (
                <div key={e.id} className="px-4 py-3 flex items-center gap-4 text-sm" data-testid={`detail-entry-${e.id}`}>
                  <span className="font-medium text-gray-700 w-28 flex-shrink-0">
                    {cin.toLocaleDateString("de-DE", { weekday: "short", day: "2-digit", month: "2-digit", year: "numeric" })}
                  </span>
                  <span className="text-green-600 font-medium">
                    {cin.toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" })}
                  </span>
                  <span className="text-gray-400">—</span>
                  <span className="text-red-500 font-medium">
                    {cout.toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" })}
                  </span>
                  <span className="font-bold text-gray-900 ml-auto">{dH > 0 ? `${dH}h ${dM}m` : `${dM}m`}</span>
                  {e.clock_in_lat && (
                    <a href={`https://www.google.com/maps?q=${e.clock_in_lat},${e.clock_in_lng}`} target="_blank" rel="noreferrer" className="text-gray-400 hover:text-fuchsia-600" title="Einstempel-Standort" onClick={ev => ev.stopPropagation()}>
                      <MapPin className="w-3.5 h-3.5" />
                    </a>
                  )}
                  {e.clock_out_lat && (
                    <a href={`https://www.google.com/maps?q=${e.clock_out_lat},${e.clock_out_lng}`} target="_blank" rel="noreferrer" className="text-gray-400 hover:text-green-600" title="Ausstempel-Standort" onClick={ev => ev.stopPropagation()}>
                      <MapPin className="w-3.5 h-3.5" />
                    </a>
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
