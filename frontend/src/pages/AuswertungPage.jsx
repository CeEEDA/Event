import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import api from "../lib/api";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import {
  ArrowLeft, BarChart3, AlertTriangle, Check, Clock, Search,
  User, FileText, Filter, ChevronDown, ChevronUp, MapPin,
} from "lucide-react";

export default function AuswertungPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const token = localStorage.getItem("token");
  const isAdmin = user?.role === "admin";

  const [activeTab, setActiveTab] = useState("documents");

  const [report, setReport] = useState([]);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [groupBy, setGroupBy] = useState("status");

  const loadReport = useCallback(async () => {
    try {
      const res = await api.get(`/employee/report/expiry?token=${token}`);
      setReport(res.data);
    } catch {}
  }, [token]);

  useEffect(() => { loadReport(); }, [loadReport]);

  // Time tracking report
  const [timeReport, setTimeReport] = useState([]);
  const [timeMonth, setTimeMonth] = useState(() => {
    const now = new Date();
    return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
  });
  const [expandedTimeUser, setExpandedTimeUser] = useState(null);

  const loadTimeReport = useCallback(async () => {
    const [y, m] = timeMonth.split("-");
    const from = `${y}-${m}-01`;
    const lastDay = new Date(parseInt(y), parseInt(m), 0).getDate();
    const to = `${y}-${m}-${String(lastDay).padStart(2, "0")}`;
    try {
      const res = await api.get(`/employee/time/report?token=${token}&date_from=${from}&date_to=${to}`);
      setTimeReport(res.data);
    } catch {}
  }, [token, timeMonth]);

  useEffect(() => { if (activeTab === "time") loadTimeReport(); }, [activeTab, loadTimeReport]);

  if (!isAdmin) { navigate("/hub"); return null; }

  const filtered = report.filter(d => {
    if (search) {
      const q = search.toLowerCase();
      if (!d.user_name?.toLowerCase().includes(q) && !d.doc_label?.toLowerCase().includes(q)) return false;
    }
    if (statusFilter === "expired") return d.status === "expired";
    if (statusFilter === "critical") return d.status === "critical" || d.status === "expired";
    if (statusFilter === "warning") return d.status === "warning" || d.status === "critical" || d.status === "expired";
    if (statusFilter === "ok") return d.status === "ok";
    if (statusFilter === "no_date") return d.status === "no_date";
    return true;
  });

  const expiredCount = report.filter(d => d.status === "expired").length;
  const criticalCount = report.filter(d => d.status === "critical").length;
  const warningCount = report.filter(d => d.status === "warning").length;
  const okCount = report.filter(d => d.status === "ok").length;

  const statusConfig = {
    expired: { label: "Abgelaufen", cls: "text-red-700 bg-red-50 border-red-200", dot: "bg-red-500", icon: AlertTriangle },
    critical: { label: "< 30 Tage", cls: "text-red-600 bg-red-50 border-red-200", dot: "bg-red-400", icon: AlertTriangle },
    warning: { label: "< 60 Tage", cls: "text-amber-700 bg-amber-50 border-amber-200", dot: "bg-amber-400", icon: Clock },
    ok: { label: "Gültig", cls: "text-green-700 bg-green-50 border-green-200", dot: "bg-green-500", icon: Check },
    no_date: { label: "Kein Datum", cls: "text-gray-500 bg-gray-50 border-gray-200", dot: "bg-gray-400", icon: FileText },
  };

  // Group by employee
  const grouped = {};
  filtered.forEach(d => {
    const key = groupBy === "employee" ? d.user_id : d.status;
    if (!grouped[key]) grouped[key] = { label: groupBy === "employee" ? d.user_name : statusConfig[d.status]?.label || d.status, items: [] };
    grouped[key].items.push(d);
  });

  // Sort groups: expired first
  const statusOrder = ["expired", "critical", "warning", "ok", "no_date"];
  const sortedGroups = groupBy === "status"
    ? statusOrder.filter(s => grouped[s]).map(s => ({ key: s, ...grouped[s] }))
    : Object.entries(grouped).sort((a, b) => a[1].label.localeCompare(b[1].label)).map(([k, v]) => ({ key: k, ...v }));

  return (
    <div className="min-h-screen bg-gray-50" data-testid="auswertung-page">
      <header className="bg-white border-b border-gray-200 sticky top-0 z-10">
        <div className="max-w-5xl mx-auto px-4 py-3 flex items-center gap-3">
          <button onClick={() => navigate("/verwaltung")} className="text-gray-500 hover:text-gray-700" data-testid="back-btn">
            <ArrowLeft className="w-5 h-5" />
          </button>
          <BarChart3 className="w-5 h-5 text-fuchsia-600" />
          <h1 className="text-lg font-semibold text-gray-900">Auswertung</h1>
        </div>
      </header>

      <div className="max-w-5xl mx-auto px-4 py-5 space-y-5">
        {/* Tab Switch */}
        <div className="flex gap-1 bg-gray-100 rounded-lg p-1">
          <button onClick={() => setActiveTab("documents")} className={`flex-1 py-2 text-sm font-medium rounded-md transition-colors flex items-center justify-center gap-1.5 ${activeTab === "documents" ? "bg-white text-fuchsia-700 shadow-sm" : "text-gray-500 hover:text-gray-700"}`} data-testid="tab-documents">
            <FileText className="w-3.5 h-3.5" /> Dokumente
          </button>
          <button onClick={() => setActiveTab("time")} className={`flex-1 py-2 text-sm font-medium rounded-md transition-colors flex items-center justify-center gap-1.5 ${activeTab === "time" ? "bg-white text-fuchsia-700 shadow-sm" : "text-gray-500 hover:text-gray-700"}`} data-testid="tab-time">
            <Clock className="w-3.5 h-3.5" /> Arbeitszeiten
          </button>
        </div>

        {activeTab === "documents" && (
          <>
        {/* Stats Cards */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <button onClick={() => setStatusFilter(statusFilter === "expired" ? "all" : "expired")} className={`rounded-xl border p-4 text-left transition-all ${statusFilter === "expired" ? "ring-2 ring-red-400" : ""} border-red-200 bg-red-50 hover:shadow-md`} data-testid="stat-expired">
            <p className="text-2xl font-bold text-red-600">{expiredCount}</p>
            <p className="text-xs text-red-500 font-medium">Abgelaufen</p>
          </button>
          <button onClick={() => setStatusFilter(statusFilter === "critical" ? "all" : "critical")} className={`rounded-xl border p-4 text-left transition-all ${statusFilter === "critical" ? "ring-2 ring-orange-400" : ""} border-orange-200 bg-orange-50 hover:shadow-md`} data-testid="stat-critical">
            <p className="text-2xl font-bold text-orange-600">{criticalCount}</p>
            <p className="text-xs text-orange-500 font-medium">Kritisch (&lt; 30 Tage)</p>
          </button>
          <button onClick={() => setStatusFilter(statusFilter === "warning" ? "all" : "warning")} className={`rounded-xl border p-4 text-left transition-all ${statusFilter === "warning" ? "ring-2 ring-amber-400" : ""} border-amber-200 bg-amber-50 hover:shadow-md`} data-testid="stat-warning">
            <p className="text-2xl font-bold text-amber-600">{warningCount}</p>
            <p className="text-xs text-amber-500 font-medium">Warnung (&lt; 60 Tage)</p>
          </button>
          <button onClick={() => setStatusFilter(statusFilter === "ok" ? "all" : "ok")} className={`rounded-xl border p-4 text-left transition-all ${statusFilter === "ok" ? "ring-2 ring-green-400" : ""} border-green-200 bg-green-50 hover:shadow-md`} data-testid="stat-ok">
            <p className="text-2xl font-bold text-green-600">{okCount}</p>
            <p className="text-xs text-green-500 font-medium">Gültig</p>
          </button>
        </div>

        {/* Controls */}
        <div className="flex flex-col sm:flex-row gap-3">
          <div className="relative flex-1">
            <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
            <Input value={search} onChange={e => setSearch(e.target.value)} placeholder="Mitarbeiter oder Dokument suchen..." className="pl-10" data-testid="report-search" />
          </div>
          <div className="flex gap-2">
            <Button variant={groupBy === "status" ? "default" : "outline"} size="sm" onClick={() => setGroupBy("status")} className={groupBy === "status" ? "bg-fuchsia-600 hover:bg-fuchsia-700" : ""} data-testid="group-by-status">
              <Filter className="w-3.5 h-3.5 mr-1.5" /> Nach Status
            </Button>
            <Button variant={groupBy === "employee" ? "default" : "outline"} size="sm" onClick={() => setGroupBy("employee")} className={groupBy === "employee" ? "bg-fuchsia-600 hover:bg-fuchsia-700" : ""} data-testid="group-by-employee">
              <User className="w-3.5 h-3.5 mr-1.5" /> Nach Mitarbeiter
            </Button>
            {statusFilter !== "all" && (
              <Button variant="ghost" size="sm" onClick={() => setStatusFilter("all")} className="text-gray-500" data-testid="clear-filter">
                Filter zurücksetzen
              </Button>
            )}
          </div>
        </div>

        {/* Report Table */}
        {sortedGroups.length === 0 ? (
          <div className="bg-white rounded-xl border border-gray-200 p-12 text-center">
            <Check className="w-10 h-10 text-green-400 mx-auto mb-3" />
            <p className="text-gray-500">Keine Einträge gefunden</p>
          </div>
        ) : (
          <div className="space-y-4">
            {sortedGroups.map(group => {
              const cfg = statusConfig[group.key] || {};
              return (
                <div key={group.key} className="bg-white rounded-xl border border-gray-200 overflow-hidden" data-testid={`report-group-${group.key}`}>
                  <div className={`px-4 py-2.5 flex items-center gap-2 border-b ${cfg.cls || "text-gray-700 bg-gray-50 border-gray-200"}`}>
                    {cfg.icon && <cfg.icon className="w-4 h-4" />}
                    <span className="text-sm font-semibold">{group.label}</span>
                    <span className="text-xs opacity-70 ml-auto">{group.items.length} Dokument{group.items.length !== 1 ? "e" : ""}</span>
                  </div>
                  <div className="divide-y divide-gray-100">
                    {group.items.map(d => {
                      const sc = statusConfig[d.status] || {};
                      return (
                        <div key={d.doc_id} className="px-4 py-2.5 flex items-center gap-3 hover:bg-gray-50" data-testid={`report-row-${d.doc_id}`}>
                          <div className={`w-2 h-2 rounded-full flex-shrink-0 ${sc.dot || "bg-gray-400"}`} />
                          <div className="flex-1 min-w-0 grid grid-cols-1 sm:grid-cols-4 gap-1 sm:gap-3 items-center">
                            <span className="text-sm font-medium text-gray-900 truncate flex items-center gap-1.5">
                              <User className="w-3 h-3 text-gray-400 flex-shrink-0" /> {d.user_name}
                            </span>
                            <span className="text-xs text-gray-600 truncate">{d.doc_label}</span>
                            <span className="text-xs font-mono text-gray-700">{d.expiry_date || "—"}</span>
                            <span className={`text-xs font-medium ${d.status === "expired" ? "text-red-600" : d.status === "critical" ? "text-red-500" : d.status === "warning" ? "text-amber-600" : d.status === "ok" ? "text-green-600" : "text-gray-400"}`}>
                              {d.days_left !== null && d.days_left !== undefined
                                ? d.days_left < 0
                                  ? `${Math.abs(d.days_left)} Tage überfällig`
                                  : `${d.days_left} Tage verbleibend`
                                : "Kein Ablaufdatum"}
                            </span>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              );
            })}
          </div>
        )}
          </>
        )}

        {/* Time Tracking Tab */}
        {activeTab === "time" && (
          <>
            {/* Month Selector */}
            <div className="flex items-center justify-between">
              <input type="month" value={timeMonth} onChange={e => setTimeMonth(e.target.value)} className="border border-gray-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-fuchsia-400" data-testid="time-month-picker" />
              <div className="text-right">
                <p className="text-xs text-gray-500">{timeReport.length} Mitarbeiter mit Einträgen</p>
              </div>
            </div>

            {/* Employee Time Cards */}
            {timeReport.length === 0 ? (
              <div className="bg-white rounded-xl border border-gray-200 p-8 text-center">
                <Clock className="w-8 h-8 text-gray-300 mx-auto mb-2" />
                <p className="text-sm text-gray-400">Keine Zeiteinträge in diesem Monat</p>
              </div>
            ) : (
              <div className="space-y-3">
                {timeReport.map(emp => {
                  const hours = Math.floor(emp.total_minutes / 60);
                  const mins = Math.round(emp.total_minutes % 60);
                  const isOpen = expandedTimeUser === emp.user_id;
                  return (
                    <div key={emp.user_id} className="bg-white rounded-xl border border-gray-200 overflow-hidden" data-testid={`time-user-${emp.user_id}`}>
                      <button onClick={() => setExpandedTimeUser(isOpen ? null : emp.user_id)} className="w-full text-left px-4 py-3 flex items-center gap-3 hover:bg-gray-50">
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
                          {emp.entries.map(e => (
                            <div key={e.id} className="px-4 py-2.5 flex items-center gap-3 text-xs" data-testid={`time-entry-${e.id}`}>
                              <span className="font-medium text-gray-700 w-24">
                                {new Date(e.clock_in).toLocaleDateString("de-DE", { weekday: "short", day: "2-digit", month: "2-digit" })}
                              </span>
                              <span className="text-green-600">{new Date(e.clock_in).toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" })}</span>
                              <span className="text-gray-400">—</span>
                              <span className="text-red-500">{e.clock_out ? new Date(e.clock_out).toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" }) : "Aktiv"}</span>
                              <span className="font-semibold text-gray-900 ml-auto">{e.duration_minutes ? `${Math.floor(e.duration_minutes / 60)}h ${Math.round(e.duration_minutes % 60)}m` : "—"}</span>
                              {e.clock_in_lat && (
                                <a href={`https://www.google.com/maps?q=${e.clock_in_lat},${e.clock_in_lng}`} target="_blank" rel="noreferrer" className="text-gray-400 hover:text-fuchsia-600" title="Standort Ein">
                                  <MapPin className="w-3 h-3" />
                                </a>
                              )}
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
        )}
      </div>
    </div>
  );
}
