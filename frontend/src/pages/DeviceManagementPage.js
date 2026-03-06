import { useState, useEffect, useCallback, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { Logo } from "../components/Logo";
import api from "../lib/api";
import { toast } from "sonner";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import {
  ArrowLeft,
  Plus,
  Search,
  Pencil,
  Trash2,
  Copy,
  FileText,
  Upload,
  X,
  Zap,
  Lightbulb,
  Settings,
  ChevronDown,
} from "lucide-react";

const DEVICE_TYPES = [
  { value: "stromerzeuger", label: "Stromerzeuger", icon: Zap },
  { value: "lichtmast", label: "Lichtmast", icon: Lightbulb },
  { value: "messkoffer", label: "Messkoffer", icon: Settings },
  { value: "kirmeskiste", label: "Kirmeskiste", icon: Settings },
];

const TYPE_LABELS = Object.fromEntries(DEVICE_TYPES.map(t => [t.value, t.label]));

const EMPTY_FORM = {
  device_type: "stromerzeuger",
  serial_number: "",
  user_field: "",
  latitude: "",
  longitude: "",
  model: "",
  engine_manufacturer: "",
  engine_type: "",
  engine_number: "",
  generator_manufacturer: "",
  generator_type: "",
  generator_number: "",
  year_of_manufacture: "",
  power_output: "",
  controller: "",
  last_maintenance: "",
  next_maintenance: "",
  notes: "",
};

function DeviceModal({ open, onClose, formData, setFormData, onSave, editing, onCopy }) {
  const fileInputRef = useRef(null);
  const [documents, setDocuments] = useState([]);
  const [uploading, setUploading] = useState(false);

  const isGenerator = formData.device_type === "stromerzeuger" || formData.device_type === "lichtmast";

  const loadDocuments = useCallback(async () => {
    if (!editing) return;
    try {
      const res = await api.get(`/devices/${editing.id}/documents`);
      setDocuments(res.data);
    } catch { setDocuments([]); }
  }, [editing]);

  useEffect(() => { if (open && editing) loadDocuments(); else setDocuments([]); }, [open, editing, loadDocuments]);

  const handleUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file || !editing) return;
    setUploading(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      await api.post(`/devices/${editing.id}/documents`, fd, { headers: { "Content-Type": "multipart/form-data" } });
      toast.success("Dokument hochgeladen");
      loadDocuments();
    } catch { toast.error("Upload fehlgeschlagen"); }
    finally { setUploading(false); if (fileInputRef.current) fileInputRef.current.value = ""; }
  };

  const handleDeleteDoc = async (docId) => {
    if (!editing) return;
    try {
      await api.delete(`/devices/${editing.id}/documents/${docId}`);
      toast.success("Dokument gelöscht");
      loadDocuments();
    } catch { toast.error("Fehler"); }
  };

  const update = (field, value) => setFormData(prev => ({ ...prev, [field]: value }));

  if (!open) return null;

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-start justify-center pt-8 overflow-y-auto">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-2xl mx-4 mb-8" data-testid="device-modal">
        <div className="flex items-center justify-between p-5 border-b border-gray-200">
          <h2 className="text-lg font-semibold text-gray-900">
            {editing ? "Gerät bearbeiten" : "Neues Gerät anlegen"}
          </h2>
          <div className="flex items-center gap-2">
            {editing && (
              <Button variant="outline" size="sm" onClick={() => onCopy(editing.id)} className="text-fuchsia-600" data-testid="copy-device-btn">
                <Copy className="w-4 h-4 mr-1" /> Kopieren
              </Button>
            )}
            <button onClick={onClose} className="text-gray-400 hover:text-gray-600"><X className="w-5 h-5" /></button>
          </div>
        </div>

        <div className="p-5 space-y-5 max-h-[70vh] overflow-y-auto" data-testid="device-form">
          {/* Device Type */}
          <div>
            <Label className="text-gray-700 text-sm mb-1.5 block">Gerätetyp</Label>
            <div className="grid grid-cols-4 gap-2">
              {DEVICE_TYPES.map(t => (
                <button
                  key={t.value}
                  onClick={() => update("device_type", t.value)}
                  className={`p-3 rounded-lg border text-center text-xs font-medium transition-colors ${
                    formData.device_type === t.value
                      ? "border-fuchsia-500 bg-fuchsia-50 text-fuchsia-700"
                      : "border-gray-200 text-gray-500 hover:border-gray-300"
                  }`}
                  data-testid={`type-${t.value}`}
                >
                  <t.icon className="w-5 h-5 mx-auto mb-1" />
                  {t.label}
                </button>
              ))}
            </div>
          </div>

          {/* Common Fields */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label className="text-gray-700 text-sm">Seriennummer *</Label>
              <Input value={formData.serial_number} onChange={e => update("serial_number", e.target.value)} className="mt-1" data-testid="serial-input" />
            </div>
            <div>
              <Label className="text-gray-700 text-sm">Benutzerfeld</Label>
              <Input value={formData.user_field} onChange={e => update("user_field", e.target.value)} placeholder="Freitext (suchbar)" className="mt-1" data-testid="user-field-input" />
            </div>
          </div>

          {/* Generator/Lichtmast specific fields */}
          {isGenerator && (
            <>
              <div className="border-t border-gray-100 pt-4">
                <h3 className="text-sm font-medium text-gray-900 mb-3">Gerätedaten</h3>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <Label className="text-gray-700 text-sm">Modell</Label>
                    <Input value={formData.model} onChange={e => update("model", e.target.value)} className="mt-1" data-testid="model-input" />
                  </div>
                  <div>
                    <Label className="text-gray-700 text-sm">Baujahr</Label>
                    <Input type="number" value={formData.year_of_manufacture} onChange={e => update("year_of_manufacture", e.target.value)} className="mt-1" data-testid="year-input" />
                  </div>
                  <div>
                    <Label className="text-gray-700 text-sm">Leistung</Label>
                    <Input value={formData.power_output} onChange={e => update("power_output", e.target.value)} placeholder="z.B. 400 kVA" className="mt-1" data-testid="power-input" />
                  </div>
                  <div>
                    <Label className="text-gray-700 text-sm">Steuerung</Label>
                    <Input value={formData.controller} onChange={e => update("controller", e.target.value)} placeholder="z.B. DSE8610MK2" className="mt-1" data-testid="controller-input" />
                  </div>
                </div>
              </div>

              <div className="border-t border-gray-100 pt-4">
                <h3 className="text-sm font-medium text-gray-900 mb-3">Motor</h3>
                <div className="grid grid-cols-3 gap-4">
                  <div>
                    <Label className="text-gray-700 text-sm">Hersteller</Label>
                    <Input value={formData.engine_manufacturer} onChange={e => update("engine_manufacturer", e.target.value)} className="mt-1" data-testid="engine-mfr-input" />
                  </div>
                  <div>
                    <Label className="text-gray-700 text-sm">Typ</Label>
                    <Input value={formData.engine_type} onChange={e => update("engine_type", e.target.value)} className="mt-1" data-testid="engine-type-input" />
                  </div>
                  <div>
                    <Label className="text-gray-700 text-sm">Motornummer</Label>
                    <Input value={formData.engine_number} onChange={e => update("engine_number", e.target.value)} className="mt-1" data-testid="engine-num-input" />
                  </div>
                </div>
              </div>

              <div className="border-t border-gray-100 pt-4">
                <h3 className="text-sm font-medium text-gray-900 mb-3">Generator</h3>
                <div className="grid grid-cols-3 gap-4">
                  <div>
                    <Label className="text-gray-700 text-sm">Hersteller</Label>
                    <Input value={formData.generator_manufacturer} onChange={e => update("generator_manufacturer", e.target.value)} className="mt-1" data-testid="gen-mfr-input" />
                  </div>
                  <div>
                    <Label className="text-gray-700 text-sm">Typ</Label>
                    <Input value={formData.generator_type} onChange={e => update("generator_type", e.target.value)} className="mt-1" data-testid="gen-type-input" />
                  </div>
                  <div>
                    <Label className="text-gray-700 text-sm">Generatornummer</Label>
                    <Input value={formData.generator_number} onChange={e => update("generator_number", e.target.value)} className="mt-1" data-testid="gen-num-input" />
                  </div>
                </div>
              </div>

              <div className="border-t border-gray-100 pt-4">
                <h3 className="text-sm font-medium text-gray-900 mb-3">Wartung</h3>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <Label className="text-gray-700 text-sm">Letzte Wartung</Label>
                    <Input type="date" value={formData.last_maintenance} onChange={e => update("last_maintenance", e.target.value)} className="mt-1" data-testid="last-maint-input" />
                  </div>
                  <div>
                    <Label className="text-gray-700 text-sm">Nächste Wartung</Label>
                    <Input type="date" value={formData.next_maintenance} onChange={e => update("next_maintenance", e.target.value)} className="mt-1" data-testid="next-maint-input" />
                  </div>
                </div>
              </div>
            </>
          )}

          {/* GPS */}
          <div className="border-t border-gray-100 pt-4">
            <h3 className="text-sm font-medium text-gray-900 mb-3">Standort (GPS)</h3>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label className="text-gray-700 text-sm">Breitengrad</Label>
                <Input type="number" step="any" value={formData.latitude} onChange={e => update("latitude", e.target.value)} placeholder="z.B. 50.1109" className="mt-1" data-testid="lat-input" />
              </div>
              <div>
                <Label className="text-gray-700 text-sm">Längengrad</Label>
                <Input type="number" step="any" value={formData.longitude} onChange={e => update("longitude", e.target.value)} placeholder="z.B. 8.6821" className="mt-1" data-testid="lng-input" />
              </div>
            </div>
          </div>

          {/* Notes */}
          <div>
            <Label className="text-gray-700 text-sm">Notizen</Label>
            <textarea
              value={formData.notes}
              onChange={e => update("notes", e.target.value)}
              rows={2}
              className="mt-1 w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:border-fuchsia-500"
              data-testid="notes-input"
            />
          </div>

          {/* Documents (only for existing devices) */}
          {editing && (
            <div className="border-t border-gray-100 pt-4">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-medium text-gray-900">Dokumente ({documents.length})</h3>
                <label className="cursor-pointer">
                  <input type="file" ref={fileInputRef} onChange={handleUpload} className="hidden" />
                  <span className="inline-flex items-center gap-1 px-3 py-1.5 bg-fuchsia-50 text-fuchsia-600 rounded-lg text-xs font-medium hover:bg-fuchsia-100 transition-colors" data-testid="upload-doc-btn">
                    <Upload className="w-3.5 h-3.5" /> {uploading ? "Lädt..." : "Hochladen"}
                  </span>
                </label>
              </div>
              {documents.length === 0 ? (
                <p className="text-xs text-gray-400">Keine Dokumente vorhanden</p>
              ) : (
                <div className="space-y-1.5">
                  {documents.map(doc => (
                    <div key={doc.id} className="flex items-center justify-between py-2 px-3 bg-gray-50 rounded-lg" data-testid={`doc-${doc.id}`}>
                      <div className="flex items-center gap-2 min-w-0">
                        <FileText className="w-4 h-4 text-gray-400 flex-shrink-0" />
                        <div className="min-w-0">
                          <p className="text-sm text-gray-900 truncate">{doc.filename}</p>
                          <p className="text-[10px] text-gray-400">{(doc.size / 1024).toFixed(1)} KB · {new Date(doc.uploaded_at).toLocaleDateString("de-DE")}</p>
                        </div>
                      </div>
                      <button onClick={() => handleDeleteDoc(doc.id)} className="text-gray-400 hover:text-red-500 flex-shrink-0 ml-2" data-testid={`delete-doc-${doc.id}`}>
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        <div className="flex justify-end gap-3 p-5 border-t border-gray-200">
          <Button variant="outline" onClick={onClose} data-testid="cancel-btn">Abbrechen</Button>
          <Button onClick={onSave} className="bg-fuchsia-600 hover:bg-fuchsia-700 text-white" data-testid="save-device-btn">
            {editing ? "Speichern" : "Anlegen"}
          </Button>
        </div>
      </div>
    </div>
  );
}

export default function DeviceManagementPage() {
  const navigate = useNavigate();
  const [devices, setDevices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState("all");
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [formData, setFormData] = useState({ ...EMPTY_FORM });
  const [deleteConfirm, setDeleteConfirm] = useState(null);

  const loadDevices = useCallback(async () => {
    try {
      const res = await api.get("/devices");
      setDevices(res.data);
    } catch (err) {
      toast.error("Fehler beim Laden der Geräte");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadDevices(); }, [loadDevices]);

  const openCreate = () => {
    setEditing(null);
    setFormData({ ...EMPTY_FORM });
    setModalOpen(true);
  };

  const openEdit = (device) => {
    setEditing(device);
    setFormData({
      device_type: device.device_type || "stromerzeuger",
      serial_number: device.serial_number || "",
      user_field: device.user_field || "",
      latitude: device.latitude ?? "",
      longitude: device.longitude ?? "",
      model: device.model || "",
      engine_manufacturer: device.engine_manufacturer || "",
      engine_type: device.engine_type || "",
      engine_number: device.engine_number || "",
      generator_manufacturer: device.generator_manufacturer || "",
      generator_type: device.generator_type || "",
      generator_number: device.generator_number || "",
      year_of_manufacture: device.year_of_manufacture ?? "",
      power_output: device.power_output || "",
      controller: device.controller || "",
      last_maintenance: device.last_maintenance || "",
      next_maintenance: device.next_maintenance || "",
      notes: device.notes || "",
    });
    setModalOpen(true);
  };

  const handleSave = async () => {
    if (!formData.serial_number.trim()) {
      toast.error("Seriennummer ist erforderlich");
      return;
    }

    const payload = {
      ...formData,
      latitude: formData.latitude ? parseFloat(formData.latitude) : null,
      longitude: formData.longitude ? parseFloat(formData.longitude) : null,
      year_of_manufacture: formData.year_of_manufacture ? parseInt(formData.year_of_manufacture) : null,
    };

    try {
      if (editing) {
        await api.put(`/devices/${editing.id}`, payload);
        toast.success("Gerät aktualisiert");
      } else {
        await api.post("/devices", payload);
        toast.success("Gerät angelegt");
      }
      setModalOpen(false);
      loadDevices();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Fehler beim Speichern");
    }
  };

  const handleCopy = async (deviceId) => {
    try {
      const res = await api.post(`/devices/${deviceId}/copy`);
      toast.success("Gerät kopiert – bitte Seriennummer anpassen");
      setModalOpen(false);
      loadDevices();
      // Open the copied device for editing
      setTimeout(() => openEdit(res.data), 300);
    } catch (err) {
      toast.error("Fehler beim Kopieren");
    }
  };

  const handleDelete = async (deviceId) => {
    try {
      await api.delete(`/devices/${deviceId}`);
      toast.success("Gerät gelöscht");
      setDeleteConfirm(null);
      loadDevices();
    } catch {
      toast.error("Fehler beim Löschen");
    }
  };

  const filtered = devices.filter(d => {
    const matchType = typeFilter === "all" || d.device_type === typeFilter;
    const q = search.toLowerCase();
    const matchSearch = !search ||
      (d.serial_number || "").toLowerCase().includes(q) ||
      (d.user_field || "").toLowerCase().includes(q) ||
      (d.model || "").toLowerCase().includes(q) ||
      (d.engine_manufacturer || "").toLowerCase().includes(q) ||
      (d.notes || "").toLowerCase().includes(q);
    return matchType && matchSearch;
  });

  return (
    <div className="min-h-screen bg-gray-50" data-testid="device-management">
      {/* Header */}
      <header className="sticky top-0 z-10 bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Button variant="ghost" size="sm" onClick={() => navigate("/hub")} className="text-gray-600 hover:text-fuchsia-600" data-testid="back-btn">
              <ArrowLeft className="w-4 h-4 mr-1" /> Zurück
            </Button>
            <div className="h-5 w-px bg-gray-200" />
            <h1 className="text-base font-semibold text-gray-900">Geräteverwaltung</h1>
          </div>
          <div className="flex items-center gap-2">
            <Button size="sm" onClick={openCreate} className="bg-fuchsia-600 hover:bg-fuchsia-700 text-white" data-testid="new-device-btn">
              <Plus className="w-4 h-4 mr-1" /> Neues Gerät
            </Button>
            <Logo size="small" />
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 py-6">
        {/* Filters */}
        <div className="flex flex-col sm:flex-row gap-3 mb-6">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <input
              type="text"
              placeholder="Suche nach Seriennummer, Benutzerfeld, Modell..."
              value={search}
              onChange={e => setSearch(e.target.value)}
              className="w-full pl-10 pr-4 py-2 bg-white border border-gray-200 rounded-lg text-sm text-gray-900 placeholder-gray-400 focus:outline-none focus:border-fuchsia-500"
              data-testid="device-search"
            />
          </div>
          <div className="flex gap-1">
            {[{ value: "all", label: "Alle" }, ...DEVICE_TYPES].map(t => (
              <button
                key={t.value}
                onClick={() => setTypeFilter(t.value)}
                className={`px-3 py-2 rounded-lg text-xs font-medium transition-colors ${
                  typeFilter === t.value
                    ? "bg-fuchsia-600 text-white"
                    : "bg-white text-gray-500 hover:text-gray-700 border border-gray-200"
                }`}
                data-testid={`filter-${t.value}`}
              >
                {t.label}
              </button>
            ))}
          </div>
        </div>

        {/* Device Table */}
        {loading ? (
          <div className="text-center py-20 text-gray-400">Laden...</div>
        ) : filtered.length === 0 ? (
          <div className="text-center py-20">
            <Settings className="w-12 h-12 text-gray-300 mx-auto mb-4" />
            <p className="text-gray-500 mb-4">{devices.length === 0 ? "Keine Geräte angelegt" : "Keine Treffer"}</p>
            {devices.length === 0 && (
              <Button size="sm" onClick={openCreate} className="bg-fuchsia-600 hover:bg-fuchsia-700 text-white">
                <Plus className="w-4 h-4 mr-1" /> Erstes Gerät anlegen
              </Button>
            )}
          </div>
        ) : (
          <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-sm" data-testid="device-table">
                <thead>
                  <tr className="bg-gray-50 border-b border-gray-200 text-xs text-gray-500 uppercase tracking-wider">
                    <th className="px-4 py-3 text-left">Typ</th>
                    <th className="px-4 py-3 text-left">Seriennummer</th>
                    <th className="px-4 py-3 text-left hidden md:table-cell">Modell</th>
                    <th className="px-4 py-3 text-left hidden md:table-cell">Benutzerfeld</th>
                    <th className="px-4 py-3 text-left hidden lg:table-cell">Leistung</th>
                    <th className="px-4 py-3 text-left hidden lg:table-cell">Wartung</th>
                    <th className="px-4 py-3 text-left hidden lg:table-cell">Dok.</th>
                    <th className="px-4 py-3 text-right">Aktionen</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map(device => {
                    const TypeIcon = DEVICE_TYPES.find(t => t.value === device.device_type)?.icon || Settings;
                    const nextMaint = device.next_maintenance ? new Date(device.next_maintenance) : null;
                    const isOverdue = nextMaint && nextMaint < new Date();
                    return (
                      <tr key={device.id} className="border-b border-gray-100 hover:bg-gray-50 transition-colors" data-testid={`device-row-${device.serial_number}`}>
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-2">
                            <TypeIcon className="w-4 h-4 text-fuchsia-500" />
                            <span className="text-xs text-gray-500">{TYPE_LABELS[device.device_type] || device.device_type}</span>
                          </div>
                        </td>
                        <td className="px-4 py-3 font-mono font-medium text-gray-900">{device.serial_number}</td>
                        <td className="px-4 py-3 text-gray-600 hidden md:table-cell">{device.model || "–"}</td>
                        <td className="px-4 py-3 text-gray-500 hidden md:table-cell truncate max-w-[200px]">{device.user_field || "–"}</td>
                        <td className="px-4 py-3 text-gray-600 hidden lg:table-cell">{device.power_output || "–"}</td>
                        <td className="px-4 py-3 hidden lg:table-cell">
                          {device.next_maintenance ? (
                            <span className={`text-xs ${isOverdue ? "text-red-500 font-medium" : "text-gray-500"}`}>
                              {new Date(device.next_maintenance).toLocaleDateString("de-DE")}
                              {isOverdue && " (überfällig)"}
                            </span>
                          ) : "–"}
                        </td>
                        <td className="px-4 py-3 hidden lg:table-cell">
                          {device.document_count > 0 ? (
                            <span className="inline-flex items-center gap-1 text-xs text-fuchsia-600">
                              <FileText className="w-3 h-3" /> {device.document_count}
                            </span>
                          ) : "–"}
                        </td>
                        <td className="px-4 py-3 text-right">
                          <div className="flex items-center justify-end gap-1">
                            <button onClick={() => openEdit(device)} className="p-1.5 text-gray-400 hover:text-fuchsia-600 transition-colors" data-testid={`edit-${device.serial_number}`}>
                              <Pencil className="w-4 h-4" />
                            </button>
                            <button onClick={() => handleCopy(device.id)} className="p-1.5 text-gray-400 hover:text-fuchsia-600 transition-colors" data-testid={`copy-${device.serial_number}`}>
                              <Copy className="w-4 h-4" />
                            </button>
                            <button onClick={() => setDeleteConfirm(device)} className="p-1.5 text-gray-400 hover:text-red-500 transition-colors" data-testid={`delete-${device.serial_number}`}>
                              <Trash2 className="w-4 h-4" />
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <div className="px-4 py-2 bg-gray-50 text-xs text-gray-400 border-t border-gray-100">
              {filtered.length} von {devices.length} Geräte{typeFilter !== "all" ? ` (Filter: ${TYPE_LABELS[typeFilter]})` : ""}
            </div>
          </div>
        )}
      </main>

      {/* Device Modal */}
      <DeviceModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        formData={formData}
        setFormData={setFormData}
        onSave={handleSave}
        editing={editing}
        onCopy={handleCopy}
      />

      {/* Delete Confirmation */}
      {deleteConfirm && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center">
          <div className="bg-white rounded-xl shadow-xl p-6 max-w-sm mx-4" data-testid="delete-confirm">
            <h3 className="text-lg font-semibold text-gray-900 mb-2">Gerät löschen?</h3>
            <p className="text-sm text-gray-500 mb-4">
              <strong>{deleteConfirm.serial_number}</strong> wird unwiderruflich gelöscht, inklusive aller Dokumente.
            </p>
            <div className="flex justify-end gap-3">
              <Button variant="outline" onClick={() => setDeleteConfirm(null)}>Abbrechen</Button>
              <Button onClick={() => handleDelete(deleteConfirm.id)} className="bg-red-600 hover:bg-red-700 text-white" data-testid="confirm-delete-btn">Löschen</Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
