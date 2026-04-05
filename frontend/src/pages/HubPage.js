import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import api from "../lib/api";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Logo } from "../components/Logo";
import { toast } from "sonner";
import {
  FolderOpen, Users, LogOut, Activity, Settings, Wrench, Zap,
  ClipboardList, Receipt, Tent, Briefcase, MessageSquare,
  Plus, Check, Calendar, Flag, User, ChevronRight, Trash2, X,
} from "lucide-react";

export default function HubPage() {
  const { user, logout, isAdmin } = useAuth();
  const navigate = useNavigate();
  const token = localStorage.getItem("token");

  const [tasks, setTasks] = useState([]);
  const [taskFilter, setTaskFilter] = useState("mine");
  const [showNewTask, setShowNewTask] = useState(false);
  const [newTask, setNewTask] = useState({ title: "", priority: "medium", due_date: "", assigned_to: [] });
  const [allUsers, setAllUsers] = useState([]);
  const [unreadChats, setUnreadChats] = useState(0);

  const hasFilesharing = isAdmin || user?.apps?.filesharing?.enabled;
  const hasMonitoring = isAdmin || user?.apps?.generator_monitoring?.enabled;
  const hasEnergyMonitoring = isAdmin || user?.apps?.energy_monitoring?.enabled;
  const hasBilling = isAdmin || user?.permissions?.can_billing;
  const isStaff = isAdmin || user?.role === "mitarbeiter";

  const loadTasks = useCallback(async () => {
    try {
      const res = await api.get(`/chat/tasks?token=${token}&filter=${taskFilter}`);
      setTasks(res.data);
    } catch {}
  }, [token, taskFilter]);

  useEffect(() => {
    loadTasks();
    api.get(`/chat/users?token=${token}`).then(r => setAllUsers(r.data)).catch(() => {});
    // Unread chat count
    api.get(`/chat/conversations?token=${token}`).then(r => {
      const total = r.data.reduce((sum, c) => sum + (c.unread_count || 0), 0);
      setUnreadChats(total);
    }).catch(() => {});
  }, [loadTasks, token]);

  const handleLogout = () => { logout(); navigate("/login"); };

  const createTask = async () => {
    if (!newTask.title.trim()) return;
    try {
      const payload = {
        title: newTask.title.trim(),
        priority: newTask.priority,
        due_date: newTask.due_date || null,
        assigned_to: newTask.assigned_to.length > 0 ? newTask.assigned_to : [user.id],
      };
      await api.post(`/chat/tasks?token=${token}`, payload);
      setShowNewTask(false);
      setNewTask({ title: "", priority: "medium", due_date: "", assigned_to: [] });
      loadTasks();
      toast.success("Aufgabe erstellt");
    } catch { toast.error("Fehler"); }
  };

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

  const priorityColor = { high: "text-red-600 bg-red-50", medium: "text-amber-600 bg-amber-50", low: "text-gray-500 bg-gray-100" };
  const priorityLabel = { high: "Hoch", medium: "Mittel", low: "Niedrig" };

  const modules = [
    isStaff && { key: "orders", icon: ClipboardList, label: "Aufträge", path: "/orders", color: "bg-fuchsia-100 text-fuchsia-600" },
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

  const openTasks = tasks.filter(t => !t.completed);
  const doneTasks = tasks.filter(t => t.completed);

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
    <div className="min-h-screen bg-gray-50 flex flex-col" data-testid="hub-page">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 px-4 py-3">
        <div className="max-w-6xl mx-auto flex items-center justify-between">
          <Logo size="normal" />
          <div className="flex items-center gap-3">
            <div className="text-right hidden sm:block">
              <p className="text-sm font-medium text-gray-900">{user?.name}</p>
              <p className="text-xs text-gray-500 capitalize">{user?.role}</p>
            </div>
            <Button variant="outline" size="sm" onClick={handleLogout} className="text-gray-600 hover:text-red-600 hover:border-red-300" data-testid="logout-btn">
              <LogOut className="w-4 h-4 mr-1.5" />
              <span className="hidden sm:inline">Abmelden</span>
            </Button>
          </div>
        </div>
      </header>

      <main className="flex-1 p-4 md:p-6">
        <div className="max-w-6xl mx-auto">
          {/* Top Row: Chat + Quick Actions */}
          <div className="flex items-center justify-between mb-5">
            <h1 className="text-xl font-bold text-gray-900">Willkommen, {user?.name?.split(" ")[0]}!</h1>
            <Button onClick={() => navigate("/chat")} className="bg-fuchsia-600 hover:bg-fuchsia-700 text-white relative" data-testid="open-chat-btn">
              <MessageSquare className="w-4 h-4 mr-2" /> Team Chat
              {unreadChats > 0 && (
                <span className="absolute -top-1.5 -right-1.5 w-5 h-5 rounded-full bg-red-500 text-white text-[10px] flex items-center justify-center">{unreadChats}</span>
              )}
            </Button>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
            {/* Left: Module Grid */}
            <div className="lg:col-span-2">
              <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3" data-testid="modules-grid">
                {modules.map(m => (
                  <button
                    key={m.key}
                    onClick={() => navigate(m.path)}
                    className="bg-white border border-gray-200 rounded-xl p-4 flex flex-col items-center gap-2.5 hover:border-fuchsia-400 hover:shadow-md transition-all group text-center"
                    data-testid={`module-${m.key}`}
                  >
                    <div className={`w-11 h-11 rounded-xl ${m.color} flex items-center justify-center group-hover:scale-110 transition-transform`}>
                      <m.icon className="w-5 h-5" />
                    </div>
                    <span className="text-xs font-medium text-gray-700 leading-tight">{m.label}</span>
                  </button>
                ))}
              </div>
            </div>

            {/* Right: Tasks */}
            <div className="bg-white rounded-xl border border-gray-200 flex flex-col" style={{ maxHeight: "calc(100vh - 180px)" }} data-testid="tasks-panel">
              <div className="px-4 py-3 border-b border-gray-100 flex items-center justify-between">
                <h2 className="text-sm font-semibold text-gray-900">Aufgaben</h2>
                <Button size="sm" onClick={() => setShowNewTask(true)} className="bg-fuchsia-600 hover:bg-fuchsia-700 text-white h-7 text-xs" data-testid="new-task-btn">
                  <Plus className="w-3.5 h-3.5 mr-1" /> Neue Aufgabe
                </Button>
              </div>

              {/* Task Filter */}
              <div className="px-3 py-2 flex gap-1 border-b border-gray-50">
                {[
                  { key: "mine", label: "Meine" },
                  { key: "created", label: "Erstellt" },
                  ...(isAdmin ? [{ key: "all", label: "Alle" }] : []),
                ].map(f => (
                  <button
                    key={f.key}
                    onClick={() => setTaskFilter(f.key)}
                    className={`px-2.5 py-1 rounded-md text-xs font-medium transition-colors ${taskFilter === f.key ? "bg-fuchsia-100 text-fuchsia-700" : "text-gray-500 hover:bg-gray-100"}`}
                    data-testid={`task-filter-${f.key}`}
                  >
                    {f.label}
                  </button>
                ))}
              </div>

              {/* Task List */}
              <div className="flex-1 overflow-y-auto">
                {openTasks.length === 0 && doneTasks.length === 0 ? (
                  <div className="p-6 text-center text-gray-400 text-xs">
                    <Check className="w-8 h-8 mx-auto mb-2 opacity-30" />
                    Keine Aufgaben
                  </div>
                ) : (
                  <div className="divide-y divide-gray-50">
                    {openTasks.map(t => {
                      const due = formatDue(t.due_date);
                      return (
                        <div key={t.id} className="px-3 py-2.5 flex items-start gap-2.5 hover:bg-gray-50 group" data-testid={`task-${t.id}`}>
                          <button onClick={() => toggleTask(t)} className="mt-0.5 w-5 h-5 rounded-full border-2 border-gray-300 hover:border-fuchsia-500 flex-shrink-0 flex items-center justify-center transition-colors" data-testid={`toggle-task-${t.id}`} />
                          <div className="flex-1 min-w-0">
                            <p className="text-sm text-gray-900 leading-tight">{t.title}</p>
                            <div className="flex items-center gap-2 mt-1 flex-wrap">
                              <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${priorityColor[t.priority]}`}>
                                {priorityLabel[t.priority]}
                              </span>
                              {due && <span className={`text-[10px] flex items-center gap-0.5 ${due.cls}`}><Calendar className="w-2.5 h-2.5" />{due.text}</span>}
                              {t.assigned_to !== t.created_by && (
                                <span className="text-[10px] text-gray-400 flex items-center gap-0.5">
                                  <User className="w-2.5 h-2.5" />
                                  {Array.isArray(t.assigned_to)
                                    ? (t.assigned_to.includes(user?.id) && t.created_by !== user?.id
                                        ? `von ${t.created_by_name}`
                                        : Object.values(t.assigned_to_names || {}).join(", "))
                                    : (t.assigned_to === user?.id ? `von ${t.created_by_name}` : `an ${t.assigned_to_name || "?"}`)}
                                </span>
                              )}
                            </div>
                          </div>
                          <button onClick={() => deleteTask(t.id)} className="opacity-0 group-hover:opacity-100 text-gray-400 hover:text-red-500 transition-all" data-testid={`delete-task-${t.id}`}>
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      );
                    })}
                    {doneTasks.length > 0 && (
                      <>
                        <div className="px-3 py-1.5 bg-gray-50">
                          <span className="text-[10px] font-medium text-gray-400 uppercase">Erledigt ({doneTasks.length})</span>
                        </div>
                        {doneTasks.slice(0, 5).map(t => (
                          <div key={t.id} className="px-3 py-2 flex items-center gap-2.5 opacity-60 group" data-testid={`task-done-${t.id}`}>
                            <button onClick={() => toggleTask(t)} className="w-5 h-5 rounded-full bg-fuchsia-600 flex-shrink-0 flex items-center justify-center" data-testid={`untoggle-task-${t.id}`}>
                              <Check className="w-3 h-3 text-white" />
                            </button>
                            <div className="flex-1 min-w-0">
                              <p className="text-sm text-gray-500 line-through truncate">{t.title}</p>
                              {t.completed_by_name && (
                                <p className="text-[10px] text-gray-400">Erledigt von {t.completed_by_name}</p>
                              )}
                            </div>
                            <button onClick={() => deleteTask(t.id)} className="opacity-0 group-hover:opacity-100 text-gray-400 hover:text-red-500"><Trash2 className="w-3.5 h-3.5" /></button>
                          </div>
                        ))}
                      </>
                    )}
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
            </div>

            <Button onClick={createTask} disabled={!newTask.title.trim()} className="w-full bg-fuchsia-600 hover:bg-fuchsia-700 text-white" data-testid="create-task-btn">
              Aufgabe erstellen
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
