import { useState, useEffect, useCallback, useRef } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import api from "../lib/api";
import { toast } from "sonner";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Textarea } from "../components/ui/textarea";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "../components/ui/dialog";
import {
  ArrowLeft, User, Save, Palmtree, TrendingUp,
  Plus, Trash2, CalendarDays, ThermometerSun, ChevronDown, ChevronUp, CalendarOff, Archive,
  Download, StickyNote, Eye, FileText, Heart, FileDown, Coffee, Clock, X,
  History,
} from "lucide-react";
import { openExternal } from "../lib/openExternal";
import WeeklyScheduleSection from "../components/admin/zeit_detail/WeeklyScheduleSection";
import PayrollSection from "../components/admin/zeit_detail/PayrollSection";
import TravelExpensesSection from "../components/admin/zeit_detail/TravelExpensesSection";
import MonthlyBreakdownSection from "../components/admin/zeit_detail/MonthlyBreakdownSection";
import AuditLogSection from "../components/admin/zeit_detail/AuditLogSection";

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
  const [verbEntries, setVerbEntries] = useState([]);

  const loadVerbEntries = useCallback(async () => {
    if (!userId) return;
    try {
      const res = await api.get(`/verbandsbuch/by-user/${userId}`);
      setVerbEntries(res.data.entries || []);
    } catch { /* silent */ }
  }, [userId]);

  useEffect(() => { loadVerbEntries(); }, [loadVerbEntries]);

  // Audit-Log: protokolliert manuelle Aenderungen an Zeit/Urlaub/HR-Daten
  const [auditOpen, setAuditOpen] = useState(false);
  const [auditEntries, setAuditEntries] = useState([]);
  const [auditLoading, setAuditLoading] = useState(false);
  const loadAuditLog = useCallback(async () => {
    if (!userId) return;
    setAuditLoading(true);
    try {
      const res = await api.get(`/employee/audit-log/${userId}?token=${token}`);
      setAuditEntries(res.data.entries || []);
    } catch { /* silent */ } finally { setAuditLoading(false); }
  }, [userId, token]);
  // Beim ersten Aufklappen laden
  useEffect(() => { if (auditOpen) loadAuditLog(); }, [auditOpen, loadAuditLog]);

  const handleVerbPdf = async (entryId, lfdNr, eventDate) => {
    try {
      const t = localStorage.getItem("token");
      const resp = await fetch(`${process.env.REACT_APP_BACKEND_URL}/api/verbandsbuch/${entryId}/pdf`, {
        headers: { Authorization: `Bearer ${t}` },
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `Verbandsbuch_Nr${String(lfdNr).padStart(4, "0")}_${eventDate}.pdf`;
      document.body.appendChild(a); a.click(); a.remove();
      URL.revokeObjectURL(url);
    } catch { toast.error("PDF-Download fehlgeschlagen"); }
  };
  const [overtimeHours, setOvertimeHours] = useState("");
  const [vacationTotal, setVacationTotal] = useState("");
  const [dateOfBirth, setDateOfBirth] = useState("");
  const [hrData, setHrData] = useState(null);
  const [saving, setSaving] = useState(false);

  // Vacation entries
  const [vacationEntries, setVacationEntries] = useState([]);
  const [vacStart, setVacStart] = useState("");
  const [vacEnd, setVacEnd] = useState("");
  const [vacType, setVacType] = useState("urlaub"); // "urlaub" | "ueberstundenabbau" | "krank"
  const [addingVac, setAddingVac] = useState(false);
  // iOS-Fix: refs auf vacStart/vacEnd, damit addVacation nach blur den letzten Wert sieht
  const vacStartRef = useRef("");
  const vacEndRef = useRef("");
  vacStartRef.current = vacStart;
  vacEndRef.current = vacEnd;

  // Manual time entry editing (must be declared before any early return — rules-of-hooks)
  const [addRow, setAddRow] = useState({});
  const [addingRow, setAddingRow] = useState(null);
  const [editEntryId, setEditEntryId] = useState(null);
  const [editDraft, setEditDraft] = useState({ date: "", start: "", end: "", break_min: 0, note: "" });

  // iOS-Fix: Ref auf den aktuellen addRow-State, damit submitAddRow nach blur den
  // letzten Wert sieht (iOS commit-on-blur des Date/Time-Pickers).
  const addRowRef = useRef({});
  addRowRef.current = addRow;
  const editDraftRef = useRef({ date: "", start: "", end: "", break_min: 0, note: "" });
  editDraftRef.current = editDraft;

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
  const [deductions, setDeductions] = useState([]);
  const [newDeduction, setNewDeduction] = useState({ text: "", amount: "" });
  const [releasingPayroll, setReleasingPayroll] = useState(false);
  const [releasedMonths, setReleasedMonths] = useState({});

  // Reisekosten
  const [travelTrips, setTravelTrips] = useState([]);
  const [loadingTravel, setLoadingTravel] = useState(false);

  // Documents
  const DOC_TYPES = [
    { key: "personalausweis", label: "Personalausweis" },
    { key: "fuehrerschein", label: "Führerschein" },
    { key: "fahrerkarte", label: "Fahrerkarte" },
    { key: "erste_hilfe", label: "Erste Hilfe" },
    { key: "sicherheitsunterweisung", label: "Sicherheitsunterweisung" },
    { key: "staplerschein", label: "Staplerschein" },
    { key: "hubarbeitsbuehne", label: "Hubarbeitsbühne" },
    { key: "teleskoplader", label: "Teleskoplader" },
    { key: "baumaschine", label: "Baumaschine" },
    { key: "adr_karte", label: "ADR-Karte" },
    { key: "kranschein", label: "Kranschein" },
  ];
  const [docs, setDocs] = useState([]);
  const [uploadingDoc, setUploadingDoc] = useState(null);
  const [expiryPrompt, setExpiryPrompt] = useState(null);
  const [manualExpiry, setManualExpiry] = useState("");
  const isDocExpired = (d) => d && new Date(d) < new Date();
  const isDocExpiringSoon = (d) => { if (!d) return false; const diff = (new Date(d) - new Date()) / (1000 * 60 * 60 * 24); return diff > 0 && diff <= 60; };

  const loadDocs = useCallback(async () => {
    try {
      const res = await api.get(`/employee/documents?token=${token}&user_id=${userId}`);
      setDocs(res.data || []);
    } catch {}
  }, [token, userId]);
  useEffect(() => { loadDocs(); }, [loadDocs]);

  const handleDocUpload = async (docType, file) => {
    if (!file) return;
    setUploadingDoc(docType);
    try {
      const fd = new FormData();
      fd.append("doc_type", docType);
      fd.append("user_id", userId);
      fd.append("file", file);
      const res = await api.post(`/employee/documents?token=${token}`, fd, { headers: { "Content-Type": "multipart/form-data" } });
      toast.success("Dokument hochgeladen — KI prüft Ablaufdatum...");
      await new Promise(r => setTimeout(r, 5000));
      const docsRes = await api.get(`/employee/documents?token=${token}&user_id=${userId}`);
      setDocs(docsRes.data || []);
      const newDoc = (docsRes.data || []).find(d => d.id === res.data.id);
      if (newDoc && !newDoc.expiry_date) {
        setExpiryPrompt(newDoc);
        setManualExpiry("");
      }
    } catch (err) { toast.error(err.response?.data?.detail || "Fehler beim Hochladen"); }
    setUploadingDoc(null);
  };

  const saveDocExpiry = async () => {
    if (!expiryPrompt || !manualExpiry) { setExpiryPrompt(null); return; }
    try {
      await api.put(`/employee/documents/${expiryPrompt.id}?token=${token}`, { expiry_date: manualExpiry });
      loadDocs();
      toast.success("Ablaufdatum gespeichert");
    } catch { toast.error("Fehler"); }
    setExpiryPrompt(null);
  };

  // Load released payrolls
  const loadReleases = useCallback(async () => {
    try {
      const res = await api.get(`/employee/payroll/${userId}/releases?token=${token}`);
      const map = {};
      (res.data || []).forEach(r => { map[r.month] = r.released_at; });
      setReleasedMonths(map);
    } catch {}
  }, [token, userId]);
  useEffect(() => { loadReleases(); }, [loadReleases]);

  const releasePayroll = async () => {
    if (!payroll || !payrollMonth) return;
    setReleasingPayroll(true);
    try {
      await api.post(`/employee/payroll/${userId}/release?month=${payrollMonth}&token=${token}`);
      toast.success(`Abrechnung ${payrollMonth} freigegeben`);
      loadReleases();
    } catch { toast.error("Fehler bei der Freigabe"); }
    setReleasingPayroll(false);
  };

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
      setDateOfBirth(res.data.date_of_birth || "");
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
    if (!d) return null;
    // Neue Logik: Sollstunden direkt
    if (d.soll_hours != null && d.soll_hours !== "") {
      const h = parseFloat(d.soll_hours);
      return Number.isFinite(h) && h > 0 ? Math.round(h * 60) : null;
    }
    // Rueckwaertskompatibel: alte start/end-Spanne minus Pause
    if (!d.start || !d.end) return null;
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
      const [payRes, dedRes] = await Promise.all([
        api.get(`/employee/payroll/${userId}?month=${payrollMonth}&token=${token}`),
        api.get(`/employee/deductions/${userId}?month=${payrollMonth}&token=${token}`),
      ]);
      setPayroll(payRes.data);
      setDeductions(dedRes.data || []);
    } catch { toast.error("Fehler beim Laden der Lohnabrechnung"); }
    setLoadingPayroll(false);
  }, [token, userId, payrollMonth]);

  const loadTravelTrips = useCallback(async () => {
    if (!payrollMonth) return;
    setLoadingTravel(true);
    try {
      const res = await api.get(`/employee/travel-expenses/user/${userId}?month=${payrollMonth}&token=${token}`);
      setTravelTrips(res.data || []);
    } catch { /* still */ }
    setLoadingTravel(false);
  }, [token, userId, payrollMonth]);

  useEffect(() => { loadTravelTrips(); }, [loadTravelTrips]);

  const approveTrip = async (id) => {
    try {
      await api.patch(`/employee/travel-expenses/${id}/approve?token=${token}`);
      toast.success("Reise genehmigt");
      loadTravelTrips();
      loadPayroll();
    } catch (e) { toast.error(e.response?.data?.detail || "Fehler"); }
  };
  const rejectTrip = async (id) => {
    const reason = prompt("Grund für Ablehnung:");
    if (reason === null) return;
    try {
      await api.patch(`/employee/travel-expenses/${id}/reject?token=${token}`, { reason });
      toast.success("Reise abgelehnt");
      loadTravelTrips();
      loadPayroll();
    } catch (e) { toast.error(e.response?.data?.detail || "Fehler"); }
  };
  const deleteTripAdmin = async (id) => {
    if (!confirm("Reise endgültig löschen?")) return;
    try {
      await api.delete(`/employee/travel-expenses/${id}?token=${token}`);
      toast.success("Gelöscht");
      loadTravelTrips();
      loadPayroll();
    } catch (e) { toast.error(e.response?.data?.detail || "Fehler"); }
  };
  const downloadTripPdf = (id) => {
    openExternal(`${process.env.REACT_APP_BACKEND_URL}/api/employee/travel-expenses/${id}/pdf?token=${token}`);
  };
  const downloadTravelXlsx = () => {
    openExternal(`${process.env.REACT_APP_BACKEND_URL}/api/employee/travel-expenses/summary/${userId}/xlsx?month=${payrollMonth}&token=${token}`);
  };

  const addDeduction = async () => {
    if (!newDeduction.text.trim() || !newDeduction.amount) return toast.error("Text und Betrag erforderlich");
    try {
      await api.post(`/employee/deductions/${userId}?token=${token}`, { ...newDeduction, month: payrollMonth });
      setNewDeduction({ text: "", amount: "" });
      loadPayroll();
    } catch { toast.error("Fehler"); }
  };

  const removeDeduction = async (id) => {
    try {
      await api.delete(`/employee/deductions/entry/${id}?token=${token}`);
      loadPayroll();
    } catch { toast.error("Fehler"); }
  };

  const downloadCsv = async () => {
    const url = `${process.env.REACT_APP_BACKEND_URL}/api/employee/payroll/${userId}/csv?month=${payrollMonth}&token=${token}`;
    openExternal(url);
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
        date_of_birth: dateOfBirth || "",
      });
      setHrData(res.data);
      toast.success("Gespeichert");
    } catch { toast.error("Fehler beim Speichern"); }
    setSaving(false);
  };

  const reloadTimeOff = useCallback(async () => {
    try {
      const r = await api.get(`/employee/time-off?token=${token}&user_id=${userId}`);
      setTimeOffRequests(r.data || []);
    } catch {}
  }, [token, userId]);

  const addVacation = async () => {
    // iOS-Fix: Picker-Commit erzwingen, dann State aus Ref lesen
    if (typeof document !== "undefined" && document.activeElement && typeof document.activeElement.blur === "function") {
      document.activeElement.blur();
    }
    await new Promise(r => setTimeout(r, 60));
    const vStart = vacStartRef.current;
    const vEnd = vacEndRef.current;
    if (!vStart || !vEnd) { toast.error("Bitte Start- und Enddatum wählen"); return; }
    if (vEnd < vStart) { toast.error("Enddatum muss nach Startdatum liegen"); return; }
    setAddingVac(true);
    try {
      if (vacType === "urlaub") {
        await api.post(`/employee/vacation/${userId}?token=${token}`, { start_date: vStart, end_date: vEnd });
        toast.success("Urlaub eingetragen");
        loadVacationEntries();
      } else {
        await api.post(`/employee/time-off/admin-create?token=${token}`, {
          user_id: userId,
          type: vacType,
          start_date: vStart,
          end_date: vEnd,
        });
        toast.success(vacType === "ueberstundenabbau" ? "Überstundenabbau eingetragen" : "Krankheit eingetragen");
        reloadTimeOff();
      }
      setVacStart(""); setVacEnd("");
      loadHrData();
    } catch (e) { toast.error(e.response?.data?.detail || "Fehler"); }
    setAddingVac(false);
  };

  const deleteVacation = async (entryId) => {
    if (!window.confirm("Urlaubseintrag wirklich löschen?")) return;
    try {
      await api.delete(`/employee/vacation/${userId}/${entryId}?token=${token}`);
      toast.success("Urlaub gelöscht");
      loadVacationEntries(); loadHrData();
    } catch { toast.error("Fehler beim Löschen"); }
  };

  const deleteTimeOff = async (entryId, type) => {
    const isOvertime = type === "ueberstundenabbau";
    const msg = isOvertime
      ? "Überstundenabbau wirklich löschen? Die Stunden werden zurück aufs Konto gebucht."
      : "Krankheits-Eintrag wirklich löschen?";
    if (!window.confirm(msg)) return;
    try {
      await api.delete(`/employee/time-off/${entryId}?token=${token}`);
      toast.success("Eintrag gelöscht");
      reloadTimeOff(); loadHrData();
    } catch (e) { toast.error(e.response?.data?.detail || "Fehler beim Löschen"); }
  };

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
  // WICHTIG: Alle Zeiten IMMER in Europe/Berlin anzeigen, unabhaengig von der
  // Browser-Timezone. Sonst driftet die Anzeige um +/-1-2h (Server in UTC,
  // Browser in CEST). Backend speichert echtes UTC, hier nur formatieren.
  const formatTime = (iso) => new Date(iso).toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit", timeZone: "Europe/Berlin" });
  const isoToHHMM = (iso) => iso ? new Date(iso).toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit", hour12: false, timeZone: "Europe/Berlin" }) : "";

  const reloadEntries = async () => {
    try {
      const r = await api.get(`/employee/time/entries?token=${token}&user_id=${userId}&date_from=${year}-01-01&date_to=${year}-12-31`);
      setYearEntries(r.data || []);
    } catch {}
  };

  const startEditEntry = (e) => {
    setEditEntryId(e.id);
    setEditDraft({
      date: e.date || (e.clock_in || "").slice(0, 10),
      start: isoToHHMM(e.clock_in),
      end: isoToHHMM(e.clock_out),
      break_min: Number(e.break_min || 0),
      note: e.manual_note || "",
    });
  };

  const saveEditEntry = async (entryId) => {
    // iOS-Fix: Picker-Commit erzwingen, bevor State gelesen wird
    if (typeof document !== "undefined" && document.activeElement && typeof document.activeElement.blur === "function") {
      document.activeElement.blur();
    }
    await new Promise(r => setTimeout(r, 60));
    const draft = editDraftRef.current;
    if (!draft.start) { toast.error("Startzeit erforderlich"); return; }
    try {
      await api.put(`/employee/time/entries/${entryId}?token=${token}`, {
        date: draft.date,
        clock_in_time: draft.start,
        clock_out_time: draft.end || null,
        break_min: Number(draft.break_min) || 0,
        note: draft.note || "",
      });
      toast.success("Eintrag aktualisiert");
      setEditEntryId(null);
      reloadEntries();
    } catch (err) { toast.error(err.response?.data?.detail || "Fehler beim Speichern"); }
  };

  const deleteEntry = async (entryId) => {
    if (!window.confirm("Diesen Stempel-Eintrag wirklich löschen?")) return;
    try {
      await api.delete(`/employee/time/entries/${entryId}?token=${token}`);
      toast.success("Eintrag gelöscht");
      reloadEntries();
    } catch { toast.error("Fehler beim Löschen"); }
  };

  const updateAddRow = (monthKey, field, value) => {
    setAddRow(prev => ({ ...prev, [monthKey]: { ...(prev[monthKey] || { date: "", start: "", end: "" }), [field]: value } }));
  };

  const submitAddRow = async (monthKey) => {
    // iOS-Fix: erzwinge Commit von noch offenem Date/Time-Picker
    if (typeof document !== "undefined" && document.activeElement && typeof document.activeElement.blur === "function") {
      document.activeElement.blur();
    }
    // Warte einen Tick, damit React den onChange-State aus dem Blur propagiert
    await new Promise(r => setTimeout(r, 60));
    const row = addRowRef.current[monthKey] || {};
    if (!row.date || !row.start) { toast.error("Datum und Startzeit erforderlich"); return; }
    if (!row.date.startsWith(monthKey)) { toast.error(`Datum muss im Monat ${monthKey} liegen`); return; }
    setAddingRow(monthKey);
    try {
      await api.post(`/employee/time/manual?token=${token}`, {
        user_id: userId,
        date: row.date,
        clock_in_time: row.start,
        clock_out_time: row.end || null,
        note: row.note || "Manuell durch Admin erfasst",
      });
      toast.success("Eintrag hinzugefügt");
      setAddRow(prev => ({ ...prev, [monthKey]: { date: "", start: "", end: "", note: "" } }));
      reloadEntries();
    } catch (err) { toast.error(err.response?.data?.detail || "Fehler beim Speichern"); }
    setAddingRow(null);
  };

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
            <Button
              onClick={() => { setAuditOpen(true); setTimeout(() => loadAuditLog(), 50); document.getElementById("audit-section")?.scrollIntoView({ behavior: "smooth", block: "start" }); }}
              size="sm" variant="outline"
              className="text-violet-700 border-violet-300 hover:bg-violet-50"
              data-testid="audit-btn"
            >
              <History className="w-3.5 h-3.5 mr-1.5" /> Protokoll
            </Button>
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
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="text-xs text-gray-500 mb-1 block">Überstunden (Std.)</label>
                  <Input type="number" step="0.5" value={overtimeHours} onChange={e => setOvertimeHours(e.target.value)} data-testid="input-overtime" />
                </div>
                <div>
                  <label className="text-xs text-gray-500 mb-1 block">Urlaubstage (Gesamt/Jahr)</label>
                  <Input type="number" value={vacationTotal} onChange={e => setVacationTotal(e.target.value)} data-testid="input-vacation-total" />
                </div>
                <div className="sm:col-span-2 max-w-xs">
                  <label className="text-xs text-gray-500 mb-1 block">Geburtstag</label>
                  <Input type="date" value={dateOfBirth} onChange={e => setDateOfBirth(e.target.value)} data-testid="input-date-of-birth" />
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

        {/* Dokumente & Zertifikate */}
        <div className="bg-white rounded-xl border border-gray-200 p-4" data-testid="documents-section"
          onDragOver={e => { e.preventDefault(); e.stopPropagation(); }}
          onDrop={e => { e.preventDefault(); e.stopPropagation(); }}
        >
          <div className="flex items-center gap-2 mb-3">
            <FileText className="w-4 h-4 text-fuchsia-600" />
            <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider">Dokumente & Zertifikate</p>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-1.5">
            {DOC_TYPES.map(dt => {
              const activeDoc = docs.find(d => d.doc_type === dt.key && d.status === "active");
              const expired = activeDoc && isDocExpired(activeDoc.expiry_date);
              const expiring = activeDoc && isDocExpiringSoon(activeDoc.expiry_date);
              const isUploading = uploadingDoc === dt.key;
              const inputId = `doc-upload-${dt.key}`;
              return (
                <div key={dt.key}
                  className={`border-2 rounded-lg px-3 py-2.5 flex items-center gap-2 text-xs relative group transition-all ${
                    !activeDoc ? "border-dashed border-gray-300 bg-gray-50/50 hover:border-fuchsia-400 hover:bg-fuchsia-50/30 cursor-pointer" :
                    expired ? "border-red-300 bg-red-50" :
                    expiring ? "border-amber-300 bg-amber-50" :
                    "border-green-200 bg-green-50"
                  }`}
                  data-testid={`doc-${dt.key}`}
                  onClick={() => document.getElementById(inputId)?.click()}
                  onDragEnter={e => { e.preventDefault(); e.stopPropagation(); }}
                  onDragOver={e => { e.preventDefault(); e.stopPropagation(); e.currentTarget.style.borderColor = "#d946ef"; e.currentTarget.style.backgroundColor = "#fdf4ff"; }}
                  onDragLeave={e => { e.stopPropagation(); e.currentTarget.style.borderColor = ""; e.currentTarget.style.backgroundColor = ""; }}
                  onDrop={e => { e.preventDefault(); e.stopPropagation(); e.currentTarget.style.borderColor = ""; e.currentTarget.style.backgroundColor = ""; const f = e.dataTransfer?.files?.[0]; if (f) handleDocUpload(dt.key, f); }}
                >
                  <input type="file" id={inputId} accept="application/pdf,image/*" className="hidden" onChange={e => { if (e.target.files[0]) handleDocUpload(dt.key, e.target.files[0]); e.target.value = ""; }} onClick={e => e.stopPropagation()} />
                  <div className={`w-2 h-2 rounded-full flex-shrink-0 ${
                    !activeDoc ? "bg-gray-300" : expired ? "bg-red-500" : expiring ? "bg-amber-400" : "bg-green-500"
                  }`} />
                  <span className="flex-1 truncate font-medium text-gray-800">{dt.label}</span>
                  {isUploading ? (
                    <span className="text-[10px] text-fuchsia-600 animate-pulse">Hochladen...</span>
                  ) : activeDoc ? (
                    <>
                      <span className={`text-[10px] ${expired ? "text-red-600" : expiring ? "text-amber-600" : "text-green-600"}`}>
                        {activeDoc.expiry_date || "—"}
                      </span>
                      <a href={`${process.env.REACT_APP_BACKEND_URL}/api/employee/documents/${activeDoc.id}/file?token=${token}`} target="_blank" rel="noreferrer" className="text-fuchsia-600 hover:text-fuchsia-700" onClick={e => e.stopPropagation()}>
                        <Eye className="w-3 h-3" />
                      </a>
                    </>
                  ) : (
                    <span className="text-[10px] text-gray-400 group-hover:text-fuchsia-600">Hierher ziehen</span>
                  )}
                </div>
              );
            })}
          </div>
          {expiryPrompt && (
            <div className="mt-3 p-3 bg-amber-50 border border-amber-200 rounded-lg flex items-center gap-2">
              <span className="text-xs text-amber-700">KI konnte kein Ablaufdatum erkennen. Bitte manuell eingeben:</span>
              <Input type="date" value={manualExpiry} onChange={e => setManualExpiry(e.target.value)} className="w-40 h-8 text-xs" />
              <Button size="sm" onClick={saveDocExpiry} className="h-8 text-xs bg-amber-600 hover:bg-amber-700">Speichern</Button>
              <Button size="sm" variant="ghost" onClick={() => setExpiryPrompt(null)} className="h-8 text-xs">Abbrechen</Button>
            </div>
          )}
        </div>

        {/* Verbandsbuch-Einträge */}
        {verbEntries.length > 0 && (
          <div className="bg-white rounded-xl border border-red-200 p-4" data-testid="verbandsbuch-section">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <Heart className="w-4 h-4 text-red-600" />
                <p className="text-[10px] font-semibold text-red-600 uppercase tracking-wider">
                  Verbandsbuch · {verbEntries.length} Eintr{verbEntries.length === 1 ? "ag" : "äge"}
                </p>
              </div>
              <button onClick={() => navigate("/verwaltung/auswertung/verbandsbuch")} className="text-xs text-fuchsia-600 hover:underline" data-testid="verb-open-all">
                Alle anzeigen →
              </button>
            </div>
            <div className="space-y-2">
              {verbEntries.map(e => (
                <div
                  key={e.id}
                  className={`flex items-start gap-3 p-3 rounded-lg border ${e.role === "injured" ? "bg-red-50 border-red-200" : "bg-gray-50 border-gray-200"}`}
                  data-testid={`verb-entry-${e.lfd_nr}`}
                >
                  <div className={`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 ${e.role === "injured" ? "bg-red-600 text-white" : "bg-gray-400 text-white"}`}>
                    <Heart className="w-4 h-4" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-semibold text-gray-900 text-sm">Lfd. Nr. {e.lfd_nr}</span>
                      <span className={`text-[10px] px-2 py-0.5 rounded-full font-semibold ${e.role === "injured" ? "bg-red-600 text-white" : "bg-gray-500 text-white"}`}>
                        {e.role === "injured" ? "Geschädigte/r" : "Meldende/r"}
                      </span>
                      <span className="text-xs text-gray-500">
                        {new Date(e.event_date + "T00:00:00").toLocaleDateString("de-DE")} um {e.event_time}
                      </span>
                    </div>
                    <div className="text-sm text-gray-800 mt-0.5"><b>Ort:</b> {e.location}</div>
                    <div className="text-sm text-gray-700"><b>Hergang:</b> {e.hergang}</div>
                    <div className="text-sm text-gray-700"><b>Verletzung:</b> {e.injury_type}</div>
                  </div>
                  <button
                    onClick={() => handleVerbPdf(e.id, e.lfd_nr, e.event_date)}
                    className="text-gray-500 hover:text-emerald-600 p-1 flex-shrink-0"
                    title="PDF herunterladen"
                    data-testid={`verb-pdf-${e.lfd_nr}`}
                  >
                    <FileDown className="w-4 h-4" />
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Regelarbeitszeit */}
        <WeeklyScheduleSection
          weeklyTotalMin={weeklyTotalMin}
          schedule={schedule}
          calcDayHours={calcDayHours}
          updateDay={updateDay}
          hourlyWage={hourlyWage}
          setHourlyWage={setHourlyWage}
          surcharges={surcharges}
          setSurcharges={setSurcharges}
          saveSchedule={saveSchedule}
          savingSchedule={savingSchedule}
        />

        {/* Payroll / Lohnabrechnung */}
        <PayrollSection
          payrollMonth={payrollMonth}
          setPayrollMonth={setPayrollMonth}
          loadPayroll={loadPayroll}
          loadingPayroll={loadingPayroll}
          payroll={payroll}
          downloadCsv={downloadCsv}
          newDeduction={newDeduction}
          setNewDeduction={setNewDeduction}
          addDeduction={addDeduction}
          removeDeduction={removeDeduction}
          releasePayroll={releasePayroll}
          releasingPayroll={releasingPayroll}
          releasedMonths={releasedMonths}
        />

        {/* Reisekosten / Travel Expenses */}
        <TravelExpensesSection
          payrollMonth={payrollMonth}
          travelTrips={travelTrips}
          loadingTravel={loadingTravel}
          downloadTravelXlsx={downloadTravelXlsx}
          downloadTripPdf={downloadTripPdf}
          approveTrip={approveTrip}
          rejectTrip={rejectTrip}
          deleteTripAdmin={deleteTripAdmin}
        />

        {/* Vacation & Überstundenabbau Entries */}
        <div className="bg-white rounded-xl border border-gray-200 p-4" data-testid="vacation-section">
          <div className="flex items-center gap-2 mb-3">
            <CalendarDays className="w-4 h-4 text-sky-600" />
            <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider">Genehmigte Abwesenheit</p>
          </div>
          <div className="flex flex-wrap items-end gap-3 mb-3 pb-3 border-b border-gray-100">
            <div>
              <label className="text-xs text-gray-500 mb-1 block">Typ</label>
              <select
                value={vacType}
                onChange={e => setVacType(e.target.value)}
                className="border border-gray-200 rounded-lg px-3 py-1.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-sky-400"
                data-testid="vac-type"
              >
                <option value="urlaub">Urlaub</option>
                <option value="ueberstundenabbau">Überstundenabbau</option>
                <option value="krank">Krank</option>
              </select>
            </div>
            <div>
              <label className="text-xs text-gray-500 mb-1 block">Von</label>
              <input type="date" value={vacStart} onChange={e => setVacStart(e.target.value)} className="border border-gray-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-sky-400" data-testid="vac-start" />
            </div>
            <div>
              <label className="text-xs text-gray-500 mb-1 block">Bis</label>
              <input type="date" value={vacEnd} onChange={e => setVacEnd(e.target.value)} className="border border-gray-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-sky-400" data-testid="vac-end" />
            </div>
            <Button
              onClick={addVacation}
              disabled={addingVac}
              size="sm"
              className={vacType === "urlaub" ? "bg-sky-600 hover:bg-sky-700" : vacType === "krank" ? "bg-red-600 hover:bg-red-700" : "bg-amber-600 hover:bg-amber-700"}
              data-testid="add-vacation-btn"
            >
              <Plus className="w-3.5 h-3.5 mr-1" /> Eintragen
            </Button>
          </div>
          {(() => {
            const overtimeEntries = timeOffRequests.filter(r => r.type === "ueberstundenabbau" && r.status === "approved");
            const sickEntries = timeOffRequests.filter(r => r.type === "krank" && r.status === "approved");
            const merged = [
              ...vacationEntries.map(v => ({ ...v, _kind: "urlaub" })),
              ...overtimeEntries.map(o => ({ ...o, _kind: "ueberstundenabbau" })),
              ...sickEntries.map(s => ({ ...s, _kind: "krank" })),
            ].sort((a, b) => (b.start_date || "").localeCompare(a.start_date || ""));
            if (merged.length === 0) {
              return <p className="text-xs text-gray-400">Keine Einträge vorhanden</p>;
            }
            return (
              <div className="space-y-1.5">
                {merged.map(v => {
                  const cfg = v._kind === "ueberstundenabbau"
                    ? { bg: "bg-amber-50", icon: <TrendingUp className="w-4 h-4 text-amber-500 flex-shrink-0" />, badge: "bg-amber-200 text-amber-800", label: "Üb-Abbau", text: "text-amber-700", suffix: ` · ${(v.days * 8).toFixed(0)}h` }
                    : v._kind === "krank"
                      ? { bg: "bg-red-50", icon: <ThermometerSun className="w-4 h-4 text-red-500 flex-shrink-0" />, badge: "bg-red-200 text-red-800", label: "Krank", text: "text-red-700", suffix: "" }
                      : { bg: "bg-sky-50", icon: <CalendarDays className="w-4 h-4 text-sky-500 flex-shrink-0" />, badge: "bg-sky-200 text-sky-800", label: "Urlaub", text: "text-sky-700", suffix: "" };
                  return (
                    <div key={`${v._kind}-${v.id}`} className={`flex items-center gap-3 rounded-lg px-3 py-2 text-sm ${cfg.bg}`} data-testid={`absence-${v._kind}-${v.id}`}>
                      {cfg.icon}
                      <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded-full ${cfg.badge}`}>{cfg.label}</span>
                      <span className="text-gray-700 font-medium">{new Date(v.start_date + "T00:00").toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit", year: "numeric" })}</span>
                      <span className="text-gray-400">—</span>
                      <span className="text-gray-700 font-medium">{new Date(v.end_date + "T00:00").toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit", year: "numeric" })}</span>
                      <span className={`font-bold ml-auto ${cfg.text}`}>{v.days} Tag{v.days === 1 ? "" : "e"}{cfg.suffix}</span>
                      <button
                        onClick={() => v._kind === "urlaub" ? deleteVacation(v.id) : deleteTimeOff(v.id, v._kind)}
                        className="text-gray-400 hover:text-red-500"
                        data-testid={`delete-absence-${v.id}`}
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  );
                })}
              </div>
            );
          })()}
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
        <MonthlyBreakdownSection
          months={months}
          currentMonth={currentMonth}
          expandedMonth={expandedMonth}
          setExpandedMonth={setExpandedMonth}
          getMonthStats={getMonthStats}
          fmtH={fmtH}
          addRow={addRow}
          updateAddRow={updateAddRow}
          submitAddRow={submitAddRow}
          addingRow={addingRow}
          editEntryId={editEntryId}
          setEditEntryId={setEditEntryId}
          editDraft={editDraft}
          setEditDraft={setEditDraft}
          startEditEntry={startEditEntry}
          saveEditEntry={saveEditEntry}
          deleteEntry={deleteEntry}
        />

        {/* Audit-Log (Protokoll der manuellen Aenderungen) */}
        <AuditLogSection
          auditOpen={auditOpen}
          setAuditOpen={setAuditOpen}
          auditEntries={auditEntries}
          auditLoading={auditLoading}
          loadAuditLog={loadAuditLog}
        />
      </div>

      {/* Arbeitszeit-Korrektur Dialog */}
      <Dialog open={!!editEntryId} onOpenChange={(o) => { if (!o) setEditEntryId(null); }}>
        <DialogContent className="sm:max-w-lg" data-testid="edit-time-dialog" aria-describedby="edit-time-desc">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-gray-900">
              <Clock className="w-5 h-5 text-amber-600" /> Arbeitszeit korrigieren
            </DialogTitle>
          </DialogHeader>
          <p id="edit-time-desc" className="sr-only">Datum, Arbeitsbeginn, Arbeitsende und Pausenzeit korrigieren. Zeiten in Europe/Berlin.</p>

          <div className="space-y-4 pt-2">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs text-gray-600 mb-1 block font-medium">Datum</label>
                <Input type="date" value={editDraft.date} onChange={e => setEditDraft(d => ({ ...d, date: e.target.value }))} className="text-sm" data-testid="edit-date" />
              </div>
              <div>
                <label className="text-xs text-gray-600 mb-1 block font-medium flex items-center gap-1">
                  <Coffee className="w-3 h-3 text-sky-500" /> Pause (Min.)
                </label>
                <Input type="number" min="0" max="480" step="5" value={editDraft.break_min} onChange={e => setEditDraft(d => ({ ...d, break_min: e.target.value }))} className="text-sm" data-testid="edit-break-min" placeholder="z.B. 30" />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs text-emerald-600 mb-1 block font-medium">Arbeitsbeginn</label>
                <Input type="time" value={editDraft.start} onChange={e => setEditDraft(d => ({ ...d, start: e.target.value }))} className="text-sm" data-testid="edit-start" />
              </div>
              <div>
                <label className="text-xs text-rose-600 mb-1 block font-medium">Arbeitsende</label>
                <Input type="time" value={editDraft.end} onChange={e => setEditDraft(d => ({ ...d, end: e.target.value }))} className="text-sm" data-testid="edit-end" />
              </div>
            </div>

            <div>
              <label className="text-xs text-gray-600 mb-1 block font-medium">Notiz / Begründung</label>
              <Textarea rows={2} value={editDraft.note} onChange={e => setEditDraft(d => ({ ...d, note: e.target.value }))} placeholder="z.B. Vergessen einzustempeln, manuell nachgetragen..." className="text-sm" data-testid="edit-note" />
            </div>

            {(() => {
              const start = editDraft.start; const end = editDraft.end;
              if (!start || !end) return null;
              const [sh, sm] = start.split(":").map(Number);
              const [eh, em] = end.split(":").map(Number);
              const raw = (eh * 60 + em) - (sh * 60 + sm);
              if (raw <= 0) return <p className="text-xs text-rose-600">Endzeit muss nach Startzeit liegen.</p>;
              const legal = raw > 540 ? 45 : raw > 360 ? 30 : 0;
              const brk = Math.max(Number(editDraft.break_min) || 0, legal);
              const net = raw - (brk < raw ? brk : 0);
              return (
                <div className="bg-gray-50 border border-gray-200 rounded-lg px-3 py-2 text-xs text-gray-700 flex items-center gap-3 flex-wrap" data-testid="edit-preview">
                  <span>Anwesenheit: <strong>{fmtH(raw)}</strong></span>
                  <span className="text-gray-300">·</span>
                  <span>Pause: <strong>{brk} min</strong>{legal > 0 && brk === legal && Number(editDraft.break_min) < legal && <span className="text-amber-600"> (gesetzl. Min.)</span>}</span>
                  <span className="text-gray-300">·</span>
                  <span>Arbeitszeit: <strong className="text-emerald-700">{fmtH(net)}</strong></span>
                </div>
              );
            })()}

            <div className="flex gap-2 pt-2">
              <Button onClick={() => saveEditEntry(editEntryId)} className="flex-1 bg-emerald-600 hover:bg-emerald-700" data-testid="edit-save">
                <Save className="w-4 h-4 mr-2" /> Speichern
              </Button>
              <Button variant="outline" onClick={() => setEditEntryId(null)} data-testid="edit-cancel">
                <X className="w-4 h-4 mr-2" /> Abbrechen
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
