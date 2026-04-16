import { useState, useEffect, useCallback, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import api, { BACKEND_URL } from "../lib/api";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Logo } from "../components/Logo";
import { toast } from "sonner";
import {
  FolderOpen, Users, LogOut, Activity, Settings, Wrench, Zap,
  ClipboardList, Receipt, Tent, Briefcase, MessageSquare,
  Plus, Check, Calendar, Flag, User, ChevronRight, Trash2, X,
  Paperclip, Send, MessageCircle, Download, Search, Clock,
  Sun, Timer, Palmtree, TrendingUp, CalendarOff, ThumbsUp, ThumbsDown, Undo2, CalendarDays,
} from "lucide-react";
import { SwipeClock } from "../components/SwipeClock";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle,
} from "../components/ui/dialog";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "../components/ui/select";
import { Switch } from "../components/ui/switch";

const API = BACKEND_URL;

export default function HubPage() {
  const { user, logout, isAdmin } = useAuth();
  const navigate = useNavigate();
  const token = localStorage.getItem("token");

  const [tasks, setTasks] = useState([]);
  const [taskFilter, setTaskFilter] = useState("mine");
  const [viewFilter, setViewFilter] = useState("aktuell");
  const [taskSearch, setTaskSearch] = useState("");
  const [showNewTask, setShowNewTask] = useState(false);
  const [myAvatarUrl, setMyAvatarUrl] = useState(null);
  const [clockedIn, setClockedIn] = useState(false);
  const [clockEntry, setClockEntry] = useState(null);
  const [clockLoading, setClockLoading] = useState(false);
  const [elapsedTime, setElapsedTime] = useState("");
  const [recentEntries, setRecentEntries] = useState([]);
  const [hrData, setHrData] = useState(null);

  // Time-off request dialog
  const [showTimeOff, setShowTimeOff] = useState(false);
  const [toType, setToType] = useState("");
  const [toStartDate, setToStartDate] = useState("");
  const [toEndDate, setToEndDate] = useState("");
  const [toAllDay, setToAllDay] = useState(true);
  const [toStartTime, setToStartTime] = useState("");
  const [toEndTime, setToEndTime] = useState("");
  const [toSubmitting, setToSubmitting] = useState(false);
  const [newTask, setNewTask] = useState({ title: "", priority: "medium", due_date: "", assigned_to: [] });
  const [newTaskFile, setNewTaskFile] = useState(null);
  const [allUsers, setAllUsers] = useState([]);
  const [unreadChats, setUnreadChats] = useState(0);
  // Task detail / comments
  const [selectedTask, setSelectedTask] = useState(null);
  const [comments, setComments] = useState([]);
  const [newComment, setNewComment] = useState("");
  const [sendingComment, setSendingComment] = useState(false);
  const commentFileRef = useRef(null);
  const commentsEndRef = useRef(null);
  const taskFileRef = useRef(null);

  const hasFilesharing = isAdmin || user?.apps?.filesharing?.enabled;
  const hasMonitoring = isAdmin || user?.apps?.generator_monitoring?.enabled;
  const hasEnergyMonitoring = isAdmin || user?.apps?.energy_monitoring?.enabled;
  const hasBilling = isAdmin || user?.permissions?.can_billing;
  const isStaff = isAdmin || user?.role === "mitarbeiter";

  // Desktop mode: Electron app shows only module tiles
  const isDesktopMode = new URLSearchParams(window.location.search).get('desktop') === '1';
  const handleModuleClick = (path) => {
    if (window.desktopApp?.openModule) {
      window.desktopApp.openModule(path);
    } else {
      navigate(path);
    }
  };

  const loadTasks = useCallback(async () => {
    try {
      const f = isAdmin ? "all" : "both";
      const res = await api.get(`/chat/tasks?token=${token}&filter=${f}`);
      setTasks(res.data);
    } catch {}
  }, [token, isAdmin]);

  useEffect(() => {
    loadTasks();
    api.get(`/chat/users?token=${token}`).then(r => setAllUsers(r.data)).catch(() => {});
    loadUnreadChats();
    loadClockStatus();
    loadRecentEntries();
    // Load HR data
    api.get(`/employee/hr-data/${user.id}?token=${token}`).then(r => setHrData(r.data)).catch(() => {});
    // Load own avatar
    api.get(`/employee/profile?token=${token}`).then(r => {
      if (r.data.avatar_path) setMyAvatarUrl(`${API}/api/employee/avatar/${r.data.user_id}?token=${token}&_=${r.data.avatar_path}`);
    }).catch(() => {});
    // Poll for updates every 10 seconds
    const poll = setInterval(() => { loadTasks(); loadUnreadChats(); }, 10000);
    return () => clearInterval(poll);
  }, [loadTasks, token]);

  // Clock elapsed timer
  useEffect(() => {
    if (!clockedIn || !clockEntry?.clock_in) return;
    const update = () => {
      const start = new Date(clockEntry.clock_in);
      const now = new Date();
      const diff = Math.floor((now - start) / 1000);
      const h = Math.floor(diff / 3600);
      const m = Math.floor((diff % 3600) / 60);
      const s = diff % 60;
      setElapsedTime(`${String(h).padStart(2,"0")}:${String(m).padStart(2,"0")}:${String(s).padStart(2,"0")}`);
    };
    update();
    const iv = setInterval(update, 1000);
    return () => clearInterval(iv);
  }, [clockedIn, clockEntry]);

  const loadClockStatus = async () => {
    try {
      const res = await api.get(`/employee/time/status?token=${token}`);
      setClockedIn(res.data.clocked_in);
      setClockEntry(res.data.entry);
    } catch {}
  };

  const loadRecentEntries = async () => {
    try {
      const res = await api.get(`/employee/time/entries?token=${token}`);
      setRecentEntries((res.data || []).filter(e => e.clock_out).slice(0, 5));
    } catch {}
  };

  const getGPS = () => new Promise((resolve) => {
    if (!navigator.geolocation) { resolve({ lat: null, lng: null }); return; }
    navigator.geolocation.getCurrentPosition(
      pos => resolve({ lat: pos.coords.latitude, lng: pos.coords.longitude }),
      () => resolve({ lat: null, lng: null }),
      { timeout: 10000, enableHighAccuracy: true }
    );
  });

  // My shift plan (employee view)
  const [myPlan, setMyPlan] = useState([]);
  useEffect(() => {
    api.get(`/employee/shift-plan/my-plan?token=${token}`)
      .then(r => setMyPlan(r.data?.assignments || []))
      .catch(() => {});
  }, [token]);

  const submitTimeOff = async () => {
    if (!toType) { toast.error("Bitte Art auswählen"); return; }
    if (!toStartDate) { toast.error("Bitte Startdatum wählen"); return; }
    if (!toAllDay && (!toStartTime || !toEndTime)) { toast.error("Bitte Uhrzeiten angeben"); return; }
    setToSubmitting(true);
    try {
      await api.post(`/employee/time-off?token=${token}`, {
        type: toType,
        start_date: toStartDate,
        end_date: toEndDate || toStartDate,
        all_day: toAllDay,
        start_time: toAllDay ? null : toStartTime,
        end_time: toAllDay ? null : toEndTime,
      });
      toast.success("Antrag eingereicht");
      setShowTimeOff(false);
      setToType(""); setToStartDate(""); setToEndDate(""); setToAllDay(true); setToStartTime(""); setToEndTime("");
    } catch (e) {
      toast.error(e.response?.data?.detail || "Fehler beim Einreichen");
    }
    setToSubmitting(false);
  };


  const handleSwipeClock = async () => {
    setClockLoading(true);
    const gps = await getGPS();
    try {
      if (clockedIn) {
        await api.post(`/employee/time/clock-out?token=${token}`, gps);
        toast.success("Ausgestempelt");
        setClockedIn(false);
        setClockEntry(null);
        setElapsedTime("");
        loadRecentEntries();
      } else {
        const res = await api.post(`/employee/time/clock-in?token=${token}`, gps);
        toast.success("Eingestempelt");
        setClockedIn(true);
        setClockEntry(res.data);
      }
    } catch (err) { toast.error(err.response?.data?.detail || "Fehler"); }
    setClockLoading(false);
  };

  const loadUnreadChats = () => {
    api.get(`/chat/conversations?token=${token}`).then(r => {
      const total = r.data.reduce((sum, c) => sum + (c.unread_count || 0), 0);
      setUnreadChats(total);
    }).catch(() => {});
  };

  const handleLogout = () => { logout(); navigate("/login"); };

  const createTask = async () => {
    if (!newTask.title.trim()) return;
    try {
      const formData = new FormData();
      formData.append("title", newTask.title.trim());
      formData.append("priority", newTask.priority);
      formData.append("due_date", newTask.due_date || "");
      const assignees = newTask.assigned_to.length > 0 ? newTask.assigned_to : [user.id];
      formData.append("assigned_to", assignees.join(","));
      if (newTaskFile) formData.append("file", newTaskFile);
      await api.post(`/chat/tasks?token=${token}`, formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setShowNewTask(false);
      setNewTask({ title: "", priority: "medium", due_date: "", assigned_to: [] });
      setNewTaskFile(null);
      loadTasks();
      toast.success("Aufgabe erstellt");
    } catch { toast.error("Fehler"); }
  };

  const openTaskDetail = async (task) => {
    setSelectedTask(task);
    try {
      const res = await api.get(`/chat/tasks/${task.id}/comments?token=${token}`);
      setComments(res.data);
      // Mark comments as read - reset unread locally
      if (task.unread_comments > 0 || task.comment_count > 0) {
        setTasks(prev => prev.map(t => t.id === task.id ? { ...t, unread_comments: 0 } : t));
        api.put(`/chat/tasks/${task.id}?token=${token}`, { mark_read: true }).catch(() => {});
      }
    } catch { setComments([]); }
  };

  const sendComment = async (e, file) => {
    e?.preventDefault();
    if (!newComment.trim() && !file) return;
    setSendingComment(true);
    try {
      const formData = new FormData();
      formData.append("text", newComment.trim());
      if (file) formData.append("file", file);
      await api.post(`/chat/tasks/${selectedTask.id}/comments?token=${token}`, formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setNewComment("");
      const res = await api.get(`/chat/tasks/${selectedTask.id}/comments?token=${token}`);
      setComments(res.data);
      loadTasks();
    } catch { toast.error("Fehler beim Senden"); }
    finally { setSendingComment(false); }
  };

  useEffect(() => {
    commentsEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [comments]);

  const toggleTask = async (task) => {
    try {
      await api.put(`/chat/tasks/${task.id}?token=${token}`, { completed: !task.completed });
      loadTasks();
    } catch {}
  };

  const deleteTask = async (taskId) => {
    try {
      await api.delete(`/chat/tasks/${taskId}?token=${token}`);
      loadTasks();
    } catch {}
  };

  const resolveTimeOff = async (task, status) => {
    try {
      await api.put(`/employee/time-off/${task.time_off_request_id}?token=${token}`, { status });
      toast.success(status === "approved" ? "Genehmigt" : status === "rejected" ? "Abgelehnt" : "Zurückgezogen");
      loadTasks();
    } catch { toast.error("Fehler"); }
  };

  const withdrawTimeOff = async (task) => {
    try {
      await api.put(`/employee/time-off/${task.time_off_request_id}?token=${token}`, { status: "withdrawn" });
      toast.success("Antrag zurückgezogen");
      loadTasks();
    } catch { toast.error("Fehler"); }
  };

  const priorityColor = { high: "text-red-600 bg-red-50", medium: "text-amber-600 bg-amber-50", low: "text-gray-500 bg-gray-100" };
  const priorityLabel = { high: "Hoch", medium: "Mittel", low: "Niedrig" };

  const modules = [
    isStaff && { key: "orders", icon: ClipboardList, label: "Aufträge", path: "/orders", color: "bg-fuchsia-100 text-fuchsia-600" },
    isAdmin && { key: "einsatzplanung", icon: CalendarDays, label: "Einsatzplanung", path: "/einsatzplanung", color: "bg-indigo-100 text-indigo-600" },
    isAdmin && { key: "ki-training", icon: Zap, label: "KI-Training", path: "/ki-training", color: "bg-fuchsia-100 text-fuchsia-600" },
    isStaff && { key: "kirmes", icon: Tent, label: "Kirmes", path: "/kirmes", color: "bg-pink-100 text-pink-600" },
    hasBilling && { key: "verwaltung", icon: Briefcase, label: "Verwaltung", path: "/verwaltung", color: "bg-violet-100 text-violet-600" },
    hasMonitoring && { key: "generators", icon: Activity, label: "Power Monitoring", path: "/generators", color: "bg-emerald-100 text-emerald-600" },
    hasEnergyMonitoring && { key: "energy", icon: Zap, label: "Energy Monitoring", path: "/energy-monitoring", color: "bg-yellow-100 text-yellow-700" },
    isStaff && { key: "devices", icon: Settings, label: "Geräte", path: "/devices", color: "bg-slate-100 text-slate-600" },
    hasFilesharing && { key: "fileshare", icon: FolderOpen, label: "FileShare", path: "/fileshare", color: "bg-sky-100 text-sky-600" },
    isStaff && { key: "serviceplan", icon: Wrench, label: "Serviceplan", path: "/serviceplan", color: "bg-orange-100 text-orange-600" },
    isAdmin && { key: "admin", icon: Users, label: "Benutzer", path: "/admin", color: "bg-gray-100 text-gray-600" },
    isAdmin && { key: "settings", icon: Settings, label: "Einstellungen", path: "/admin/settings", color: "bg-gray-100 text-gray-600" },
  ].filter(Boolean);

  const filteredTasks = tasks.filter(t => {
    const q = taskSearch.toLowerCase().trim();
    if (q && !t.title?.toLowerCase().includes(q)) return false;
    if (viewFilter === "aktuell") return !t.completed;
    if (viewFilter === "erledigt") return t.completed;
    return true;
  });

  const formatDue = (d) => {
    if (!d) return null;
    const date = new Date(d);
    const now = new Date();
    const diff = Math.ceil((date - now) / (1000 * 60 * 60 * 24));
    if (diff < 0) return { text: "Überfällig", cls: "text-red-600" };
    if (diff === 0) return { text: "Heute", cls: "text-amber-600" };
    if (diff === 1) return { text: "Morgen", cls: "text-amber-600" };
    return { text: date.toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit" }), cls: "text-gray-500" };
  };

  return (
    <>
    <div className="min-h-screen bg-gray-50 flex flex-col" data-testid="hub-page">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 px-4 py-3">
        <div className="max-w-6xl mx-auto flex items-center justify-between">
          <Logo size="normal" />
          <div className="flex items-center gap-3">
            <button onClick={() => navigate("/profile")} className="flex items-center gap-2 hover:bg-gray-50 rounded-lg px-2 py-1 transition-colors" data-testid="profile-link">
              <div className="text-right hidden sm:block">
                <p className="text-sm font-medium text-gray-900">{user?.name}</p>
                <p className="text-xs text-gray-500 capitalize">{user?.role}</p>
              </div>
              <div className="w-8 h-8 rounded-full bg-gray-100 flex items-center justify-center overflow-hidden">
                {myAvatarUrl ? <img src={myAvatarUrl} alt="" className="w-full h-full object-cover" /> : <User className="w-4 h-4 text-gray-500" />}
              </div>
            </button>
            <Button variant="outline" size="sm" onClick={handleLogout} className="text-gray-600 hover:text-red-600 hover:border-red-300" data-testid="logout-btn">
              <LogOut className="w-4 h-4 mr-1.5" />
              <span className="hidden sm:inline">Abmelden</span>
            </Button>
          </div>
        </div>
      </header>

      <main className="flex-1 p-3 sm:p-4 md:p-6">
        <div className="max-w-6xl mx-auto">
          {/* Top Row */}
          <div className="flex items-center justify-between mb-5">
            <h1 className="text-lg sm:text-xl font-bold text-gray-900">Willkommen, {user?.name?.split(" ")[0]}!</h1>
          </div>

          {/* Time Clock Section */}
          <div className="mb-5 bg-white rounded-xl border border-gray-200 p-4" data-testid="time-clock-section">
            <div className="flex flex-col lg:flex-row gap-4">
              {/* Left: Slider + Status */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-2">
                  <Clock className={`w-4 h-4 ${clockedIn ? "text-green-600" : "text-gray-400"}`} />
                  <span className={`text-sm font-semibold ${clockedIn ? "text-green-700" : "text-gray-700"}`}>
                    {clockedIn ? "Eingestempelt" : "Nicht eingestempelt"}
                  </span>
                  {clockedIn && elapsedTime && (
                    <span className="text-sm font-mono text-green-600 bg-green-50 px-2 py-0.5 rounded" data-testid="elapsed-time">{elapsedTime}</span>
                  )}
                  {clockedIn && clockEntry?.clock_in && (
                    <span className="text-xs text-gray-500 ml-1">
                      seit {new Date(clockEntry.clock_in).toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" })} Uhr
                    </span>
                  )}
                </div>
                <div className="max-w-[280px]">
                  <SwipeClock clockedIn={clockedIn} onSwipeComplete={handleSwipeClock} disabled={clockLoading} />
                </div>

                {/* Letzte Stempelungen */}
                {recentEntries.length > 0 && (
                  <div className="mt-3" data-testid="recent-entries">
                    <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider mb-1.5">Letzte Stempelungen</p>
                    <div className="space-y-1">
                      {recentEntries.slice(0, 3).map(e => {
                        const cin = new Date(e.clock_in);
                        const cout = new Date(e.clock_out);
                        const mins = e.duration_minutes || 0;
                        const h = Math.floor(mins / 60);
                        const m = Math.round(mins % 60);
                        return (
                          <div key={e.id} className="flex items-center gap-2 text-xs text-gray-600" data-testid={`recent-entry-${e.id}`}>
                            <span className="text-gray-400 w-[68px] flex-shrink-0">
                              {cin.toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit" })}
                            </span>
                            <span className="text-green-600 font-medium">
                              {cin.toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" })}
                            </span>
                            <span className="text-gray-300">&mdash;</span>
                            <span className="text-red-500 font-medium">
                              {cout.toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" })}
                            </span>
                            <span className="text-gray-400 ml-auto">
                              {h > 0 ? `${h}h ${m}m` : `${m}m`}
                            </span>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}
              </div>

              {/* Right: Info Cards */}
              <div className="flex flex-row lg:flex-col gap-3 flex-shrink-0">
                {/* Resturlaubstage */}
                <div className="flex items-center gap-3 bg-sky-50 rounded-lg px-3 py-2.5 min-w-[150px]" data-testid="vacation-card">
                  <div className="w-8 h-8 rounded-lg bg-sky-100 flex items-center justify-center flex-shrink-0">
                    <Palmtree className="w-4 h-4 text-sky-600" />
                  </div>
                  <div>
                    <p className="text-[10px] font-medium text-sky-600 uppercase tracking-wider">Resturlaub</p>
                    <p className="text-lg font-bold text-sky-800 leading-tight" data-testid="vacation-days">{hrData ? hrData.vacation_days_remaining : "--"} <span className="text-xs font-normal text-sky-500">Tage</span></p>
                  </div>
                </div>

                {/* Überstundenkonto */}
                <div className="flex items-center gap-3 bg-amber-50 rounded-lg px-3 py-2.5 min-w-[150px]" data-testid="overtime-card">
                  <div className="w-8 h-8 rounded-lg bg-amber-100 flex items-center justify-center flex-shrink-0">
                    <TrendingUp className="w-4 h-4 text-amber-600" />
                  </div>
                  <div>
                    <p className="text-[10px] font-medium text-amber-600 uppercase tracking-wider">Überstunden</p>
                    <p className="text-lg font-bold text-amber-800 leading-tight" data-testid="overtime-hours">{hrData ? hrData.overtime_hours : "--"} <span className="text-xs font-normal text-amber-500">Std.</span></p>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* My Shift Plan (Employee) */}
          {!isAdmin && (
            <div className="bg-white rounded-xl border border-gray-200 p-4" data-testid="my-shift-plan">
              <div className="flex items-center gap-2 mb-3">
                <CalendarDays className="w-4 h-4 text-indigo-600" />
                <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider">Meine Einsätze</p>
              </div>
              {myPlan.length > 0 ? (
                <div className="space-y-2">
                  {myPlan.map(a => {
                    const d = new Date(a.date + "T00:00:00");
                    const dayName = d.toLocaleDateString("de-DE", { weekday: "short" });
                    const dateStr = d.toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit" });
                    return (
                      <div key={a.id}
                        className={`flex items-center gap-3 bg-indigo-50 border border-indigo-100 rounded-lg px-3 py-2 ${a.order_pk ? "cursor-pointer hover:bg-indigo-100 hover:border-indigo-300 transition-colors" : ""}`}
                        onClick={() => a.order_pk && navigate(`/orders/${a.order_pk}`)}
                        data-testid={`my-plan-${a.id}`}
                      >
                        <div className="text-center min-w-[44px]">
                          <p className="text-[10px] text-indigo-500 font-medium uppercase">{dayName}</p>
                          <p className="text-sm font-bold text-indigo-800">{dateStr}</p>
                        </div>
                        <div className="flex-1 min-w-0">
                          {a.order_name && <p className="text-xs font-semibold text-gray-900 truncate">{a.order_name}</p>}
                          {a.role && <p className="text-[10px] text-indigo-600">{a.role}</p>}
                          {a.note && <p className="text-[10px] text-gray-500 italic truncate">{a.note}</p>}
                          {(a.start_time || a.end_time) && <p className="text-[10px] text-gray-400">{a.start_time || "?"} – {a.end_time || "?"}</p>}
                        </div>
                        {a.order_pk && <ChevronRight className="w-4 h-4 text-indigo-400 flex-shrink-0" />}
                      </div>
                    );
                  })}
                </div>
              ) : (
                <p className="text-xs text-gray-400 text-center py-3">Noch keine Einsätze geplant.</p>
              )}
            </div>
          )}

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            {/* Left: Module Grid */}
            <div className="lg:col-span-2">
              <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-5 gap-2.5" data-testid="modules-grid">
                {/* Chat Tile with unread indicator */}
                <button
                  onClick={() => handleModuleClick("/chat")}
                  className={`relative bg-white border rounded-xl p-3 sm:p-4 flex flex-col items-center gap-2 hover:shadow-md transition-all group text-center ${unreadChats > 0 ? "border-fuchsia-400 ring-2 ring-fuchsia-200" : "border-gray-200 hover:border-fuchsia-400"}`}
                  data-testid="module-chat"
                >
                  <div className={`w-10 h-10 sm:w-11 sm:h-11 rounded-xl flex items-center justify-center group-hover:scale-110 transition-transform ${unreadChats > 0 ? "bg-fuchsia-600 text-white" : "bg-fuchsia-100 text-fuchsia-600"}`}>
                    <MessageSquare className="w-5 h-5" />
                  </div>
                  <span className="text-[11px] sm:text-xs font-medium text-gray-700 leading-tight">Team Chat</span>
                  {unreadChats > 0 && (
                    <span className="absolute -top-1.5 -right-1.5 w-5 h-5 rounded-full bg-red-500 text-white text-[10px] flex items-center justify-center animate-pulse">{unreadChats}</span>
                  )}
                </button>

                {/* Arbeitszeit Tile */}
                <button
                  onClick={() => handleModuleClick("/arbeitszeit")}
                  className="bg-white border border-gray-200 rounded-xl p-3 sm:p-4 flex flex-col items-center gap-2 hover:border-fuchsia-400 hover:shadow-md transition-all group text-center"
                  data-testid="module-arbeitszeit"
                >
                  <div className="w-10 h-10 sm:w-11 sm:h-11 rounded-xl bg-green-100 text-green-600 flex items-center justify-center group-hover:scale-110 transition-transform">
                    <Clock className="w-5 h-5" />
                  </div>
                  <span className="text-[11px] sm:text-xs font-medium text-gray-700 leading-tight">Arbeitszeit</span>
                </button>

                {/* Time Off Request Tile */}
                <button
                  onClick={() => setShowTimeOff(true)}
                  className="bg-white border border-gray-200 rounded-xl p-3 sm:p-4 flex flex-col items-center gap-2 hover:border-orange-400 hover:shadow-md transition-all group text-center"
                  data-testid="module-time-off"
                >
                  <div className="w-10 h-10 sm:w-11 sm:h-11 rounded-xl bg-orange-100 text-orange-600 flex items-center justify-center group-hover:scale-110 transition-transform">
                    <CalendarOff className="w-5 h-5" />
                  </div>
                  <span className="text-[11px] sm:text-xs font-medium text-gray-700 leading-tight">Freie Zeit</span>
                </button>

                {/* Abrechnung Tile */}
                <button
                  onClick={() => handleModuleClick("/abrechnung")}
                  className="bg-white border border-gray-200 rounded-xl p-3 sm:p-4 flex flex-col items-center gap-2 hover:border-emerald-400 hover:shadow-md transition-all group text-center"
                  data-testid="module-abrechnung"
                >
                  <div className="w-10 h-10 sm:w-11 sm:h-11 rounded-xl bg-emerald-100 text-emerald-600 flex items-center justify-center group-hover:scale-110 transition-transform">
                    <Receipt className="w-5 h-5" />
                  </div>
                  <span className="text-[11px] sm:text-xs font-medium text-gray-700 leading-tight">Abrechnung</span>
                </button>

                {modules.map(m => (
                  <button
                    key={m.key}
                    onClick={() => handleModuleClick(m.path)}
                    className="bg-white border border-gray-200 rounded-xl p-3 sm:p-4 flex flex-col items-center gap-2 hover:border-fuchsia-400 hover:shadow-md transition-all group text-center"
                    data-testid={`module-${m.key}`}
                  >
                    <div className={`w-10 h-10 sm:w-11 sm:h-11 rounded-xl ${m.color} flex items-center justify-center group-hover:scale-110 transition-transform`}>
                      <m.icon className="w-5 h-5" />
                    </div>
                    <span className="text-[11px] sm:text-xs font-medium text-gray-700 leading-tight">{m.label}</span>
                  </button>
                ))}
              </div>
            </div>

            {/* Right: Tasks */}
            <div className="bg-white rounded-xl border border-gray-200 flex flex-col max-h-[60vh] lg:max-h-[calc(100vh-180px)]" data-testid="tasks-panel">
              <div className="px-4 py-3 border-b border-gray-100 flex items-center justify-between">
                <h2 className="text-sm font-semibold text-gray-900">Aufgaben</h2>
                <Button size="sm" onClick={() => setShowNewTask(true)} className="bg-fuchsia-600 hover:bg-fuchsia-700 text-white h-7 text-xs" data-testid="new-task-btn">
                  <Plus className="w-3.5 h-3.5 mr-1" /> Neue Aufgabe
                </Button>
              </div>

              {/* Task Filter */}
              <div className="px-3 py-2 flex gap-1 border-b border-gray-50">
                {[
                  { key: "aktuell", label: "Aktuell" },
                  { key: "erledigt", label: "Erledigt" },
                  { key: "alle", label: "Alle" },
                ].map(f => (
                  <button
                    key={f.key}
                    onClick={() => setViewFilter(f.key)}
                    className={`px-2.5 py-1 rounded-md text-xs font-medium transition-colors ${viewFilter === f.key ? "bg-fuchsia-100 text-fuchsia-700" : "text-gray-500 hover:bg-gray-100"}`}
                    data-testid={`task-filter-${f.key}`}
                  >
                    {f.label}
                  </button>
                ))}
              </div>

              {/* Search */}
              <div className="px-3 py-2 border-b border-gray-50">
                <div className="relative">
                  <Search className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-400" />
                  <input
                    value={taskSearch}
                    onChange={e => setTaskSearch(e.target.value)}
                    placeholder="Aufgabe suchen..."
                    className="w-full pl-8 pr-3 py-1.5 text-xs bg-gray-50 border border-gray-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-fuchsia-400 focus:border-fuchsia-400"
                    data-testid="task-search-input"
                  />
                </div>
              </div>

              {/* Task List */}
              <div className="flex-1 overflow-y-auto">
                {filteredTasks.length === 0 ? (
                  <div className="p-6 text-center text-gray-400 text-xs">
                    <Check className="w-8 h-8 mx-auto mb-2 opacity-30" />
                    {taskSearch ? "Keine Ergebnisse" : viewFilter === "erledigt" ? "Keine erledigten Aufgaben" : "Keine Aufgaben"}
                  </div>
                ) : (
                  <div className="divide-y divide-gray-50">
                    {filteredTasks.map(t => {
                      const due = formatDue(t.due_date);
                      const isTimeOff = !!t.time_off_request_id;
                      const isAdmin = user?.role === "admin";
                      const isOwnRequest = t.created_by === user?.id;
                      if (t.completed || (isTimeOff && t.title?.startsWith("["))) {
                        return (
                          <div key={t.id} className="px-3 py-2 flex items-center gap-2.5 opacity-60 group cursor-pointer" data-testid={`task-done-${t.id}`} onClick={() => openTaskDetail(t)}>
                            {isTimeOff ? (
                              <div className="w-5 h-5 rounded-full bg-green-600 flex-shrink-0 flex items-center justify-center">
                                <ThumbsUp className="w-3 h-3 text-white" />
                              </div>
                            ) : (
                              <button onClick={(e) => { e.stopPropagation(); toggleTask(t); }} className="w-5 h-5 rounded-full bg-fuchsia-600 flex-shrink-0 flex items-center justify-center" data-testid={`untoggle-task-${t.id}`}>
                                <Check className="w-3 h-3 text-white" />
                              </button>
                            )}
                            <div className="flex-1 min-w-0">
                              <p className="text-sm text-gray-500 line-through truncate">{t.title}</p>
                              {t.completed_by_name && (
                                <p className="text-[10px] text-gray-400">Erledigt von {t.completed_by_name}</p>
                              )}
                            </div>
                            {!isTimeOff && (
                              <button onClick={(e) => { e.stopPropagation(); deleteTask(t.id); }} className="opacity-0 group-hover:opacity-100 text-gray-400 hover:text-red-500"><Trash2 className="w-3.5 h-3.5" /></button>
                            )}
                          </div>
                        );
                      }
                      return (
                        <div key={t.id} className={`px-3 py-2.5 flex items-start gap-2.5 hover:bg-gray-50 group cursor-pointer ${(t.unread_comments || 0) > 0 ? "border-l-2 border-l-fuchsia-500 bg-fuchsia-50/30" : ""}`} data-testid={`task-${t.id}`} onClick={() => openTaskDetail(t)}>
                          {isTimeOff ? (
                            <div className="flex items-center gap-1.5 flex-shrink-0 mt-0.5">
                              {isAdmin ? (
                                <>
                                  <button onClick={(e) => { e.stopPropagation(); resolveTimeOff(t, "approved"); }} className="px-2 py-1 text-[10px] font-semibold rounded-md bg-green-100 text-green-700 hover:bg-green-200 transition-colors" data-testid={`approve-task-${t.id}`}>
                                    <ThumbsUp className="w-3 h-3 inline mr-0.5 -mt-0.5" />Genehmigt
                                  </button>
                                  <button onClick={(e) => { e.stopPropagation(); resolveTimeOff(t, "rejected"); }} className="px-2 py-1 text-[10px] font-semibold rounded-md bg-red-100 text-red-700 hover:bg-red-200 transition-colors" data-testid={`reject-task-${t.id}`}>
                                    <ThumbsDown className="w-3 h-3 inline mr-0.5 -mt-0.5" />Abgelehnt
                                  </button>
                                </>
                              ) : isOwnRequest ? (
                                <button onClick={(e) => { e.stopPropagation(); withdrawTimeOff(t); }} className="px-2 py-1 text-[10px] font-semibold rounded-md bg-gray-100 text-gray-600 hover:bg-gray-200 transition-colors" data-testid={`withdraw-task-${t.id}`}>
                                  <Undo2 className="w-3 h-3 inline mr-0.5 -mt-0.5" />Zurückziehen
                                </button>
                              ) : (
                                <div className="w-5 h-5 rounded-full border-2 border-amber-400 flex-shrink-0 flex items-center justify-center">
                                  <Clock className="w-3 h-3 text-amber-500" />
                                </div>
                              )}
                            </div>
                          ) : t.task_type === "payment_reminder" ? (
                            <div className="flex items-center gap-1.5 flex-shrink-0 mt-0.5">
                              <button onClick={async (e) => {
                                e.stopPropagation();
                                if (!window.confirm(`Zahlungserinnerung fuer ${t.payment_reminder_invoice_number} an ${t.payment_reminder_email} senden?`)) return;
                                try {
                                  await api.post(`/kirmes/invoices/${t.payment_reminder_invoice_id}/send-reminder`);
                                  toast.success("Zahlungserinnerung gesendet");
                                  loadTasks();
                                } catch { toast.error("Fehler beim Senden"); }
                              }} className="px-2 py-1 text-[10px] font-semibold rounded-md bg-red-100 text-red-700 hover:bg-red-200 transition-colors" data-testid={`send-reminder-${t.id}`}>
                                Mahnung senden
                              </button>
                              <button onClick={(e) => { e.stopPropagation(); toggleTask(t); }} className="px-2 py-1 text-[10px] font-semibold rounded-md bg-gray-100 text-gray-600 hover:bg-gray-200 transition-colors" data-testid={`dismiss-reminder-${t.id}`}>
                                Erledigt
                              </button>
                            </div>
                          ) : (
                            <button onClick={(e) => { e.stopPropagation(); toggleTask(t); }} className="mt-0.5 w-5 h-5 rounded-full border-2 border-gray-300 hover:border-fuchsia-500 flex-shrink-0 flex items-center justify-center transition-colors" data-testid={`toggle-task-${t.id}`} />
                          )}
                          <div className="flex-1 min-w-0">
                            <p className="text-sm text-gray-900 leading-tight">{t.title}</p>
                            <div className="flex items-center gap-2 mt-1 flex-wrap">
                              <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${priorityColor[t.priority]}`}>
                                {priorityLabel[t.priority]}
                              </span>
                              {due && <span className={`text-[10px] flex items-center gap-0.5 ${due.cls}`}><Calendar className="w-2.5 h-2.5" />{due.text}</span>}
                              {t.attachment && <span className="text-[10px] text-gray-400"><Paperclip className="w-2.5 h-2.5 inline" /></span>}
                              {(t.unread_comments || 0) > 0 && (
                                <span className="text-[10px] text-fuchsia-600 font-semibold flex items-center gap-0.5 bg-fuchsia-50 px-1.5 py-0.5 rounded-full animate-pulse">
                                  <MessageCircle className="w-2.5 h-2.5" />{t.unread_comments} neu
                                </span>
                              )}
                              {(t.unread_comments || 0) === 0 && (t.comment_count || 0) > 0 && (
                                <span className="text-[10px] text-gray-400 flex items-center gap-0.5">
                                  <MessageCircle className="w-2.5 h-2.5" />{t.comment_count}
                                </span>
                              )}
                              {t.assigned_to !== t.created_by && (
                                <span className="text-[10px] text-gray-400 flex items-center gap-0.5">
                                  <User className="w-2.5 h-2.5" />
                                  {Array.isArray(t.assigned_to)
                                    ? (t.assigned_to.includes(user?.id) && t.created_by !== user?.id
                                        ? `von ${t.created_by_name || "?"}`
                                        : Object.values(t.assigned_to_names || {}).join(", "))
                                    : (t.assigned_to === user?.id ? `von ${t.created_by_name || "?"}` : `an ${t.assigned_to_name || "?"}`)}
                                </span>
                              )}
                            </div>
                          </div>
                          {!isTimeOff && (
                            <button onClick={(e) => { e.stopPropagation(); deleteTask(t.id); }} className="opacity-0 group-hover:opacity-100 text-gray-400 hover:text-red-500 transition-all" data-testid={`delete-task-${t.id}`}>
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </main>

      <footer className="bg-white border-t border-gray-200 p-3 text-center text-xs text-gray-400">
        &copy; {new Date().getFullYear()} Eventenergie Deutschland GmbH & Co. KG
      </footer>

      {/* New Task Modal */}
      {showNewTask && (
        <div className="fixed inset-0 bg-black/30 z-50 flex items-center justify-center" onClick={() => setShowNewTask(false)}>
          <div className="bg-white rounded-xl shadow-xl w-full max-w-md mx-4 p-5 space-y-4" onClick={e => e.stopPropagation()} data-testid="new-task-modal">
            <div className="flex items-center justify-between">
              <h3 className="font-semibold text-gray-900">Neue Aufgabe</h3>
              <button onClick={() => setShowNewTask(false)} className="text-gray-400 hover:text-gray-600"><X className="w-5 h-5" /></button>
            </div>

            <div className="space-y-3">
              <div>
                <label className="text-xs font-medium text-gray-600 mb-1 block">Titel *</label>
                <Input
                  value={newTask.title}
                  onChange={e => setNewTask(p => ({ ...p, title: e.target.value }))}
                  placeholder="Was muss erledigt werden?"
                  className="text-sm"
                  autoFocus
                  data-testid="task-title-input"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs font-medium text-gray-600 mb-1 block">Priorität</label>
                  <select
                    value={newTask.priority}
                    onChange={e => setNewTask(p => ({ ...p, priority: e.target.value }))}
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm bg-white"
                    data-testid="task-priority-select"
                  >
                    <option value="high">Hoch</option>
                    <option value="medium">Mittel</option>
                    <option value="low">Niedrig</option>
                  </select>
                </div>
                <div>
                  <label className="text-xs font-medium text-gray-600 mb-1 block">Fällig am</label>
                  <Input
                    type="date"
                    value={newTask.due_date}
                    onChange={e => setNewTask(p => ({ ...p, due_date: e.target.value }))}
                    className="text-sm"
                    data-testid="task-due-date-input"
                  />
                </div>
              </div>

              <div>
                <label className="text-xs font-medium text-gray-600 mb-1.5 block">Zuweisen an</label>
                <div className="border border-gray-200 rounded-lg max-h-40 overflow-y-auto divide-y divide-gray-50">
                  {/* Self */}
                  <label className="flex items-center gap-2.5 px-3 py-2 hover:bg-gray-50 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={newTask.assigned_to.length === 0 || newTask.assigned_to.includes(user?.id)}
                      onChange={e => {
                        if (e.target.checked) setNewTask(p => ({ ...p, assigned_to: [...p.assigned_to.filter(x => x !== user?.id), user?.id] }));
                        else setNewTask(p => ({ ...p, assigned_to: p.assigned_to.filter(x => x !== user?.id) }));
                      }}
                      className="rounded border-gray-300 text-fuchsia-600 focus:ring-fuchsia-500"
                      data-testid="task-assign-self"
                    />
                    <span className="text-sm text-gray-900">Mir selbst</span>
                  </label>
                  {allUsers.map(u => (
                    <label key={u.id} className="flex items-center gap-2.5 px-3 py-2 hover:bg-gray-50 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={newTask.assigned_to.includes(u.id)}
                        onChange={e => {
                          if (e.target.checked) setNewTask(p => ({ ...p, assigned_to: [...p.assigned_to, u.id] }));
                          else setNewTask(p => ({ ...p, assigned_to: p.assigned_to.filter(x => x !== u.id) }));
                        }}
                        className="rounded border-gray-300 text-fuchsia-600 focus:ring-fuchsia-500"
                        data-testid={`task-assign-${u.id}`}
                      />
                      <span className="text-sm text-gray-900">{u.name}</span>
                      <span className="text-xs text-gray-400">{u.role}</span>
                    </label>
                  ))}
                </div>
                {newTask.assigned_to.length > 0 && (
                  <p className="text-[10px] text-fuchsia-600 mt-1">{newTask.assigned_to.length} Person(en) ausgewählt</p>
                )}
              </div>
              <div>
                <label className="text-xs font-medium text-gray-600 mb-1.5 block">Dokument anhängen</label>
                <input type="file" ref={taskFileRef} className="hidden" onChange={e => setNewTaskFile(e.target.files[0])} />
                {newTaskFile ? (
                  <div className="flex items-center gap-2 px-3 py-2 border border-gray-200 rounded-lg bg-gray-50 text-sm">
                    <Paperclip className="w-4 h-4 text-gray-400 flex-shrink-0" />
                    <span className="flex-1 truncate text-gray-700">{newTaskFile.name}</span>
                    <button onClick={() => { setNewTaskFile(null); if (taskFileRef.current) taskFileRef.current.value = ""; }} className="text-gray-400 hover:text-red-500"><X className="w-4 h-4" /></button>
                  </div>
                ) : (
                  <div
                    className="border-2 border-dashed border-gray-300 rounded-lg p-4 text-center cursor-pointer hover:border-fuchsia-400 hover:bg-fuchsia-50/30 transition-colors"
                    onClick={() => taskFileRef.current?.click()}
                    onDragOver={e => { e.preventDefault(); e.currentTarget.classList.add("border-fuchsia-500", "bg-fuchsia-50"); }}
                    onDragLeave={e => { e.preventDefault(); e.currentTarget.classList.remove("border-fuchsia-500", "bg-fuchsia-50"); }}
                    onDrop={e => { e.preventDefault(); e.currentTarget.classList.remove("border-fuchsia-500", "bg-fuchsia-50"); if (e.dataTransfer.files[0]) setNewTaskFile(e.dataTransfer.files[0]); }}
                    data-testid="task-drop-zone"
                  >
                    <Paperclip className="w-5 h-5 text-gray-400 mx-auto mb-1" />
                    <p className="text-xs text-gray-500">Datei hierher ziehen oder <span className="text-fuchsia-600 font-medium">klicken</span></p>
                  </div>
                )}
              </div>
            </div>

            <Button onClick={createTask} disabled={!newTask.title.trim()} className="w-full bg-fuchsia-600 hover:bg-fuchsia-700 text-white" data-testid="create-task-btn">
              Aufgabe erstellen
            </Button>
          </div>
        </div>
      )}

      {/* Task Detail Panel (Overlay) */}
      {selectedTask && (
        <>
          <div className="fixed inset-0 bg-black/20 z-40" onClick={() => setSelectedTask(null)} />
          <div className="fixed top-0 right-0 h-full w-full sm:w-[420px] bg-white border-l border-gray-200 z-50 flex flex-col shadow-2xl" data-testid="task-detail-panel" onClick={e => e.stopPropagation()}>
            {/* Header */}
            <div className="px-4 py-3 border-b border-gray-200 flex items-center justify-between flex-shrink-0">
              <h3 className="font-semibold text-gray-900 text-sm truncate flex-1">{selectedTask.title}</h3>
              <button onClick={() => setSelectedTask(null)} className="text-gray-400 hover:text-gray-600 ml-2"><X className="w-5 h-5" /></button>
            </div>

            {/* Task Info */}
            <div className="px-4 py-3 border-b border-gray-100 space-y-2 flex-shrink-0">
              <div className="flex items-center gap-3 flex-wrap">
                <span className={`text-xs px-2 py-0.5 rounded font-medium ${priorityColor[selectedTask.priority]}`}>{priorityLabel[selectedTask.priority]}</span>
                {selectedTask.due_date && <span className="text-xs text-gray-500 flex items-center gap-1"><Calendar className="w-3 h-3" />{new Date(selectedTask.due_date).toLocaleDateString("de-DE")}</span>}
                {selectedTask.completed && <span className="text-xs text-green-600 flex items-center gap-1"><Check className="w-3 h-3" />Erledigt von {selectedTask.completed_by_name}</span>}
              </div>
              <div className="text-xs text-gray-500">
                <span>Erstellt von <strong>{selectedTask.created_by_name}</strong></span>
                {Object.keys(selectedTask.assigned_to_names || {}).length > 0 && (
                  <span> &middot; Zugewiesen: <strong>{Object.values(selectedTask.assigned_to_names).join(", ")}</strong></span>
                )}
              </div>
              {selectedTask.attachment && (
                <a href={`${API}/api/chat/tasks/${selectedTask.id}/file?token=${token}`} target="_blank" rel="noreferrer"
                  className="inline-flex items-center gap-1.5 text-xs text-fuchsia-600 hover:underline bg-fuchsia-50 px-2 py-1 rounded" data-testid="task-attachment-link">
                  <Download className="w-3 h-3" /> {selectedTask.attachment.filename}
                </a>
              )}
            </div>

            {/* Comments Thread */}
            <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3" data-testid="task-comments-area">
              {comments.length === 0 ? (
                <div className="text-center py-8 text-gray-400">
                  <MessageCircle className="w-8 h-8 mx-auto mb-2 opacity-30" />
                  <p className="text-xs">Noch keine Kommentare. Stellen Sie eine Rückfrage!</p>
                </div>
              ) : comments.map(c => {
                const isMine = c.user_id === user?.id;
                const isImage = c.attachment?.content_type?.startsWith("image/");
                return (
                  <div key={c.id} className={`flex ${isMine ? "justify-end" : "justify-start"}`}>
                    <div className={`max-w-[80%] ${isMine ? "" : ""}`}>
                      {!isMine && <span className="text-[10px] text-gray-400 ml-1 block mb-0.5">{c.user_name}</span>}
                      <div className={`rounded-2xl px-3 py-2 ${isMine ? "bg-fuchsia-600 text-white rounded-br-sm" : "bg-gray-100 text-gray-900 rounded-bl-sm"}`}>
                        {c.attachment && (
                          <div className="mb-1">
                            {isImage ? (
                              <img src={`${API}/api/chat/tasks/${selectedTask.id}/comments/${c.id}/file?token=${token}`} alt={c.attachment.filename} className="rounded-lg max-w-full max-h-32" />
                            ) : (
                              <a href={`${API}/api/chat/tasks/${selectedTask.id}/comments/${c.id}/file?token=${token}`} target="_blank" rel="noreferrer"
                                className={`text-xs underline flex items-center gap-1 ${isMine ? "text-white/90" : "text-fuchsia-600"}`}>
                                <Paperclip className="w-3 h-3" /> {c.attachment.filename}
                              </a>
                            )}
                          </div>
                        )}
                        {c.text && <p className="text-sm whitespace-pre-wrap">{c.text}</p>}
                        <span className={`text-[10px] block text-right mt-0.5 ${isMine ? "text-white/50" : "text-gray-400"}`}>
                          {new Date(c.created_at).toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" })}
                        </span>
                      </div>
                    </div>
                  </div>
                );
              })}
              <div ref={commentsEndRef} />
            </div>

            {/* Comment Input */}
            <form onSubmit={e => sendComment(e)} className="border-t border-gray-200 px-3 py-2 flex items-center gap-2 flex-shrink-0" data-testid="comment-input-form">
              <input type="file" ref={commentFileRef} className="hidden" onChange={e => { if (e.target.files[0]) sendComment(null, e.target.files[0]); e.target.value = ""; }} />
              <Button type="button" variant="ghost" size="sm" onClick={() => commentFileRef.current?.click()} className="text-gray-400 hover:text-fuchsia-600 flex-shrink-0" data-testid="comment-attach-btn">
                <Paperclip className="w-4 h-4" />
              </Button>
              <Input
                value={newComment}
                onChange={e => setNewComment(e.target.value)}
                placeholder="Rückfrage oder Kommentar..."
                className="flex-1 border-0 bg-gray-100 focus-visible:ring-0 text-sm"
                data-testid="comment-input"
              />
              <Button type="submit" size="sm" disabled={!newComment.trim() || sendingComment} className="bg-fuchsia-600 hover:bg-fuchsia-700 text-white flex-shrink-0" data-testid="send-comment-btn">
                <Send className="w-4 h-4" />
              </Button>
            </form>
          </div>
        </>
      )}
    </div>

    {/* Time Off Request Dialog */}
    <Dialog open={showTimeOff} onOpenChange={setShowTimeOff}>
      <DialogContent className="sm:max-w-md" data-testid="time-off-dialog">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <CalendarOff className="w-5 h-5 text-orange-600" /> Arbeitsfreie Zeit beantragen
          </DialogTitle>
        </DialogHeader>
        <div className="space-y-4 pt-2">
          <div>
            <label className="text-xs text-gray-500 mb-1 block">Art</label>
            <Select value={toType} onValueChange={setToType}>
              <SelectTrigger data-testid="to-type-select">
                <SelectValue placeholder="Bitte wählen..." />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="krank">Krank</SelectItem>
                <SelectItem value="urlaub">Urlaub</SelectItem>
                <SelectItem value="ueberstundenabbau">Überstundenabbau</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-gray-500 mb-1 block">Von</label>
              <input type="date" value={toStartDate} onChange={e => setToStartDate(e.target.value)} className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-orange-400" data-testid="to-start-date" />
            </div>
            <div>
              <label className="text-xs text-gray-500 mb-1 block">Bis</label>
              <input type="date" value={toEndDate} onChange={e => setToEndDate(e.target.value)} className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-orange-400" data-testid="to-end-date" />
            </div>
          </div>
          <div className="flex items-center justify-between">
            <label className="text-sm text-gray-700">Ganztägig</label>
            <Switch checked={toAllDay} onCheckedChange={setToAllDay} data-testid="to-all-day" />
          </div>
          {!toAllDay && (
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs text-gray-500 mb-1 block">Von (Uhrzeit)</label>
                <input type="time" value={toStartTime} onChange={e => setToStartTime(e.target.value)} className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-orange-400" data-testid="to-start-time" />
              </div>
              <div>
                <label className="text-xs text-gray-500 mb-1 block">Bis (Uhrzeit)</label>
                <input type="time" value={toEndTime} onChange={e => setToEndTime(e.target.value)} className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-orange-400" data-testid="to-end-time" />
              </div>
            </div>
          )}
          <Button onClick={submitTimeOff} disabled={toSubmitting} className="w-full bg-orange-600 hover:bg-orange-700" data-testid="to-submit-btn">
            {toSubmitting ? "Wird eingereicht..." : "Absenden"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
    </>
  );
}
