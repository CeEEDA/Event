import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import api from "../lib/api";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { toast } from "sonner";
import {
  ArrowLeft, ChevronLeft, ChevronRight, CalendarDays, Users, Plus, X, Trash2,
  Check, Send, Palmtree, ThermometerSun, TrendingUp, Clock, Edit2, UserPlus,
} from "lucide-react";

const WEEKDAYS = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"];
const STANDARD_HOURS = 8;

function getWeekKey(date) {
  const d = new Date(date);
  d.setHours(0, 0, 0, 0);
  d.setDate(d.getDate() + 3 - ((d.getDay() + 6) % 7));
  const w1 = new Date(d.getFullYear(), 0, 4);
  const wk = 1 + Math.round(((d - w1) / 86400000 - 3 + ((w1.getDay() + 6) % 7)) / 7);
  return `${d.getFullYear()}-W${String(wk).padStart(2, "0")}`;
}

function getWeekDates(weekKey) {
  const [y, w] = weekKey.split("-W").map(Number);
  const jan4 = new Date(y, 0, 4);
  const monday = new Date(jan4);
  monday.setDate(jan4.getDate() - ((jan4.getDay() + 6) % 7) + (w - 1) * 7);
  return Array.from({ length: 7 }, (_, i) => {
    const d = new Date(monday);
    d.setDate(monday.getDate() + i);
    return d.toISOString().split("T")[0];
  });
}

function formatDateShort(dateStr) {
  const d = new Date(dateStr + "T00:00:00");
  return d.toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit" });
}

function timeDiffHours(start, end) {
  if (!start || !end) return STANDARD_HOURS;
  const [sh, sm] = start.split(":").map(Number);
  const [eh, em] = end.split(":").map(Number);
  return Math.max(0, (eh * 60 + em - sh * 60 - sm) / 60);
}

export default function EinsatzplanungPage() {
  const navigate = useNavigate();
  const token = localStorage.getItem("token");
  const [weekKey, setWeekKey] = useState(() => getWeekKey(new Date()));
  const [users, setUsers] = useState([]);
  const [assignments, setAssignments] = useState([]);
  const [absences, setAbsences] = useState([]);
  const [released, setReleased] = useState(false);
  const [orders, setOrders] = useState([]);
  const [selectedJob, setSelectedJob] = useState(null);
  const [editCell, setEditCell] = useState(null);
  const [editForm, setEditForm] = useState({ order_pk: "", order_name: "", role: "", note: "", start_time: "", end_time: "" });
  const [schedules, setSchedules] = useState({});
  const [jobReqs, setJobReqs] = useState({});
  const [editingReq, setEditingReq] = useState(null);
  const [reqForm, setReqForm] = useState({ count: 1, roles: "" });
  const [crewData, setCrewData] = useState({});
  const [crewLoading, setCrewLoading] = useState(false);

  const weekDates = getWeekDates(weekKey);

  const loadUsers = useCallback(async () => {
    try {
      const r = await api.get(`/chat/users?token=${token}`);
      setUsers((r.data || []).filter(u => u.role !== "kunde"));
    } catch {}
  }, [token]);

  const loadPlan = useCallback(async () => {
    try {
      const r = await api.get(`/employee/shift-plan?week=${weekKey}&token=${token}`);
      setAssignments(r.data.assignments || []);
      setAbsences(r.data.absences || []);
      setReleased(r.data.released);
    } catch {}
  }, [token, weekKey]);

  const loadOrders = useCallback(async () => {
    try {
      const r = await api.get(`/orders/epirent?date_from=${weekDates[0]}&date_to=${weekDates[6]}`, { headers: { Authorization: `Bearer ${token}` } });
      const all = (r.data?.orders || []).filter(o => {
        if (!(o.event || o.order_no) || !o.is_confirmed) return false;
        const ds = o.dispo_start;
        const de = o.dispo_end;
        if (!ds || !de || ds === "0000-00-00" || de === "0000-00-00") return false;
        return ds <= weekDates[6] && de >= weekDates[0];
      });
      setOrders(all);
    } catch {}
  }, [token, weekDates[0], weekDates[6]]);

  const loadSchedules = useCallback(async () => {
    const map = {};
    for (const u of users) {
      try {
        const r = await api.get(`/employee/work-schedule/${u.id}?token=${token}`);
        if (r.data) map[u.id] = r.data;
      } catch {}
    }
    setSchedules(map);
  }, [token, users]);

  const loadJobReqs = useCallback(async () => {
    try {
      const r = await api.get(`/employee/shift-plan/job-reqs?week=${weekKey}&token=${token}`);
      const map = {};
      (r.data || []).forEach(j => { map[j.order_pk] = j; });
      setJobReqs(map);
    } catch {}
  }, [token, weekKey]);

  const loadCrewData = useCallback(async () => {
    if (orders.length === 0) return;
    setCrewLoading(true);
    try {
      const pks = orders.slice(0, 20).map(o => o.primary_key);
      const r = await api.post("/orders/epirent/crew/batch",
        { order_pks: pks },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      setCrewData(r.data?.results || {});
    } catch {
      // Silently fail - manual reqs still work
    }
    setCrewLoading(false);
  }, [token, orders]);

  useEffect(() => { loadUsers(); }, [loadUsers]);
  useEffect(() => { loadPlan(); loadOrders(); loadJobReqs(); }, [loadPlan, loadOrders, loadJobReqs]);
  useEffect(() => { if (users.length > 0) loadSchedules(); }, [users, loadSchedules]);
  useEffect(() => { if (orders.length > 0) loadCrewData(); }, [orders, loadCrewData]);

  const prevWeek = () => { const d = new Date(weekDates[0]); d.setDate(d.getDate() - 7); setWeekKey(getWeekKey(d)); };
  const nextWeek = () => { const d = new Date(weekDates[0]); d.setDate(d.getDate() + 7); setWeekKey(getWeekKey(d)); };

  const getAbsenceForUserDate = (userId, date) => absences.find(a => a.user_id === userId && a.date_from <= date && a.date_to >= date);
  const getAssignmentsForUserDate = (userId, date) => assignments.filter(a => a.user_id === userId && a.date === date);

  const getScheduledHours = (userId, dayIndex) => {
    const sched = schedules[userId];
    if (!sched?.days) return STANDARD_HOURS;
    const dayKeys = ["montag", "dienstag", "mittwoch", "donnerstag", "freitag", "samstag", "sonntag"];
    const day = sched.days[dayKeys[dayIndex]];
    if (!day?.start || !day?.end) return 0;
    return timeDiffHours(day.start, day.end) - (day.break_min || 0) / 60;
  };

  const getAssignedHours = (userId, date) => {
    const cellAssignments = getAssignmentsForUserDate(userId, date);
    return cellAssignments.reduce((sum, a) => sum + timeDiffHours(a.start_time, a.end_time), 0);
  };

  const getFreeHours = (userId, date, dayIndex) => {
    const scheduled = getScheduledHours(userId, dayIndex);
    const assigned = getAssignedHours(userId, date);
    return Math.max(0, scheduled - assigned);
  };

  const getJobNeeded = (orderPk) => {
    const crew = crewData[orderPk];
    if (crew && crew.length > 0) {
      return crew.reduce((sum, c) => sum + (c.count || 1), 0);
    }
    return jobReqs[orderPk]?.count || 0;
  };

  const getJobAssignedCount = (orderPk) => {
    return assignments.filter(a => a.order_pk === orderPk).length;
  };

  const absenceLabel = (type) => {
    if (type === "urlaub") return { text: "Urlaub", icon: Palmtree, cls: "bg-blue-100 text-blue-700" };
    if (type === "krank") return { text: "Krank", icon: ThermometerSun, cls: "bg-red-100 text-red-700" };
    if (type === "ueberstundenabbau") return { text: "ÜS-Abbau", icon: TrendingUp, cls: "bg-amber-100 text-amber-700" };
    return { text: type, icon: CalendarDays, cls: "bg-gray-100 text-gray-700" };
  };

  const handleCellClick = async (userId, date) => {
    if (selectedJob) {
      try {
        await api.post(`/employee/shift-plan?token=${token}`, {
          user_id: userId, date, week_key: weekKey,
          order_pk: selectedJob.primary_key,
          order_name: selectedJob.event || selectedJob.order_no,
          role: "", note: "",
          start_time: "", end_time: "",
        });
        loadPlan();
        toast.success(`${selectedJob.event || selectedJob.order_no} zugewiesen`);
      } catch { toast.error("Fehler"); }
    } else {
      setEditCell({ userId, date });
      setEditForm({ order_pk: "", order_name: "", role: "", note: "", start_time: "", end_time: "" });
    }
  };

  const saveAssignment = async (id = null) => {
    if (!editCell && !id) return;
    const payload = id ? { id, ...editForm, week_key: weekKey } : {
      user_id: editCell.userId, date: editCell.date, week_key: weekKey,
      order_pk: editForm.order_pk ? parseInt(editForm.order_pk) : null,
      order_name: editForm.order_name, role: editForm.role, note: editForm.note,
      start_time: editForm.start_time, end_time: editForm.end_time,
    };
    try {
      await api.post(`/employee/shift-plan?token=${token}`, payload);
      setEditCell(null);
      loadPlan();
    } catch { toast.error("Fehler beim Speichern"); }
  };

  const deleteAssignment = async (id) => {
    try { await api.delete(`/employee/shift-plan/${id}?token=${token}`); loadPlan(); } catch { toast.error("Fehler"); }
  };

  const releasePlan = async () => {
    try { await api.post(`/employee/shift-plan/release?week=${weekKey}&token=${token}`); toast.success("Wochenplan freigegeben!"); loadPlan(); } catch { toast.error("Fehler"); }
  };

  const saveJobReq = async () => {
    if (!editingReq) return;
    try {
      await api.post(`/employee/shift-plan/job-reqs?token=${token}`, {
        order_pk: editingReq, week_key: weekKey,
        count: parseInt(reqForm.count) || 1, roles: reqForm.roles,
      });
      setEditingReq(null);
      loadJobReqs();
    } catch { toast.error("Fehler"); }
  };

  const weekLabel = (() => {
    const from = new Date(weekDates[0] + "T00:00:00");
    const to = new Date(weekDates[6] + "T00:00:00");
    return `${from.toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit" })} – ${to.toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit", year: "numeric" })}`;
  })();

  return (
    <div className="min-h-screen bg-gray-50" data-testid="einsatzplanung-page">
      <header className="bg-white border-b border-gray-200 sticky top-0 z-20">
        <div className="max-w-[1600px] mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <button onClick={() => navigate("/hub")} className="text-gray-500 hover:text-gray-700" data-testid="back-btn">
              <ArrowLeft className="w-5 h-5" />
            </button>
            <CalendarDays className="w-5 h-5 text-indigo-600" />
            <h1 className="text-lg font-semibold text-gray-900">Einsatzplanung</h1>
          </div>
          <div className="flex items-center gap-2">
            <button onClick={prevWeek} className="p-1.5 rounded-lg hover:bg-gray-100" data-testid="prev-week"><ChevronLeft className="w-5 h-5" /></button>
            <span className="text-sm font-medium text-gray-700 min-w-[200px] text-center">{weekKey} · {weekLabel}</span>
            <button onClick={nextWeek} className="p-1.5 rounded-lg hover:bg-gray-100" data-testid="next-week"><ChevronRight className="w-5 h-5" /></button>
          </div>
          <div className="flex items-center gap-2">
            {selectedJob && (
              <div className="flex items-center gap-2 bg-indigo-100 border border-indigo-300 rounded-lg px-3 py-1.5">
                <UserPlus className="w-4 h-4 text-indigo-600" />
                <span className="text-xs font-medium text-indigo-800 max-w-[150px] truncate">{selectedJob.event || selectedJob.order_no}</span>
                <button onClick={() => setSelectedJob(null)} className="text-indigo-500 hover:text-indigo-700"><X className="w-3.5 h-3.5" /></button>
              </div>
            )}
            {released && <span className="text-xs text-green-600 flex items-center gap-1"><Check className="w-3.5 h-3.5" /> Freigegeben</span>}
            <Button onClick={releasePlan} size="sm" className="bg-indigo-600 hover:bg-indigo-700" data-testid="release-plan-btn">
              <Send className="w-3.5 h-3.5 mr-1.5" /> Freigeben
            </Button>
          </div>
        </div>
      </header>

      {/* Jobs with personnel requirements */}
      <div className="max-w-[1600px] mx-auto px-4 pt-4">
        <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider mb-2">
          Aufträge diese Woche ({orders.length}) {selectedJob && <span className="text-indigo-600 normal-case">— Klicke auf eine Zelle zum Zuweisen</span>}
        </p>
        <div className="flex gap-2 overflow-x-auto pb-2">
          {orders.slice(0, 20).map(o => {
            const pk = o.primary_key;
            const req = jobReqs[pk];
            const crew = crewData[pk];
            const hasCrew = crew && crew.length > 0;
            const assigned = getJobAssignedCount(pk);
            const needed = getJobNeeded(pk);
            const isFull = needed > 0 && assigned >= needed;
            const hasReqs = needed > 0;
            const isSelected = selectedJob?.primary_key === pk;
            const pct = needed > 0 ? Math.min(100, Math.round(assigned / needed * 100)) : 0;
            return (
              <div key={pk}
                className={`flex-shrink-0 border-2 rounded-lg px-3 py-2 text-xs cursor-pointer transition-all min-w-[200px] max-w-[260px] ${
                  isSelected ? "border-indigo-500 bg-indigo-50 ring-2 ring-indigo-200" :
                  isFull ? "border-green-400 bg-green-50 hover:border-green-500 shadow-sm shadow-green-100" :
                  hasReqs ? "border-orange-200 bg-white hover:border-orange-300" :
                  "border-gray-200 bg-white hover:border-indigo-300 hover:bg-indigo-50/30"
                }`}
                onClick={() => setSelectedJob(isSelected ? null : o)}
                data-testid={`order-${pk}`}
              >
                <p className="font-semibold text-gray-900 truncate">{o.event || o.order_no}</p>
                <p className="text-gray-400 truncate">{o.contact_name}</p>
                <p className="text-gray-400">{o.dispo_start || o.event_start || "—"} – {o.dispo_end || o.event_end || ""}</p>

                <div className="mt-1.5 pt-1.5 border-t border-gray-100">
                  {hasReqs ? (
                    <div data-testid={hasCrew ? `crew-${pk}` : `req-${pk}`}>
                      {/* Progress bar */}
                      <div className="flex items-center gap-1.5 mb-1">
                        <Users className={`w-3.5 h-3.5 ${isFull ? "text-green-600" : "text-orange-500"}`} />
                        <span className={`font-bold text-xs ${isFull ? "text-green-700" : "text-orange-600"}`}>
                          {assigned}/{needed} Zugewiesen
                        </span>
                        {isFull && <Check className="w-3.5 h-3.5 text-green-600 ml-auto" />}
                        {hasCrew && <span className="text-[9px] text-indigo-500 font-medium ml-auto">EpiRent</span>}
                      </div>
                      <div className="w-full bg-gray-200 rounded-full h-1.5 mb-1.5">
                        <div className={`h-1.5 rounded-full transition-all ${isFull ? "bg-green-500" : "bg-orange-400"}`} style={{ width: `${pct}%` }} />
                      </div>
                      {/* Role details */}
                      {hasCrew ? (
                        <div className="space-y-0.5">
                          {crew.map((c, ci) => (
                            <div key={ci} className="flex items-center gap-1 text-[10px] bg-indigo-50/60 rounded px-1.5 py-0.5">
                              <span className="font-bold text-indigo-700">{c.count}x</span>
                              <span className="text-gray-700 truncate flex-1">{c.title || "Personal"}</span>
                              {c.time_start && c.time_end && (
                                <span className="text-gray-400 flex items-center gap-0.5 flex-shrink-0">
                                  <Clock className="w-2.5 h-2.5" />{c.time_start}–{c.time_end}
                                </span>
                              )}
                            </div>
                          ))}
                        </div>
                      ) : req?.roles ? (
                        <div className="flex items-center justify-between">
                          <p className="text-[10px] text-gray-500 truncate">{req.roles}</p>
                          <button onClick={(e) => { e.stopPropagation(); setEditingReq(pk); setReqForm({ count: req?.count || 1, roles: req?.roles || "" }); }}
                            className="text-gray-400 hover:text-indigo-600 p-0.5" data-testid={`edit-req-${pk}`}>
                            <Edit2 className="w-3 h-3" />
                          </button>
                        </div>
                      ) : null}
                    </div>
                  ) : (
                    <button
                      onClick={(e) => { e.stopPropagation(); setEditingReq(pk); setReqForm({ count: 1, roles: "" }); }}
                      className="w-full flex items-center justify-center gap-1.5 py-1 rounded-md border border-dashed border-gray-300 text-gray-400 hover:border-indigo-400 hover:text-indigo-600 hover:bg-indigo-50/50 transition-colors"
                      data-testid={`add-req-${pk}`}
                    >
                      <Plus className="w-3 h-3" />
                      <span className="text-[10px] font-medium">Personal definieren</span>
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        {/* Personnel requirement edit popup */}
        {editingReq && (
          <div className="mt-2 inline-flex items-center gap-2 bg-white border-2 border-indigo-400 rounded-lg px-3 py-2 shadow-lg" data-testid="req-edit-form">
            <span className="text-xs text-gray-600 font-medium">Personal:</span>
            <Input type="number" min="1" value={reqForm.count} onChange={e => setReqForm(f => ({ ...f, count: e.target.value }))} className="w-16 h-7 text-xs" placeholder="Anz." />
            <Input value={reqForm.roles} onChange={e => setReqForm(f => ({ ...f, roles: e.target.value }))} className="w-48 h-7 text-xs" placeholder="z.B. 2x Elektriker, 1x LKW" />
            <Button size="sm" onClick={saveJobReq} className="h-7 text-xs bg-indigo-600"><Check className="w-3 h-3 mr-0.5" /> OK</Button>
            <Button size="sm" variant="ghost" onClick={() => setEditingReq(null)} className="h-7 text-xs"><X className="w-3 h-3" /></Button>
          </div>
        )}
      </div>

      {/* Weekly Grid */}
      <div className="max-w-[1600px] mx-auto px-4 py-4">
        <div className="bg-white rounded-xl border border-gray-200 overflow-x-auto">
          <table className="w-full text-xs" data-testid="shift-grid">
            <thead>
              <tr className="border-b border-gray-200">
                <th className="text-left px-3 py-2 sticky left-0 bg-white z-10 min-w-[140px]">
                  <div className="flex items-center gap-1.5 text-[10px] text-gray-400 uppercase font-semibold">
                    <Users className="w-3.5 h-3.5" /> Mitarbeiter
                  </div>
                </th>
                {weekDates.map((d, i) => {
                  const isToday = d === new Date().toISOString().split("T")[0];
                  const isSun = i === 6;
                  return (
                    <th key={d} className={`text-center px-1 py-2 min-w-[140px] ${isToday ? "bg-indigo-50" : ""} ${isSun ? "bg-red-50/50" : ""}`}>
                      <p className={`text-[10px] uppercase font-semibold ${isToday ? "text-indigo-600" : isSun ? "text-red-500" : "text-gray-400"}`}>{WEEKDAYS[i]}</p>
                      <p className={`text-sm font-bold ${isToday ? "text-indigo-700" : "text-gray-700"}`}>{formatDateShort(d)}</p>
                    </th>
                  );
                })}
              </tr>
            </thead>
            <tbody>
              {users.map(user => (
                <tr key={user.id} className="border-b border-gray-100 hover:bg-gray-50/50" data-testid={`row-${user.id}`}>
                  <td className="px-3 py-1.5 sticky left-0 bg-white z-10 border-r border-gray-100">
                    <p className="font-medium text-gray-900 truncate text-xs">{user.name}</p>
                  </td>
                  {weekDates.map((date, dayIdx) => {
                    const absence = getAbsenceForUserDate(user.id, date);
                    const cellAssignments = getAssignmentsForUserDate(user.id, date);
                    const isToday = date === new Date().toISOString().split("T")[0];
                    const isSun = dayIdx === 6;
                    const isEditing = editCell?.userId === user.id && editCell?.date === date;
                    const freeH = getFreeHours(user.id, date, dayIdx);
                    const assignedH = getAssignedHours(user.id, date);
                    const hasWork = cellAssignments.length > 0;
                    return (
                      <td key={date}
                        className={`px-1 py-1 align-top relative group cursor-pointer ${
                          isToday ? "bg-indigo-50/50" : ""} ${isSun ? "bg-red-50/30" : ""} ${
                          selectedJob ? "hover:bg-indigo-100/50 hover:ring-1 hover:ring-indigo-300 hover:ring-inset" : ""
                        }`}
                        onClick={() => !absence && !isEditing && handleCellClick(user.id, date)}
                      >
                        {absence && (() => {
                          const a = absenceLabel(absence.type);
                          const Icon = a.icon;
                          return <div className={`rounded-md px-2 py-1 mb-1 flex items-center gap-1 ${a.cls}`}><Icon className="w-3 h-3" /><span className="text-[10px] font-medium">{a.text}</span></div>;
                        })()}

                        {cellAssignments.map(asgn => (
                          <div key={asgn.id} className="bg-indigo-50 border border-indigo-200 rounded-md px-1.5 py-1 mb-1 relative group/item" data-testid={`asgn-${asgn.id}`}>
                            {asgn.order_name && <p className="text-[10px] font-semibold text-indigo-800 truncate">{asgn.order_name}</p>}
                            {asgn.role && <p className="text-[10px] text-indigo-600">{asgn.role}</p>}
                            {(asgn.start_time || asgn.end_time) && (
                              <p className="text-[10px] text-gray-500 flex items-center gap-0.5"><Clock className="w-2.5 h-2.5" /> {asgn.start_time || "?"} – {asgn.end_time || "?"}</p>
                            )}
                            {asgn.note && <p className="text-[10px] text-gray-500 italic truncate">{asgn.note}</p>}
                            <button onClick={(e) => { e.stopPropagation(); deleteAssignment(asgn.id); }}
                              className="absolute -top-1 -right-1 w-4 h-4 rounded-full bg-red-500 text-white flex items-center justify-center opacity-0 group-hover/item:opacity-100 transition-opacity">
                              <X className="w-2.5 h-2.5" />
                            </button>
                          </div>
                        ))}

                        {/* Free hours indicator */}
                        {!absence && hasWork && freeH > 0 && (
                          <div className="text-[9px] text-center text-emerald-600 bg-emerald-50 rounded px-1 py-0.5 font-medium">
                            {freeH.toFixed(1)}h frei
                          </div>
                        )}

                        {/* Plus button when no selected job */}
                        {!absence && !isEditing && !selectedJob && (
                          <button onClick={(e) => { e.stopPropagation(); handleCellClick(user.id, date); }}
                            className="w-full py-0.5 rounded border border-dashed border-transparent hover:border-indigo-300 opacity-0 group-hover:opacity-100 transition-all flex items-center justify-center mt-0.5">
                            <Plus className="w-3 h-3 text-indigo-400" />
                          </button>
                        )}

                        {/* Edit form */}
                        {isEditing && (
                          <div className="bg-white border-2 border-indigo-400 rounded-lg p-2 shadow-xl z-30 absolute top-0 left-0 w-[240px]" onClick={e => e.stopPropagation()} data-testid="edit-form">
                            <select value={editForm.order_pk} onChange={e => {
                              const o = orders.find(o => String(o.primary_key) === e.target.value);
                              setEditForm(f => ({ ...f, order_pk: e.target.value, order_name: o ? (o.event || o.order_no) : f.order_name }));
                            }} className="w-full text-xs border rounded px-2 py-1 mb-1">
                              <option value="">— Auftrag —</option>
                              {orders.map(o => <option key={o.primary_key} value={o.primary_key}>{o.event || o.order_no}</option>)}
                            </select>
                            <Input value={editForm.order_name} onChange={e => setEditForm(f => ({ ...f, order_name: e.target.value }))} placeholder="Projekt / Freitext" className="h-7 text-xs mb-1" />
                            <Input value={editForm.role} onChange={e => setEditForm(f => ({ ...f, role: e.target.value }))} placeholder="Rolle" className="h-7 text-xs mb-1" />
                            <div className="flex gap-1 mb-1">
                              <Input type="time" value={editForm.start_time} onChange={e => setEditForm(f => ({ ...f, start_time: e.target.value }))} className="h-7 text-xs flex-1" />
                              <span className="text-gray-400 self-center text-xs">–</span>
                              <Input type="time" value={editForm.end_time} onChange={e => setEditForm(f => ({ ...f, end_time: e.target.value }))} className="h-7 text-xs flex-1" />
                            </div>
                            <Input value={editForm.note} onChange={e => setEditForm(f => ({ ...f, note: e.target.value }))} placeholder="Notiz" className="h-7 text-xs mb-1" />
                            <div className="flex gap-1">
                              <Button size="sm" onClick={() => saveAssignment()} className="h-6 text-[10px] bg-indigo-600 flex-1"><Check className="w-3 h-3 mr-0.5" /> OK</Button>
                              <Button size="sm" variant="ghost" onClick={() => setEditCell(null)} className="h-6 text-[10px]"><X className="w-3 h-3" /></Button>
                            </div>
                          </div>
                        )}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
