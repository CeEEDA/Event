import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import api from "../lib/api";
import {
  ArrowLeft, Clock, User, ChevronRight, Search, Palmtree, ThermometerSun,
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
  const [presence, setPresence] = useState([]);
  const [allEmployees, setAllEmployees] = useState([]);
  const [timeOffByUser, setTimeOffByUser] = useState({});
  const [vacByUser, setVacByUser] = useState({});

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

  // Load presence (who is currently clocked in)
  const loadPresence = useCallback(async () => {
    try {
      const res = await api.get(`/employee/time/presence?token=${token}`);
      setPresence(res.data || []);
    } catch {}
  }, [token]);

  useEffect(() => {
    loadPresence();
    const iv = setInterval(loadPresence, 15000);
    return () => clearInterval(iv);
  }, [loadPresence]);

  // Load all employees (mitarbeiter + admin)
  useEffect(() => {
    api.get(`/chat/users?token=${token}`).then(r => {
      const staff = (r.data || []).filter(u => u.role === "mitarbeiter" || u.role === "admin");
      setAllEmployees(staff);
    }).catch(() => {});
  }, [token]);

  // Load time-off requests for all users (admin)
  useEffect(() => {
    api.get(`/employee/time-off?token=${token}`).then(r => {
      const byUser = {};
      (r.data || []).forEach(req => {
        if (!byUser[req.user_id]) byUser[req.user_id] = [];
        byUser[req.user_id].push(req);
      });
      setTimeOffByUser(byUser);
    }).catch(() => {});
  }, [token]);

  // Load vacation entries for all users
  useEffect(() => {
    allEmployees.forEach(emp => {
      api.get(`/employee/vacation/${emp.id}?token=${token}`).then(r => {
        setVacByUser(prev => ({ ...prev, [emp.id]: r.data || [] }));
      }).catch(() => {});
    });
  }, [token, allEmployees]);

  if (!isAdmin) { navigate("/hub"); return null; }

  const filtered = timeReport.filter(emp => {
    if (!search.trim()) return true;
    return emp.user_name?.toLowerCase().includes(search.toLowerCase());
  });

  // Add employees that have vacation/sick but no time entries
  const [y, mo] = month.split("-");
  const prefix = `${y}-${mo}`;
  const reportUserIds = new Set(filtered.map(e => e.user_id));
  const extraEmployees = allEmployees.filter(emp => {
    if (reportUserIds.has(emp.id)) return false;
    const hasVac = (vacByUser[emp.id] || []).some(v => v.start_date?.startsWith(prefix) || v.end_date?.startsWith(prefix));
    const hasSick = (timeOffByUser[emp.id] || []).some(r => r.type === "krank" && r.status === "approved" && (r.start_date?.startsWith(prefix) || r.end_date?.startsWith(prefix)));
    if (!hasVac && !hasSick) return false;
    if (search.trim() && !emp.name?.toLowerCase().includes(search.toLowerCase())) return false;
    return true;
  }).map(emp => ({ user_id: emp.id, user_name: emp.name, total_minutes: 0, entries: [] }));
  const allFiltered = [...filtered, ...extraEmployees];

  const totalAllMinutes = allFiltered.reduce((s, e) => s + (e.total_minutes || 0), 0);
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
          <h1 className="text-lg font-semibold text-gray-900">Mitarbeiterverwaltung</h1>
        </div>
      </header>

      <div className="max-w-5xl mx-auto px-4 py-5 space-y-4">
        {/* Anwesenheits-Übersicht */}
        <div className="bg-white rounded-xl border border-gray-200 px-4 py-3" data-testid="presence-overview">
          <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider mb-2">Anwesenheit</p>
          <div className="flex flex-wrap gap-3">
            {allEmployees.map(emp => {
              const presenceEntry = presence.find(p => p.user_id === emp.id);
              const isPresent = !!presenceEntry?.clocked_in;
              return (
                <div key={emp.id} className="flex items-center gap-1.5" data-testid={`presence-${emp.id}`}>
                  <div className={`w-2 h-2 rounded-full flex-shrink-0 ${isPresent ? "bg-green-500" : "bg-gray-300"}`} />
                  <span className={`text-xs font-medium ${isPresent ? "text-gray-900" : "text-gray-400"}`}>{emp.name}</span>
                  {isPresent && presenceEntry?.clock_in && (
                    <span className="text-[10px] text-green-600">
                      seit {new Date(presenceEntry.clock_in).toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" })}
                    </span>
                  )}
                </div>
              );
            })}
            {allEmployees.length === 0 && <span className="text-xs text-gray-400">Laden...</span>}
          </div>
        </div>

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
            <p className="text-xs text-gray-500">{allFiltered.length} Mitarbeiter &middot; Gesamt: <span className="font-bold text-gray-900">{totalH}h {totalM}m</span></p>
          </div>
        </div>

        {/* Employee Cards */}
        {allFiltered.length === 0 ? (
          <div className="bg-white rounded-xl border border-gray-200 p-8 text-center">
            <Clock className="w-8 h-8 text-gray-300 mx-auto mb-2" />
            <p className="text-sm text-gray-400">Keine Zeiteinträge in diesem Monat</p>
          </div>
        ) : (
          <div className="space-y-3">
            {allFiltered.map(emp => {
              const hours = Math.floor(emp.total_minutes / 60);
              const mins = Math.round(emp.total_minutes % 60);
              const [y, m] = month.split("-");
              const prefix = `${y}-${m}`;
              const empVacs = (vacByUser[emp.user_id] || []).filter(v => v.start_date?.startsWith(prefix) || v.end_date?.startsWith(prefix));
              const vacDays = empVacs.reduce((s, v) => s + (v.days || 0), 0);
              const empSicks = (timeOffByUser[emp.user_id] || []).filter(r => r.type === "krank" && r.status === "approved" && (r.start_date?.startsWith(prefix) || r.end_date?.startsWith(prefix)));
              const sickDays = empSicks.reduce((s, r) => s + (r.days || 0), 0);
              return (
                <div key={emp.user_id} className="bg-white rounded-xl border border-gray-200 overflow-hidden" data-testid={`time-user-${emp.user_id}`}>
                  <button
                    onClick={() => navigate(`/verwaltung/zeiterfassung/${emp.user_id}`)}
                    className="w-full text-left px-4 py-3 flex items-center gap-3 hover:bg-gray-50 transition-colors"
                  >
                    <User className="w-5 h-5 text-gray-400 flex-shrink-0" />
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-gray-900">{emp.user_name}</p>
                      <p className="text-xs text-gray-500">{emp.entries.length} Einträge</p>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-bold text-gray-700 bg-gray-100 px-2 py-0.5 rounded">
                        <Clock className="w-3 h-3 inline mr-0.5 -mt-0.5" />{hours}h {mins}m
                      </span>
                      {vacDays > 0 && (
                        <span className="text-xs font-bold text-sky-700 bg-sky-50 px-2 py-0.5 rounded">
                          <Palmtree className="w-3 h-3 inline mr-0.5 -mt-0.5" />{vacDays}T
                        </span>
                      )}
                      {sickDays > 0 && (
                        <span className="text-xs font-bold text-red-600 bg-red-50 px-2 py-0.5 rounded">
                          <ThermometerSun className="w-3 h-3 inline mr-0.5 -mt-0.5" />{sickDays}T
                        </span>
                      )}
                    </div>
                    <ChevronRight className="w-4 h-4 text-gray-400" />
                  </button>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
