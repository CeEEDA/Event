import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import api from "../lib/api";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { toast } from "sonner";
import {
  ArrowLeft, ChevronLeft, ChevronRight, CalendarDays, Users, Plus, X, Trash2,
  Check, Send, Palmtree, ThermometerSun, TrendingUp, Clock, Edit2, UserPlus, ExternalLink, Copy,
  CalendarCheck2, Trees,
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
  const jan4 = new Date(y, 0, 4, 12, 0, 0); // noon to avoid timezone issues
  const monday = new Date(jan4);
  monday.setDate(jan4.getDate() - ((jan4.getDay() + 6) % 7) + (w - 1) * 7);
  return Array.from({ length: 7 }, (_, i) => {
    const d = new Date(monday);
    d.setDate(monday.getDate() + i);
    const yr = d.getFullYear();
    const mo = String(d.getMonth() + 1).padStart(2, "0");
    const da = String(d.getDate()).padStart(2, "0");
    return `${yr}-${mo}-${da}`;
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
  const [editForm, setEditForm] = useState({ order_pk: "", order_name: "", role: "", note: "", start_time: "", end_time: "", is_offday: false });
  const [schedules, setSchedules] = useState({});
  const [jobReqs, setJobReqs] = useState({});
  const [editingReq, setEditingReq] = useState(null);
  const [reqForm, setReqForm] = useState({ count: 1, roles: "" });
  const [crewData, setCrewData] = useState({});
  const [crewLoading, setCrewLoading] = useState(false);
  const [copySource, setCopySource] = useState(null);
  const [spanWholeJob, setSpanWholeJob] = useState(false);
  const [offdayMode, setOffdayMode] = useState(false);
  const [offdayBalances, setOffdayBalances] = useState({});  // { user_id: balance }
  const [orderFilter, setOrderFilter] = useState("crew"); // "crew" | "confirmed" | "all"

  const weekDates = getWeekDates(weekKey);

  const loadUsers = useCallback(async () => {
    try {
      const r = await api.get(`/users/active`);
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
      // Alle Auftraege anzeigen, die in der Woche aktiv sind - auch unbestaetigte
      // (Liefer-Jobs ohne Personal-Anforderung), damit sie nicht 'untergehen'.
      // Unbestaetigte werden im UI visuell abgesetzt (gestrichelter Rahmen).
      const all = (r.data?.orders || []).filter(o => {
        if (!(o.event || o.order_no)) return false;
        const ds = o.dispo_start;
        const de = o.dispo_end;
        if (!ds || !de || ds === "0000-00-00" || de === "0000-00-00") return false;
        return ds <= weekDates[6] && de >= weekDates[0];
      });
      setOrders(all);
    } catch {/* silent */}
  }, [token, weekDates]);

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
      // Nur fuer bestaetigte Auftraege (is_confirmed=true) Crew-Daten laden.
      const pks = orders
        .filter(o => o.is_confirmed)
        .slice(0, 40)
        .map(o => o.primary_key);
      if (pks.length === 0) { setCrewData({}); setCrewLoading(false); return; }
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

  const loadOffdayBalances = useCallback(async () => {
    try {
      const r = await api.get(`/employee/offdays?token=${token}`);
      const map = {};
      (r.data?.balances || []).forEach(b => { map[b.user_id] = b.balance; });
      setOffdayBalances(map);
    } catch {
      // Falls keine Verwaltung-Berechtigung: still ohne Saldo anzeigen
    }
  }, [token]);

  useEffect(() => { loadUsers(); }, [loadUsers]);
  useEffect(() => { loadPlan(); loadOrders(); loadJobReqs(); loadOffdayBalances(); }, [loadPlan, loadOrders, loadJobReqs, loadOffdayBalances]);
  useEffect(() => { if (users.length > 0) loadSchedules(); }, [users, loadSchedules]);
  useEffect(() => { if (orders.length > 0) loadCrewData(); }, [orders, loadCrewData]);

  const prevWeek = () => { const d = new Date(weekDates[0] + "T12:00:00"); d.setDate(d.getDate() - 7); setWeekKey(getWeekKey(d)); };
  const nextWeek = () => { const d = new Date(weekDates[0] + "T12:00:00"); d.setDate(d.getDate() + 7); setWeekKey(getWeekKey(d)); };

  const getAbsenceForUserDate = (userId, date) => absences.find(a => a.user_id === userId && a.start_date <= date && a.end_date >= date);
  const getAssignmentsForUserDate = (userId, date) => assignments.filter(a => a.user_id === userId && a.date === date);

  const getScheduledHours = (userId, dayIndex) => {
    const sched = schedules[userId];
    if (!sched?.days) return STANDARD_HOURS;
    const dayKeys = ["montag", "dienstag", "mittwoch", "donnerstag", "freitag", "samstag", "sonntag"];
    const day = sched.days[dayKeys[dayIndex]];
    if (!day) return 0;
    // Bevorzugt neue Sollstunden, Fallback auf alte start/end-Logik
    if (day.soll_hours != null && day.soll_hours !== "") {
      const h = parseFloat(day.soll_hours);
      return Number.isFinite(h) && h > 0 ? h : 0;
    }
    if (!day.start || !day.end) return 0;
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
    // Offday-Mode: belastet Konto direkt
    if (offdayMode) {
      // Vorab-Check: existiert bereits ein Eintrag fuer diesen Tag?
      const existing = (assignments || []).filter(a => a.user_id === userId && a.date === date);
      if (existing.some(a => a.is_offday)) {
        toast.error("An diesem Tag ist bereits ein Offday vergeben.");
        return;
      }
      if (existing.length > 0) {
        toast.error("Tag hat schon Einsätze - bitte erst löschen, dann Offday vergeben.");
        return;
      }
      const currBal = offdayBalances[userId] ?? 0;
      if (currBal <= 0) {
        if (!window.confirm(`Saldo ist ${currBal}. Trotzdem Offday zuweisen? Konto geht ins Minus.`)) return;
      }
      try {
        await api.post(`/employee/shift-plan?token=${token}`, {
          user_id: userId, date, week_key: weekKey,
          order_pk: null, order_name: "Offday", role: "", note: "",
          start_time: "", end_time: "", is_offday: true,
        });
        loadPlan();
        loadOffdayBalances();
        toast.success("Offday zugewiesen");
      } catch (e) { toast.error(e.response?.data?.detail || "Fehler"); }
      return;
    }
    // Copy mode: paste the copied assignment to this cell
    if (copySource) {
      // Vorab-Check: kein Einsatz auf Offday-Tag erlauben
      const offdayHere = (assignments || []).find(a => a.user_id === userId && a.date === date && a.is_offday);
      if (offdayHere) {
        toast.error("Tag ist als Offday geblockt - bitte erst Offday loeschen.");
        return;
      }
      try {
        await api.post(`/employee/shift-plan?token=${token}`, {
          user_id: userId, date, week_key: weekKey,
          order_pk: copySource.order_pk,
          order_name: copySource.order_name,
          role: copySource.role || "", note: copySource.note || "",
          start_time: copySource.start_time || "", end_time: copySource.end_time || "",
        });
        loadPlan();
        toast.success(`${copySource.order_name || "Aufgabe"} kopiert`);
      } catch (e) { toast.error(e.response?.data?.detail || "Fehler"); }
      return;
    }
    if (selectedJob) {
      try {
        const jobStart = selectedJob.dispo_start || selectedJob.event_start;
        const jobEnd = selectedJob.dispo_end || selectedJob.event_end;
        if (spanWholeJob && jobStart && jobEnd) {
          // Mehrtages-Zuweisung: gesamte Job-Dauer
          const resp = await api.post(`/employee/shift-plan?token=${token}`, {
            user_id: userId,
            date_from: jobStart, date_to: jobEnd,
            order_pk: selectedJob.primary_key,
            order_name: selectedJob.event || selectedJob.order_no,
            role: "", note: "", start_time: "", end_time: "",
          });
          loadPlan();
          const created = resp.data?.created || 0;
          const skipped = resp.data?.skipped_existing || 0;
          toast.success(`${selectedJob.event || selectedJob.order_no} zugewiesen – ${created} Tag(e)${skipped ? `, ${skipped} schon vorhanden` : ""}`);
        } else {
          await api.post(`/employee/shift-plan?token=${token}`, {
            user_id: userId, date, week_key: weekKey,
            order_pk: selectedJob.primary_key,
            order_name: selectedJob.event || selectedJob.order_no,
            role: "", note: "",
            start_time: "", end_time: "",
          });
          loadPlan();
          toast.success(`${selectedJob.event || selectedJob.order_no} zugewiesen`);
        }
      } catch { toast.error("Fehler"); }
    } else {
      setEditCell({ userId, date });
      setEditForm({ order_pk: "", order_name: "", role: "", note: "", start_time: "", end_time: "", is_offday: false });
    }
  };

  const saveAssignment = async (id = null) => {
    if (!editCell && !id) return;
    const payload = id ? { id, ...editForm, week_key: weekKey } : {
      user_id: editCell.userId, date: editCell.date, week_key: weekKey,
      order_pk: editForm.order_pk ? parseInt(editForm.order_pk) : null,
      order_name: editForm.order_name, role: editForm.role, note: editForm.note,
      start_time: editForm.start_time, end_time: editForm.end_time,
      is_offday: !!editForm.is_offday,
    };
    try {
      await api.post(`/employee/shift-plan?token=${token}`, payload);
      setEditCell(null);
      loadPlan();
      if (payload.is_offday) loadOffdayBalances();
    } catch (e) { toast.error(e.response?.data?.detail || "Fehler beim Speichern"); }
  };

  const deleteAssignment = async (id) => {
    try {
      await api.delete(`/employee/shift-plan/${id}?token=${token}`);
      loadPlan();
      loadOffdayBalances();
    } catch { toast.error("Fehler"); }
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
            {copySource && (
              <div className="flex items-center gap-2 bg-amber-100 border border-amber-300 rounded-lg px-3 py-1.5">
                <Copy className="w-4 h-4 text-amber-600" />
                <span className="text-xs font-medium text-amber-800 max-w-[150px] truncate">{copySource.order_name || "Aufgabe"}</span>
                <span className="text-[10px] text-amber-600">→ Zelle klicken zum Einfügen</span>
                <button onClick={() => setCopySource(null)} className="text-amber-500 hover:text-amber-700" data-testid="cancel-copy"><X className="w-3.5 h-3.5" /></button>
              </div>
            )}
            {selectedJob && (
              <div className="flex items-center gap-2 bg-indigo-100 border border-indigo-300 rounded-lg px-3 py-1.5">
                <UserPlus className="w-4 h-4 text-indigo-600" />
                <span className="text-xs font-medium text-indigo-800 max-w-[150px] truncate">{selectedJob.event || selectedJob.order_no}</span>
                <label className="flex items-center gap-1.5 text-xs text-indigo-800 cursor-pointer select-none ml-1 pl-2 border-l border-indigo-300"
                  title="Bei Klick auf Mitarbeiter werden alle Tage von Dispo-Start bis Dispo-Ende zugewiesen">
                  <input
                    type="checkbox"
                    checked={spanWholeJob}
                    onChange={e => setSpanWholeJob(e.target.checked)}
                    className="w-3.5 h-3.5 accent-indigo-600"
                    data-testid="span-whole-job-toggle"
                  />
                  Alle Tage
                </label>
                <button onClick={() => { setSelectedJob(null); setSpanWholeJob(false); }} className="text-indigo-500 hover:text-indigo-700"><X className="w-3.5 h-3.5" /></button>
              </div>
            )}
            {released && <span className="text-xs text-green-600 flex items-center gap-1"><Check className="w-3.5 h-3.5" /> Freigegeben</span>}
            <Button
              onClick={() => { setOffdayMode(v => !v); setSelectedJob(null); setCopySource(null); }}
              size="sm"
              variant={offdayMode ? "default" : "outline"}
              className={offdayMode ? "bg-violet-600 hover:bg-violet-700" : "border-violet-300 text-violet-700 hover:bg-violet-50"}
              data-testid="offday-mode-toggle"
              title="Offday-Modus: Klick auf Zelle vergibt einen Ausgleichstag und zieht ihn vom Saldo ab"
            >
              <CalendarCheck2 className="w-3.5 h-3.5 mr-1.5" /> Offday {offdayMode ? "AN" : ""}
            </Button>
            <Button onClick={releasePlan} size="sm" className="bg-indigo-600 hover:bg-indigo-700" data-testid="release-plan-btn">
              <Send className="w-3.5 h-3.5 mr-1.5" /> Freigeben
            </Button>
          </div>
        </div>
        {offdayMode && (
          <div className="bg-violet-50 border-t border-violet-200 px-4 py-2 text-xs text-violet-800 flex items-center gap-2">
            <CalendarCheck2 className="w-3.5 h-3.5" />
            <span><strong>Offday-Modus aktiv:</strong> Klicke auf eine Zelle, um dem Mitarbeiter einen Ausgleichstag zu vergeben. Der Tag wird vom Offday-Saldo abgezogen.</span>
            <button onClick={() => setOffdayMode(false)} className="ml-auto text-violet-500 hover:text-violet-700" data-testid="offday-mode-off"><X className="w-3.5 h-3.5" /></button>
          </div>
        )}
      </header>

      {/* Jobs with personnel requirements */}
      <div className="max-w-[1600px] mx-auto px-4 pt-4">
        <div className="flex items-center justify-between gap-3 mb-2 flex-wrap">
          <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider">
            Aufträge diese Woche
            {selectedJob && <span className="ml-2 text-indigo-600 normal-case">— Klicke auf eine Zelle zum Zuweisen</span>}
          </p>
          <div className="flex border border-gray-200 rounded-lg overflow-hidden text-[11px]" data-testid="order-filter">
            {[
              { key: "crew", label: "Nur Personal" },
              { key: "confirmed", label: "Alle bestätigten" },
              { key: "all", label: "Alle Jobs" },
            ].map(opt => {
              // "Nur Personal" = bestaetigt UND hat Personal (EpiRent-Crew oder manueller Bedarf).
              // "Alle bestaetigten" = bestaetigt (auch ohne Personal-Definition).
              // "Alle Jobs" = alles (inkl. unbestaetigt/Angebote).
              const hasPersonnel = (o) => {
                const pk = o.primary_key;
                const crew = crewData[pk];
                if (crew && crew.length > 0) return true;
                const req = jobReqs[pk];
                return !!(req && (req.count || 0) > 0);
              };
              const count = opt.key === "crew"
                ? orders.filter(o => o.is_confirmed && hasPersonnel(o)).length
                : opt.key === "confirmed"
                  ? orders.filter(o => o.is_confirmed).length
                  : orders.length;
              return (
                <button key={opt.key} onClick={() => setOrderFilter(opt.key)}
                  className={`px-3 py-1.5 transition ${orderFilter === opt.key ? "bg-indigo-600 text-white" : "bg-white text-gray-600 hover:bg-indigo-50"}`}
                  data-testid={`order-filter-${opt.key}`}
                >
                  {opt.label} <span className={`ml-1 text-[10px] ${orderFilter === opt.key ? "text-indigo-200" : "text-gray-400"}`}>({count})</span>
                </button>
              );
            })}
          </div>
        </div>
        <div className="flex gap-2 overflow-x-auto pb-2">
          {orders.filter(o => {
            if (orderFilter === "all") return true;
            if (!o.is_confirmed) return false;
            if (orderFilter === "confirmed") return true;
            // "crew" = bestaetigt + Personal (EpiRent-Crew oder manueller Bedarf)
            const pk = o.primary_key;
            const crew = crewData[pk];
            if (crew && crew.length > 0) return true;
            const req = jobReqs[pk];
            return !!(req && (req.count || 0) > 0);
          }).slice(0, 40).map(o => {
            const pk = o.primary_key;
            const req = jobReqs[pk];
            const crew = crewData[pk];
            const hasCrew = crew && crew.length > 0;
            const assigned = getJobAssignedCount(pk);
            const needed = getJobNeeded(pk);
            const isFull = needed > 0 && assigned >= needed;
            const hasReqs = needed > 0;
            const isSelected = selectedJob?.primary_key === pk;
            // Unbestaetigt = EpiRent-is_confirmed=false. Diese erscheinen
            // nur in 'Alle Jobs' (Filter blockt sie aus den anderen beiden).
            const isUnconfirmed = !o.is_confirmed;
            const pct = needed > 0 ? Math.min(100, Math.round(assigned / needed * 100)) : 0;
            return (
              <div key={pk}
                className={`flex-shrink-0 border-2 rounded-lg px-3 py-2 text-xs cursor-pointer transition-all min-w-[200px] max-w-[260px] ${
                  isSelected ? "border-indigo-500 bg-indigo-50 ring-2 ring-indigo-200" :
                  isFull ? "border-green-400 bg-green-50 hover:border-green-500 shadow-sm shadow-green-100" :
                  hasReqs ? "border-orange-200 bg-white hover:border-orange-300" :
                  isUnconfirmed ? "border-dashed border-gray-300 bg-gray-50/60 hover:border-gray-400 opacity-80" :
                  "border-gray-200 bg-white hover:border-indigo-300 hover:bg-indigo-50/30"
                }`}
                onClick={() => setSelectedJob(isSelected ? null : o)}
                data-testid={`order-${pk}`}
              >
                <div className="flex items-start justify-between gap-1">
                  <div className="min-w-0 flex-1">
                    <p className={`font-semibold truncate ${isUnconfirmed ? "text-gray-600" : "text-gray-900"}`}>
                      {o.event || o.order_no}
                    </p>
                    <p className="text-gray-400 truncate">{o.contact_name}</p>
                  </div>
                  <button
                    onClick={(e) => { e.stopPropagation(); navigate(`/orders/${pk}`); }}
                    className="flex-shrink-0 text-indigo-500 hover:text-indigo-700 hover:bg-indigo-100 rounded p-0.5 transition-colors"
                    title="Auftragsdetails öffnen"
                    data-testid={`open-order-${pk}`}
                  >
                    <ExternalLink className="w-3.5 h-3.5" />
                  </button>
                </div>
                <div className="flex items-center justify-between gap-1">
                  <p className="text-[10px] font-mono text-indigo-600 font-semibold">{o.order_no}</p>
                  {isUnconfirmed && (
                    <span className="text-[9px] bg-gray-200 text-gray-600 px-1.5 py-0.5 rounded-full font-medium" title="Angebot ohne Liefer-Kalkulation (sum_transport=0) - erscheint nur unter 'Alle Jobs'">
                      unbestätigt
                    </span>
                  )}
                </div>
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
                    <div className="flex items-center justify-between gap-2">
                      <p className="font-medium text-gray-900 truncate text-xs">{user.name}</p>
                      {offdayBalances[user.id] !== undefined && (
                        <span className={`text-[10px] font-mono px-1.5 py-0.5 rounded-full flex items-center gap-0.5 ${
                          offdayBalances[user.id] > 0 ? "bg-violet-100 text-violet-700" :
                          offdayBalances[user.id] < 0 ? "bg-rose-100 text-rose-700" :
                          "bg-gray-100 text-gray-400"
                        }`} title="Offday-Saldo" data-testid={`balance-badge-${user.id}`}>
                          <Trees className="w-2.5 h-2.5" />{offdayBalances[user.id]}
                        </span>
                      )}
                    </div>
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
                          selectedJob || copySource ? "hover:bg-indigo-100/50 hover:ring-1 hover:ring-indigo-300 hover:ring-inset" : ""
                        } ${offdayMode ? "hover:bg-violet-100/50 hover:ring-1 hover:ring-violet-300 hover:ring-inset" : ""}`}
                        onClick={() => !absence && !isEditing && handleCellClick(user.id, date)}
                      >
                        {absence && (() => {
                          const a = absenceLabel(absence.type);
                          const Icon = a.icon;
                          return <div className={`rounded-md px-2 py-1 mb-1 flex items-center gap-1 ${a.cls}`}><Icon className="w-3 h-3" /><span className="text-[10px] font-medium">{a.text}</span></div>;
                        })()}

                        {cellAssignments.map(asgn => (
                          <div key={asgn.id} className={`border rounded-md px-1.5 py-1 mb-1 relative group/item ${
                            asgn.is_offday ? "bg-violet-50 border-violet-300" :
                            copySource?.id === asgn.id ? "bg-amber-50 border-amber-300 ring-1 ring-amber-200" :
                            "bg-indigo-50 border-indigo-200"
                          }`} data-testid={`asgn-${asgn.id}`}>
                            {asgn.is_offday ? (
                              <p className="text-[10px] font-semibold text-violet-800 flex items-center gap-1"><CalendarCheck2 className="w-3 h-3" /> Offday</p>
                            ) : (
                              <>
                                {asgn.order_name && <p className="text-[10px] font-semibold text-indigo-800 truncate">{asgn.order_name}</p>}
                                {asgn.role && <p className="text-[10px] text-indigo-600">{asgn.role}</p>}
                                {(asgn.start_time || asgn.end_time) && (
                                  <p className="text-[10px] text-gray-500 flex items-center gap-0.5"><Clock className="w-2.5 h-2.5" /> {asgn.start_time || "?"} – {asgn.end_time || "?"}</p>
                                )}
                                {asgn.note && <p className="text-[10px] text-gray-500 italic truncate">{asgn.note}</p>}
                              </>
                            )}
                            <div className="absolute -top-1 -right-1 flex gap-0.5 opacity-0 group-hover/item:opacity-100 transition-opacity">
                              {!asgn.is_offday && (
                                <button onClick={(e) => { e.stopPropagation(); setCopySource(asgn); setSelectedJob(null); }}
                                  className="w-4 h-4 rounded-full bg-amber-500 text-white flex items-center justify-center" title="Kopieren"
                                  data-testid={`copy-${asgn.id}`}>
                                  <Copy className="w-2.5 h-2.5" />
                                </button>
                              )}
                              <button onClick={(e) => { e.stopPropagation(); deleteAssignment(asgn.id); }}
                                className="w-4 h-4 rounded-full bg-red-500 text-white flex items-center justify-center" title="Löschen">
                                <X className="w-2.5 h-2.5" />
                              </button>
                            </div>
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
                            <label className="flex items-center gap-1.5 text-[11px] text-violet-700 mb-1.5 cursor-pointer select-none">
                              <input type="checkbox" checked={!!editForm.is_offday} onChange={e => setEditForm(f => ({ ...f, is_offday: e.target.checked }))} className="w-3 h-3 accent-violet-600" data-testid="edit-is-offday" />
                              <CalendarCheck2 className="w-3 h-3 text-violet-600" /> Als Offday markieren (-1)
                            </label>
                            {!editForm.is_offday && (
                              <>
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
                              </>
                            )}
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
