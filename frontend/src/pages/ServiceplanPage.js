import { useState, useEffect, useCallback, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { Logo } from "../components/Logo";
import api from "../lib/api";
import { toast } from "sonner";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import {
  ArrowLeft,
  Wrench,
  Plus,
  Search,
  Clock,
  User,
  ChevronLeft,
  Trash2,
  Pencil,
  AlertTriangle,
  CheckCircle,
  X,
  Save,
  Camera,
  Image as ImageIcon,
} from "lucide-react";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

const TYPE_LABELS = {
  stromerzeuger: "Stromerzeuger",
  lichtmast: "Lichtmast",
  messkoffer: "Messkoffer",
  kirmeskiste: "Kirmeskiste",
};

const DEFAULT_TASKS = [
  "Ölwechsel",
  "Ölfilter wechseln",
  "Kraftstofffilter wechseln",
  "Luftfilter wechseln",
  "Kühlmittel prüfen",
  "Keilriemen prüfen",
  "Batterie prüfen",
  "Sichtprüfung Leitungen",
  "Funktionstest",
  "Betriebsstunden dokumentieren",
];

function getServiceStatus(plan) {
  if (!plan || !plan.latest_entry) return { label: "Kein Service", color: "text-gray-400", bg: "bg-gray-100" };
  const lastDate = new Date(plan.latest_entry.performed_at);
  const now = new Date();
  const daysSince = Math.floor((now - lastDate) / (1000 * 60 * 60 * 24));
  const intervalDays = (plan.interval_months || 12) * 30;
  const remaining = intervalDays - daysSince;

  // Also check hours
  const currentHrs = plan.current_hours || 0;
  const lastHrs = plan.latest_entry.hours_at_service || 0;
  const intervalHrs = plan.interval_hours || 500;
  const hrsRemaining = intervalHrs - (currentHrs - lastHrs);

  const isOverdue = remaining < 0 || hrsRemaining < 0;
  const isDueSoon = remaining <= 30 || hrsRemaining <= 50;

  if (isOverdue) return { label: "Überfällig", color: "text-red-600", bg: "bg-red-50", days: remaining, hours: hrsRemaining };
  if (isDueSoon) return { label: "Bald fällig", color: "text-amber-600", bg: "bg-amber-50", days: remaining, hours: hrsRemaining };
  return { label: "OK", color: "text-emerald-600", bg: "bg-emerald-50", days: remaining, hours: hrsRemaining };
}

// ============== Detail View ==============
function ServicePlanDetail({ plan, onBack, onUpdate }) {
  const { isAdmin } = useAuth();
  const [entries, setEntries] = useState([]);
  const [planDetail, setPlanDetail] = useState(plan);
  const [loading, setLoading] = useState(true);
  const [showAddEntry, setShowAddEntry] = useState(false);
  const [editingPlan, setEditingPlan] = useState(false);
  const imageInputRef = useRef(null);
  const [uploadingImages, setUploadingImages] = useState(false);
  const [entryImages, setEntryImages] = useState({});
  const [entryForm, setEntryForm] = useState({
    performed_by: "",
    performed_at: new Date().toISOString().split("T")[0],
    hours_at_service: "",
    tasks_completed: [],
    notes: "",
    remarks: "",
  });
  const [pendingImages, setPendingImages] = useState([]);
  const [planForm, setPlanForm] = useState({
    current_hours: plan.current_hours || 0,
    interval_hours: plan.interval_hours || 500,
    interval_months: plan.interval_months || 12,
    tasks: plan.tasks || [],
    notes: plan.notes || "",
  });
  const [newTask, setNewTask] = useState("");

  const loadDetail = useCallback(async () => {
    try {
      const res = await api.get(`/serviceplan/${plan.id}`);
      setPlanDetail(res.data);
      setEntries(res.data.entries || []);
      // Load images for each entry
      const imgMap = {};
      for (const entry of (res.data.entries || [])) {
        if (entry.images && entry.images.length > 0) {
          imgMap[entry.id] = entry.images;
        }
      }
      setEntryImages(imgMap);
    } catch { toast.error("Fehler beim Laden"); }
    finally { setLoading(false); }
  }, [plan.id]);

  useEffect(() => { loadDetail(); }, [loadDetail]);

  const handleAddEntry = async () => {
    if (!entryForm.performed_by.trim()) { toast.error("Durchgeführt von ist erforderlich"); return; }
    try {
      const res = await api.post(`/serviceplan/${plan.id}/entries`, {
        ...entryForm,
        hours_at_service: entryForm.hours_at_service ? parseFloat(entryForm.hours_at_service) : null,
      });
      const entryId = res.data.id;
      // Upload pending images
      if (pendingImages.length > 0) {
        setUploadingImages(true);
        for (const img of pendingImages) {
          const formData = new FormData();
          formData.append("file", img);
          await api.post(`/serviceplan/${plan.id}/entries/${entryId}/images`, formData, {
            headers: { "Content-Type": "multipart/form-data" },
          });
        }
        setUploadingImages(false);
      }
      toast.success("Wartungseintrag hinzugefügt");
      setShowAddEntry(false);
      setEntryForm({ performed_by: "", performed_at: new Date().toISOString().split("T")[0], hours_at_service: "", tasks_completed: [], notes: "", remarks: "" });
      setPendingImages([]);
      loadDetail();
      onUpdate();
    } catch (err) { toast.error(err.response?.data?.detail || "Fehler"); setUploadingImages(false); }
  };

  const handleDeleteEntry = async (entryId) => {
    try {
      await api.delete(`/serviceplan/${plan.id}/entries/${entryId}`);
      toast.success("Eintrag gelöscht");
      loadDetail();
      onUpdate();
    } catch { toast.error("Fehler"); }
  };

  const handleUpdatePlan = async () => {
    try {
      await api.put(`/serviceplan/${plan.id}`, planForm);
      toast.success("Serviceplan aktualisiert");
      setEditingPlan(false);
      loadDetail();
      onUpdate();
    } catch (err) { toast.error(err.response?.data?.detail || "Fehler"); }
  };

  const toggleTaskCompleted = (task) => {
    setEntryForm(prev => ({
      ...prev,
      tasks_completed: prev.tasks_completed.includes(task)
        ? prev.tasks_completed.filter(t => t !== task)
        : [...prev.tasks_completed, task]
    }));
  };

  const addPlanTask = () => {
    if (!newTask.trim()) return;
    setPlanForm(prev => ({ ...prev, tasks: [...prev.tasks, newTask.trim()] }));
    setNewTask("");
  };

  const removePlanTask = (idx) => {
    setPlanForm(prev => ({ ...prev, tasks: prev.tasks.filter((_, i) => i !== idx) }));
  };

  const handleImageSelect = (e) => {
    const files = Array.from(e.target.files || []);
    setPendingImages(prev => [...prev, ...files]);
  };

  const removePendingImage = (idx) => {
    setPendingImages(prev => prev.filter((_, i) => i !== idx));
  };

  const status = getServiceStatus(planDetail);
  const currentHrs = planDetail.current_hours || 0;
  const lastServiceHrs = planDetail.latest_entry?.hours_at_service || 0;
  const hrsUntilNext = (planDetail.interval_hours || 500) - (currentHrs - lastServiceHrs);

  return (
    <div>
      <button onClick={onBack} className="flex items-center gap-1 text-sm text-gray-500 hover:text-fuchsia-600 mb-4" data-testid="back-to-list">
        <ChevronLeft className="w-4 h-4" /> Zurück zur Übersicht
      </button>

      {/* Device + Plan Header */}
      <div className="bg-white border border-gray-200 rounded-lg p-6 mb-6" data-testid="plan-detail-header">
        <div className="flex items-start justify-between">
          <div>
            <h2 className="text-lg font-semibold text-gray-900">{planDetail.device_serial}</h2>
            <p className="text-sm text-gray-500">{TYPE_LABELS[planDetail.device_type] || planDetail.device_type} · {planDetail.device_model || "–"} · {planDetail.device_user_field || "–"}</p>
          </div>
          <div className={`px-3 py-1 rounded-full text-xs font-medium ${status.bg} ${status.color}`}>
            {status.label}
          </div>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mt-4 pt-4 border-t border-gray-100">
          <div>
            <p className="text-xs text-gray-400">Akt. Betriebsstunden</p>
            <p className="text-sm font-bold text-gray-900">{currentHrs || "–"} h</p>
          </div>
          <div>
            <p className="text-xs text-gray-400">Stunden bis Wartung</p>
            <p className={`text-sm font-bold ${hrsUntilNext <= 50 ? "text-amber-600" : hrsUntilNext <= 0 ? "text-red-600" : "text-gray-900"}`}>
              {planDetail.latest_entry ? `${hrsUntilNext} h` : "–"}
            </p>
          </div>
          <div>
            <p className="text-xs text-gray-400">Intervall</p>
            <p className="text-sm font-medium text-gray-900">{planDetail.interval_hours || "–"} h / {planDetail.interval_months || "–"} Mon.</p>
          </div>
          <div>
            <p className="text-xs text-gray-400">Letzter Service</p>
            <p className="text-sm font-medium text-gray-900">
              {planDetail.latest_entry ? new Date(planDetail.latest_entry.performed_at).toLocaleDateString("de-DE") : "–"}
            </p>
          </div>
        </div>

        <div className="flex gap-2 mt-4">
          <Button size="sm" onClick={() => setEditingPlan(!editingPlan)} variant="outline" className="text-gray-600" data-testid="edit-plan-btn">
            <Pencil className="w-3.5 h-3.5 mr-1" /> Plan bearbeiten
          </Button>
        </div>
      </div>

      {/* Edit Plan Form */}
      {editingPlan && (
        <div className="bg-white border border-fuchsia-200 rounded-lg p-6 mb-6" data-testid="edit-plan-form">
          <h3 className="text-sm font-semibold text-gray-900 mb-4">Serviceplan bearbeiten</h3>
          <div className="grid grid-cols-3 gap-4 mb-4">
            <div>
              <Label className="text-gray-700 text-sm">Akt. Betriebsstunden</Label>
              <Input type="number" value={planForm.current_hours} onChange={e => setPlanForm(p => ({ ...p, current_hours: parseFloat(e.target.value) || 0 }))} className="mt-1" data-testid="edit-current-hours" />
            </div>
            <div>
              <Label className="text-gray-700 text-sm">Intervall (Stunden)</Label>
              <Input type="number" value={planForm.interval_hours} onChange={e => setPlanForm(p => ({ ...p, interval_hours: parseInt(e.target.value) || 0 }))} className="mt-1" data-testid="edit-interval-hours" />
            </div>
            <div>
              <Label className="text-gray-700 text-sm">Intervall (Monate)</Label>
              <Input type="number" value={planForm.interval_months} onChange={e => setPlanForm(p => ({ ...p, interval_months: parseInt(e.target.value) || 0 }))} className="mt-1" data-testid="edit-interval-months" />
            </div>
          </div>

          <div className="mb-4">
            <Label className="text-gray-700 text-sm mb-2 block">Wartungsaufgaben (Checkliste)</Label>
            <div className="space-y-1 mb-2">
              {planForm.tasks.map((task, idx) => (
                <div key={idx} className="flex items-center gap-2 bg-gray-50 rounded px-3 py-1.5">
                  <span className="text-sm text-gray-700 flex-1">{task}</span>
                  <button onClick={() => removePlanTask(idx)} className="text-gray-400 hover:text-red-500"><X className="w-3.5 h-3.5" /></button>
                </div>
              ))}
            </div>
            <div className="flex gap-2">
              <Input value={newTask} onChange={e => setNewTask(e.target.value)} placeholder="Neue Aufgabe..." className="text-sm" onKeyDown={e => e.key === "Enter" && (e.preventDefault(), addPlanTask())} data-testid="new-task-input" />
              <Button size="sm" variant="outline" onClick={addPlanTask}>Hinzufügen</Button>
            </div>
          </div>

          <div className="flex gap-2">
            <Button size="sm" onClick={handleUpdatePlan} className="bg-fuchsia-600 hover:bg-fuchsia-700 text-white" data-testid="save-plan-btn">
              <Save className="w-3.5 h-3.5 mr-1" /> Speichern
            </Button>
            <Button size="sm" variant="outline" onClick={() => setEditingPlan(false)}>Abbrechen</Button>
          </div>
        </div>
      )}

      {/* Add Entry */}
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-base font-semibold text-gray-900">Wartungshistorie</h3>
        <Button size="sm" onClick={() => setShowAddEntry(!showAddEntry)} className="bg-fuchsia-600 hover:bg-fuchsia-700 text-white" data-testid="add-entry-btn">
          <Plus className="w-3.5 h-3.5 mr-1" /> Neue Wartung
        </Button>
      </div>

      {/* Add Entry Form */}
      {showAddEntry && (
        <div className="bg-white border border-fuchsia-200 rounded-lg p-6 mb-6" data-testid="add-entry-form">
          <h3 className="text-sm font-semibold text-gray-900 mb-4">Neuer Wartungseintrag</h3>
          <div className="grid grid-cols-2 gap-4 mb-4">
            <div>
              <Label className="text-gray-700 text-sm">Durchgeführt von *</Label>
              <Input value={entryForm.performed_by} onChange={e => setEntryForm(p => ({ ...p, performed_by: e.target.value }))} placeholder="Name des Technikers" className="mt-1" data-testid="entry-performed-by" />
            </div>
            <div>
              <Label className="text-gray-700 text-sm">Datum *</Label>
              <Input type="date" value={entryForm.performed_at} onChange={e => setEntryForm(p => ({ ...p, performed_at: e.target.value }))} className="mt-1" data-testid="entry-date" />
            </div>
            <div>
              <Label className="text-gray-700 text-sm">Betriebsstunden bei Wartung</Label>
              <Input type="number" value={entryForm.hours_at_service} onChange={e => setEntryForm(p => ({ ...p, hours_at_service: e.target.value }))} placeholder="z.B. 4500" className="mt-1" data-testid="entry-hours" />
            </div>
          </div>

          {/* Tasks Checklist */}
          {(planDetail.tasks || []).length > 0 && (
            <div className="mb-4">
              <Label className="text-gray-700 text-sm mb-2 block">Checkliste - Durchgeführte Aufgaben</Label>
              <div className="grid grid-cols-2 gap-1.5">
                {(planDetail.tasks || []).map((task, idx) => {
                  const checked = entryForm.tasks_completed.includes(task);
                  return (
                    <label key={idx} className={`flex items-center gap-2 px-3 py-2 rounded-lg cursor-pointer text-sm transition-colors ${checked ? "bg-fuchsia-50 text-fuchsia-700 border border-fuchsia-200" : "bg-gray-50 text-gray-600 hover:bg-gray-100 border border-transparent"}`}>
                      <input type="checkbox" checked={checked} onChange={() => toggleTaskCompleted(task)} className="rounded border-gray-300 text-fuchsia-600 focus:ring-fuchsia-500" />
                      {task}
                    </label>
                  );
                })}
              </div>
            </div>
          )}

          {/* Remarks (Bemerkungen) */}
          <div className="mb-4">
            <Label className="text-gray-700 text-sm">Bemerkungen / Besondere Vorkommnisse</Label>
            <textarea value={entryForm.remarks} onChange={e => setEntryForm(p => ({ ...p, remarks: e.target.value }))} rows={3} placeholder="Besonderheiten, Auffälligkeiten, Schäden..." className="mt-1 w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:border-fuchsia-500" data-testid="entry-remarks" />
          </div>

          {/* Notes */}
          <div className="mb-4">
            <Label className="text-gray-700 text-sm">Notizen</Label>
            <textarea value={entryForm.notes} onChange={e => setEntryForm(p => ({ ...p, notes: e.target.value }))} rows={2} placeholder="Weitere Hinweise..." className="mt-1 w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:border-fuchsia-500" data-testid="entry-notes" />
          </div>

          {/* Image Upload (mobile friendly) */}
          <div className="mb-4">
            <Label className="text-gray-700 text-sm mb-2 block">Fotos</Label>
            <input
              ref={imageInputRef}
              type="file"
              accept="image/*"
              capture="environment"
              multiple
              className="hidden"
              onChange={handleImageSelect}
              data-testid="entry-image-input"
            />
            <div className="flex flex-wrap gap-2 mb-2">
              {pendingImages.map((img, idx) => (
                <div key={idx} className="relative w-20 h-20 rounded-lg overflow-hidden border border-gray-200">
                  <img src={URL.createObjectURL(img)} alt="" className="w-full h-full object-cover" />
                  <button onClick={() => removePendingImage(idx)} className="absolute top-0.5 right-0.5 w-5 h-5 bg-red-500 text-white rounded-full flex items-center justify-center">
                    <X className="w-3 h-3" />
                  </button>
                </div>
              ))}
              <button
                onClick={() => imageInputRef.current?.click()}
                className="w-20 h-20 rounded-lg border-2 border-dashed border-gray-300 flex flex-col items-center justify-center text-gray-400 hover:border-fuchsia-400 hover:text-fuchsia-500 transition-colors"
                data-testid="add-photo-btn"
              >
                <Camera className="w-5 h-5" />
                <span className="text-[10px] mt-0.5">Foto</span>
              </button>
            </div>
          </div>

          <div className="flex gap-2">
            <Button size="sm" onClick={handleAddEntry} disabled={uploadingImages} className="bg-fuchsia-600 hover:bg-fuchsia-700 text-white" data-testid="save-entry-btn">
              <Save className="w-3.5 h-3.5 mr-1" /> {uploadingImages ? "Bilder werden hochgeladen..." : "Eintrag speichern"}
            </Button>
            <Button size="sm" variant="outline" onClick={() => { setShowAddEntry(false); setPendingImages([]); }}>Abbrechen</Button>
          </div>
        </div>
      )}

      {/* Entries List */}
      {loading ? (
        <p className="text-gray-400 text-center py-8">Laden...</p>
      ) : entries.length === 0 ? (
        <div className="bg-white border border-gray-200 rounded-lg p-8 text-center">
          <Clock className="w-10 h-10 text-gray-300 mx-auto mb-3" />
          <p className="text-gray-500 text-sm">Noch keine Wartungseinträge vorhanden</p>
        </div>
      ) : (
        <div className="space-y-3">
          {entries.map(entry => (
            <div key={entry.id} className="bg-white border border-gray-200 rounded-lg p-4" data-testid={`entry-${entry.id}`}>
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-full bg-fuchsia-100 flex items-center justify-center flex-shrink-0">
                    <User className="w-5 h-5 text-fuchsia-600" />
                  </div>
                  <div>
                    <p className="text-sm font-medium text-gray-900">{entry.performed_by}</p>
                    <p className="text-xs text-gray-400">
                      {new Date(entry.performed_at).toLocaleDateString("de-DE")}
                      {entry.hours_at_service != null && ` · ${entry.hours_at_service} Betriebsstunden`}
                    </p>
                  </div>
                </div>
                {isAdmin && (
                  <button onClick={() => handleDeleteEntry(entry.id)} className="text-gray-400 hover:text-red-500" data-testid={`delete-entry-${entry.id}`}>
                    <Trash2 className="w-4 h-4" />
                  </button>
                )}
              </div>

              {entry.tasks_completed && entry.tasks_completed.length > 0 && (
                <div className="flex flex-wrap gap-1.5 mt-3">
                  {entry.tasks_completed.map((task, i) => (
                    <span key={i} className="inline-flex items-center gap-1 px-2 py-0.5 bg-emerald-50 text-emerald-700 rounded text-[11px]">
                      <CheckCircle className="w-3 h-3" /> {task}
                    </span>
                  ))}
                </div>
              )}

              {entry.remarks && (
                <div className="mt-3 bg-amber-50 border border-amber-200 rounded-lg p-3">
                  <p className="text-xs font-medium text-amber-700 mb-0.5">Bemerkungen</p>
                  <p className="text-xs text-amber-800">{entry.remarks}</p>
                </div>
              )}

              {entry.notes && <p className="text-xs text-gray-500 mt-2">{entry.notes}</p>}

              {/* Entry Images */}
              {entryImages[entry.id] && entryImages[entry.id].length > 0 && (
                <div className="flex flex-wrap gap-2 mt-3">
                  {entryImages[entry.id].map(imgId => (
                    <a key={imgId} href={`${BACKEND_URL}/api/serviceplan/images/${imgId}`} target="_blank" rel="noopener noreferrer" className="block w-16 h-16 rounded-lg overflow-hidden border border-gray-200 hover:border-fuchsia-400 transition-colors">
                      <img src={`${BACKEND_URL}/api/serviceplan/images/${imgId}`} alt="Wartungsbild" className="w-full h-full object-cover" />
                    </a>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ============== Main Page ==============
export default function ServiceplanPage() {
  const navigate = useNavigate();
  const { isAdmin } = useAuth();
  const [devices, setDevices] = useState([]);
  const [plans, setPlans] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [selectedPlan, setSelectedPlan] = useState(null);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [createForm, setCreateForm] = useState({
    device_id: "",
    current_hours: 0,
    interval_hours: 500,
    interval_months: 12,
    tasks: [...DEFAULT_TASKS],
  });

  const loadData = useCallback(async () => {
    try {
      const [devRes, planRes] = await Promise.all([
        api.get("/devices"),
        api.get("/serviceplan"),
      ]);
      setDevices(devRes.data.filter(d => d.status !== "ausser_betrieb"));
      setPlans(planRes.data);
    } catch { toast.error("Fehler beim Laden"); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  const devicesWithPlans = devices.map(d => {
    const plan = plans.find(p => p.device_id === d.id);
    return { ...d, plan };
  });

  const filtered = devicesWithPlans.filter(d => {
    if (!search) return true;
    const q = search.toLowerCase();
    return (d.serial_number || "").toLowerCase().includes(q) ||
      (d.model || "").toLowerCase().includes(q) ||
      (d.user_field || "").toLowerCase().includes(q);
  });

  const handleCreatePlan = async () => {
    if (!createForm.device_id) { toast.error("Bitte Gerät auswählen"); return; }
    try {
      await api.post("/serviceplan", createForm);
      toast.success("Wartungsplan erstellt");
      setShowCreateModal(false);
      loadData();
    } catch (err) { toast.error(err.response?.data?.detail || "Fehler"); }
  };

  const devicesWithoutPlan = devices.filter(d => !plans.some(p => p.device_id === d.id));

  return (
    <div className="min-h-screen bg-gray-50" data-testid="serviceplan-page">
      <header className="sticky top-0 z-10 bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Button variant="ghost" size="sm" onClick={() => navigate("/hub")} className="text-gray-600 hover:text-fuchsia-600" data-testid="back-btn">
              <ArrowLeft className="w-4 h-4 mr-1" /> Zurück
            </Button>
            <div className="h-5 w-px bg-gray-200" />
            <h1 className="text-base font-semibold text-gray-900">Serviceplan</h1>
          </div>
          <div className="flex items-center gap-2">
            {devicesWithoutPlan.length > 0 && (
              <Button size="sm" onClick={() => { setCreateForm({ ...createForm, device_id: "" }); setShowCreateModal(true); }} className="bg-fuchsia-600 hover:bg-fuchsia-700 text-white" data-testid="new-plan-btn">
                <Plus className="w-4 h-4 mr-1" /> Neue Wartung
              </Button>
            )}
            <Logo size="small" />
          </div>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-4 py-6">
        {selectedPlan ? (
          <ServicePlanDetail
            plan={selectedPlan}
            onBack={() => { setSelectedPlan(null); loadData(); }}
            onUpdate={loadData}
          />
        ) : (
          <>
            {/* Search */}
            <div className="mb-6">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                <input
                  type="text"
                  placeholder="Gerät suchen (Seriennummer, Modell, Bezeichnung)..."
                  value={search}
                  onChange={e => setSearch(e.target.value)}
                  className="w-full pl-10 pr-4 py-2.5 bg-white border border-gray-200 rounded-lg text-sm text-gray-900 placeholder-gray-400 focus:outline-none focus:border-fuchsia-500"
                  data-testid="service-search"
                />
              </div>
            </div>

            {/* Stats */}
            {plans.length > 0 && (
              <div className="grid grid-cols-3 gap-3 mb-6">
                <div className="bg-white border border-gray-200 rounded-lg p-4 text-center">
                  <p className="text-2xl font-bold text-gray-900">{plans.length}</p>
                  <p className="text-xs text-gray-500">Wartungspläne</p>
                </div>
                <div className="bg-white border border-gray-200 rounded-lg p-4 text-center">
                  <p className="text-2xl font-bold text-amber-600">
                    {plans.filter(p => { const s = getServiceStatus(p); return s.label === "Bald fällig"; }).length}
                  </p>
                  <p className="text-xs text-gray-500">Bald fällig</p>
                </div>
                <div className="bg-white border border-gray-200 rounded-lg p-4 text-center">
                  <p className="text-2xl font-bold text-red-600">
                    {plans.filter(p => { const s = getServiceStatus(p); return s.label === "Überfällig"; }).length}
                  </p>
                  <p className="text-xs text-gray-500">Überfällig</p>
                </div>
              </div>
            )}

            {/* Device List */}
            {loading ? (
              <div className="text-center py-20 text-gray-400">Laden...</div>
            ) : filtered.length === 0 ? (
              <div className="text-center py-16">
                <Wrench className="w-12 h-12 text-gray-300 mx-auto mb-4" />
                <p className="text-gray-500">{devices.length === 0 ? "Keine aktiven Geräte vorhanden" : "Keine Treffer"}</p>
              </div>
            ) : (
              <div className="space-y-2" data-testid="device-plan-list">
                {filtered.map(d => {
                  const status = d.plan ? getServiceStatus(d.plan) : null;
                  const hasImage = d.image_gridfs_id;
                  return (
                    <button
                      key={d.id}
                      className="w-full flex items-center justify-between p-4 bg-white border border-gray-200 rounded-lg hover:border-fuchsia-400 hover:shadow-sm transition-all text-left group"
                      data-testid={`sp-device-${d.serial_number}`}
                      onClick={() => {
                        if (d.plan) {
                          setSelectedPlan(d.plan);
                        } else {
                          setCreateForm({ ...createForm, device_id: d.id });
                          setShowCreateModal(true);
                        }
                      }}
                    >
                      <div className="flex items-center gap-4">
                        {hasImage ? (
                          <img src={`${BACKEND_URL}/api/devices/${d.id}/image`} alt="" className="w-10 h-10 rounded-lg object-cover flex-shrink-0 border border-gray-200" />
                        ) : (
                          <div className={`w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0 ${d.plan ? status.bg : "bg-gray-100"}`}>
                            {d.plan ? (
                              status.label === "Überfällig" ? (
                                <AlertTriangle className={`w-5 h-5 ${status.color}`} />
                              ) : (
                                <Wrench className={`w-5 h-5 ${status.color}`} />
                              )
                            ) : (
                              <Plus className="w-5 h-5 text-gray-400" />
                            )}
                          </div>
                        )}
                        <div>
                          <p className="text-sm font-medium text-gray-900">{d.serial_number}</p>
                          <p className="text-xs text-gray-400">{TYPE_LABELS[d.device_type] || d.device_type} · {d.model || "–"} · {d.user_field || "–"}</p>
                        </div>
                      </div>
                      <div className="flex items-center gap-4">
                        {d.plan ? (
                          <div className="text-right">
                            <p className={`text-xs font-medium ${status.color}`}>{status.label}</p>
                            <p className="text-[10px] text-gray-400">
                              {d.plan.latest_entry ? `Letzter Service: ${new Date(d.plan.latest_entry.performed_at).toLocaleDateString("de-DE")}` : "Kein Eintrag"}
                            </p>
                            <p className="text-[10px] text-gray-400">{d.plan.interval_hours}h / {d.plan.interval_months} Mon.</p>
                          </div>
                        ) : (
                          <span className="text-xs text-gray-400">Kein Plan</span>
                        )}
                      </div>
                    </button>
                  );
                })}
              </div>
            )}
          </>
        )}
      </main>

      {/* Create Plan Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center" data-testid="create-plan-modal">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-lg mx-4">
            <div className="flex items-center justify-between p-5 border-b border-gray-200">
              <h2 className="text-lg font-semibold text-gray-900">Neue Wartung anlegen</h2>
              <button onClick={() => setShowCreateModal(false)} className="text-gray-400 hover:text-gray-600"><X className="w-5 h-5" /></button>
            </div>
            <div className="p-5 space-y-4 max-h-[60vh] overflow-y-auto">
              <div>
                <Label className="text-gray-700 text-sm mb-1.5 block">Gerät *</Label>
                <select
                  value={createForm.device_id}
                  onChange={e => setCreateForm(p => ({ ...p, device_id: e.target.value }))}
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:border-fuchsia-500"
                  data-testid="select-device"
                >
                  <option value="">Gerät auswählen...</option>
                  {devicesWithoutPlan.map(d => (
                    <option key={d.id} value={d.id}>{d.serial_number} – {TYPE_LABELS[d.device_type] || d.device_type} ({d.model || "–"})</option>
                  ))}
                </select>
              </div>
              <div>
                <Label className="text-gray-700 text-sm">Aktuelle Betriebsstunden</Label>
                <Input type="number" value={createForm.current_hours} onChange={e => setCreateForm(p => ({ ...p, current_hours: parseFloat(e.target.value) || 0 }))} placeholder="z.B. 3500" className="mt-1" data-testid="create-current-hours" />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label className="text-gray-700 text-sm">Nächste Wartung in (Stunden)</Label>
                  <Input type="number" value={createForm.interval_hours} onChange={e => setCreateForm(p => ({ ...p, interval_hours: parseInt(e.target.value) || 0 }))} className="mt-1" data-testid="create-interval-hours" />
                </div>
                <div>
                  <Label className="text-gray-700 text-sm">Nächste Wartung in (Monate)</Label>
                  <Input type="number" value={createForm.interval_months} onChange={e => setCreateForm(p => ({ ...p, interval_months: parseInt(e.target.value) || 0 }))} className="mt-1" data-testid="create-interval-months" />
                </div>
              </div>
              <div>
                <Label className="text-gray-700 text-sm mb-2 block">Checkliste (Wartungsaufgaben)</Label>
                <div className="space-y-1">
                  {createForm.tasks.map((task, idx) => (
                    <div key={idx} className="flex items-center gap-2 bg-gray-50 rounded px-3 py-1.5">
                      <span className="text-sm text-gray-700 flex-1">{task}</span>
                      <button onClick={() => setCreateForm(p => ({ ...p, tasks: p.tasks.filter((_, i) => i !== idx) }))} className="text-gray-400 hover:text-red-500"><X className="w-3.5 h-3.5" /></button>
                    </div>
                  ))}
                </div>
              </div>
            </div>
            <div className="flex justify-end gap-3 p-5 border-t border-gray-200">
              <Button variant="outline" onClick={() => setShowCreateModal(false)}>Abbrechen</Button>
              <Button onClick={handleCreatePlan} className="bg-fuchsia-600 hover:bg-fuchsia-700 text-white" data-testid="create-plan-submit">Erstellen</Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
