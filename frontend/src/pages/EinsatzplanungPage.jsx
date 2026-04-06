import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import api from "../lib/api";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { toast } from "sonner";
import {
  ArrowLeft, ChevronLeft, ChevronRight, CalendarDays, Users, Plus, X, Trash2,
  Check, Send, Palmtree, ThermometerSun, TrendingUp, Briefcase, FileText,
} from "lucide-react";

const WEEKDAYS = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"];

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

export default function EinsatzplanungPage() {
  const navigate = useNavigate();
  const token = localStorage.getItem("token");
  const [weekKey, setWeekKey] = useState(() => getWeekKey(new Date()));
  const [users, setUsers] = useState([]);
  const [assignments, setAssignments] = useState([]);
  const [absences, setAbsences] = useState([]);
  const [released, setReleased] = useState(false);
  const [releasedAt, setReleasedAt] = useState(null);
  const [orders, setOrders] = useState([]);
  const [editCell, setEditCell] = useState(null);
  const [editForm, setEditForm] = useState({ order_pk: "", order_name: "", role: "", note: "" });

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
      setReleasedAt(r.data.released_at);
    } catch {}
  }, [token, weekKey]);

  const loadOrders = useCallback(async () => {
    try {
      const from = weekDates[0];
      const to = weekDates[6];
      const r = await api.get(`/orders/epirent?date_from=${from}&date_to=${to}`, { headers: { Authorization: `Bearer ${token}` } });
      setOrders(r.data?.orders || []);
    } catch {}
  }, [token, weekDates]);

  useEffect(() => { loadUsers(); }, [loadUsers]);
  useEffect(() => { loadPlan(); loadOrders(); }, [loadPlan, loadOrders]);

  const prevWeek = () => {
    const d = new Date(weekDates[0]);
    d.setDate(d.getDate() - 7);
    setWeekKey(getWeekKey(d));
  };
  const nextWeek = () => {
    const d = new Date(weekDates[0]);
    d.setDate(d.getDate() + 7);
    setWeekKey(getWeekKey(d));
  };

  const getAbsenceForUserDate = (userId, date) => {
    return absences.find(a =>
      a.user_id === userId && a.date_from <= date && a.date_to >= date
    );
  };

  const getAssignmentsForUserDate = (userId, date) => {
    return assignments.filter(a => a.user_id === userId && a.date === date);
  };

  const absenceLabel = (type) => {
    if (type === "urlaub") return { text: "Urlaub", icon: Palmtree, cls: "bg-blue-100 text-blue-700" };
    if (type === "krank") return { text: "Krank", icon: ThermometerSun, cls: "bg-red-100 text-red-700" };
    if (type === "ueberstundenabbau") return { text: "ÜS-Abbau", icon: TrendingUp, cls: "bg-amber-100 text-amber-700" };
    return { text: type, icon: CalendarDays, cls: "bg-gray-100 text-gray-700" };
  };

  const openEdit = (userId, date) => {
    setEditCell({ userId, date });
    setEditForm({ order_pk: "", order_name: "", role: "", note: "" });
  };

  const saveAssignment = async () => {
    if (!editCell) return;
    try {
      await api.post(`/employee/shift-plan?token=${token}`, {
        user_id: editCell.userId,
        date: editCell.date,
        order_pk: editForm.order_pk ? parseInt(editForm.order_pk) : null,
        order_name: editForm.order_name,
        role: editForm.role,
        note: editForm.note,
        week_key: weekKey,
      });
      setEditCell(null);
      loadPlan();
    } catch { toast.error("Fehler beim Speichern"); }
  };

  const deleteAssignment = async (id) => {
    try {
      await api.delete(`/employee/shift-plan/${id}?token=${token}`);
      loadPlan();
    } catch { toast.error("Fehler"); }
  };

  const releasePlan = async () => {
    try {
      await api.post(`/employee/shift-plan/release?week=${weekKey}&token=${token}`);
      toast.success("Wochenplan freigegeben!");
      loadPlan();
    } catch { toast.error("Fehler bei der Freigabe"); }
  };

  const weekLabel = (() => {
    const from = new Date(weekDates[0] + "T00:00:00");
    const to = new Date(weekDates[6] + "T00:00:00");
    return `${from.toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit" })} – ${to.toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit", year: "numeric" })}`;
  })();

  return (
    <div className="min-h-screen bg-gray-50" data-testid="einsatzplanung-page">
      {/* Header */}
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
            {released && <span className="text-xs text-green-600 flex items-center gap-1"><Check className="w-3.5 h-3.5" /> Freigegeben</span>}
            <Button onClick={releasePlan} size="sm" className="bg-indigo-600 hover:bg-indigo-700" data-testid="release-plan-btn">
              <Send className="w-3.5 h-3.5 mr-1.5" /> Wochenplan freigeben
            </Button>
          </div>
        </div>
      </header>

      {/* Orders this week */}
      {orders.length > 0 && (
        <div className="max-w-[1600px] mx-auto px-4 pt-4">
          <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider mb-2">Aufträge diese Woche ({orders.length})</p>
          <div className="flex gap-2 overflow-x-auto pb-2">
            {orders.map(o => (
              <div key={o.primary_key} className="flex-shrink-0 bg-white border border-gray-200 rounded-lg px-3 py-2 text-xs" data-testid={`order-${o.primary_key}`}>
                <p className="font-medium text-gray-900 truncate max-w-[200px]">{o.event || o.order_no}</p>
                <p className="text-gray-400">{o.contact_name} · {o.event_start || o.dispo_start}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Weekly Grid */}
      <div className="max-w-[1600px] mx-auto px-4 py-4">
        <div className="bg-white rounded-xl border border-gray-200 overflow-x-auto">
          <table className="w-full text-xs" data-testid="shift-grid">
            <thead>
              <tr className="border-b border-gray-200">
                <th className="text-left px-3 py-2 sticky left-0 bg-white z-10 min-w-[160px]">
                  <div className="flex items-center gap-1.5 text-[10px] text-gray-400 uppercase font-semibold">
                    <Users className="w-3.5 h-3.5" /> Mitarbeiter
                  </div>
                </th>
                {weekDates.map((d, i) => {
                  const isToday = d === new Date().toISOString().split("T")[0];
                  const isSun = i === 6;
                  return (
                    <th key={d} className={`text-center px-2 py-2 min-w-[130px] ${isToday ? "bg-indigo-50" : ""} ${isSun ? "bg-red-50/50" : ""}`}>
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
                  <td className="px-3 py-2 sticky left-0 bg-white z-10 border-r border-gray-100">
                    <p className="font-medium text-gray-900 truncate">{user.name}</p>
                  </td>
                  {weekDates.map((date, i) => {
                    const absence = getAbsenceForUserDate(user.id, date);
                    const cellAssignments = getAssignmentsForUserDate(user.id, date);
                    const isToday = date === new Date().toISOString().split("T")[0];
                    const isSun = i === 6;
                    const isEditing = editCell?.userId === user.id && editCell?.date === date;
                    return (
                      <td key={date} className={`px-1.5 py-1.5 align-top relative group ${isToday ? "bg-indigo-50/50" : ""} ${isSun ? "bg-red-50/30" : ""}`}>
                        {absence && (() => {
                          const a = absenceLabel(absence.type);
                          const Icon = a.icon;
                          return (
                            <div className={`rounded-md px-2 py-1 mb-1 flex items-center gap-1 ${a.cls}`}>
                              <Icon className="w-3 h-3" />
                              <span className="text-[10px] font-medium">{a.text}</span>
                            </div>
                          );
                        })()}
                        {cellAssignments.map(asgn => (
                          <div key={asgn.id} className="bg-indigo-50 border border-indigo-200 rounded-md px-2 py-1 mb-1 relative group/item" data-testid={`asgn-${asgn.id}`}>
                            {asgn.order_name && <p className="text-[10px] font-semibold text-indigo-800 truncate">{asgn.order_name}</p>}
                            {asgn.role && <p className="text-[10px] text-indigo-600">{asgn.role}</p>}
                            {asgn.note && <p className="text-[10px] text-gray-600 italic truncate">{asgn.note}</p>}
                            <button onClick={() => deleteAssignment(asgn.id)} className="absolute -top-1 -right-1 w-4 h-4 rounded-full bg-red-500 text-white flex items-center justify-center opacity-0 group-hover/item:opacity-100 transition-opacity" data-testid={`del-${asgn.id}`}>
                              <X className="w-2.5 h-2.5" />
                            </button>
                          </div>
                        ))}
                        {!absence && !isEditing && (
                          <button onClick={() => openEdit(user.id, date)} className="w-full py-1 rounded border border-dashed border-transparent hover:border-indigo-300 hover:bg-indigo-50/50 opacity-0 group-hover:opacity-100 transition-all flex items-center justify-center" data-testid={`add-${user.id}-${date}`}>
                            <Plus className="w-3.5 h-3.5 text-indigo-400" />
                          </button>
                        )}
                        {isEditing && (
                          <div className="bg-white border-2 border-indigo-400 rounded-lg p-2 shadow-lg z-30 absolute top-0 left-0 w-[220px]" data-testid="edit-form">
                            <select value={editForm.order_pk} onChange={e => {
                              const o = orders.find(o => String(o.primary_key) === e.target.value);
                              setEditForm(f => ({ ...f, order_pk: e.target.value, order_name: o ? (o.event || o.order_no) : "" }));
                            }} className="w-full text-xs border rounded px-2 py-1 mb-1">
                              <option value="">— Auftrag (optional) —</option>
                              {orders.map(o => <option key={o.primary_key} value={o.primary_key}>{o.event || o.order_no}</option>)}
                            </select>
                            <Input value={editForm.order_name} onChange={e => setEditForm(f => ({ ...f, order_name: e.target.value }))} placeholder="Auftrag / Projekt" className="h-7 text-xs mb-1" />
                            <Input value={editForm.role} onChange={e => setEditForm(f => ({ ...f, role: e.target.value }))} placeholder="Rolle (Elektriker...)" className="h-7 text-xs mb-1" />
                            <Input value={editForm.note} onChange={e => setEditForm(f => ({ ...f, note: e.target.value }))} placeholder="Freitext / Notiz" className="h-7 text-xs mb-1" />
                            <div className="flex gap-1">
                              <Button size="sm" onClick={saveAssignment} className="h-6 text-[10px] bg-indigo-600 flex-1"><Check className="w-3 h-3 mr-0.5" /> OK</Button>
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
