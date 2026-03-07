import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { Logo } from "../components/Logo";
import api from "../lib/api";
import { toast } from "sonner";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Switch } from "../components/ui/switch";
import {
  ArrowLeft,
  Plus,
  Pencil,
  Trash2,
  Settings,
  Link2,
  CheckCircle,
  XCircle,
  Eye,
  EyeOff,
  Save,
  RefreshCw,
} from "lucide-react";

function IntegrationCard({ integration, onEdit, onDelete, onToggle }) {
  return (
    <div className="bg-white border border-gray-200 rounded-lg p-5 hover:border-fuchsia-300 transition-all" data-testid={`integration-${integration.id}`}>
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-3">
          <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${integration.active ? "bg-emerald-50 text-emerald-600" : "bg-gray-100 text-gray-400"}`}>
            <Link2 className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-gray-900">{integration.name}</h3>
            <p className="text-xs text-gray-400">{integration.type || "ERP-System"}</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium ${integration.active ? "bg-emerald-100 text-emerald-700" : "bg-gray-100 text-gray-500"}`}>
            {integration.active ? <CheckCircle className="w-3 h-3" /> : <XCircle className="w-3 h-3" />}
            {integration.active ? "Aktiv" : "Inaktiv"}
          </span>
        </div>
      </div>

      <div className="text-xs text-gray-400 mb-3 font-mono truncate">{integration.api_url || "Keine URL konfiguriert"}</div>

      {integration.field_mappings && (
        <div className="flex flex-wrap gap-1 mb-3">
          {Object.entries(integration.field_mappings).filter(([, v]) => v).map(([key]) => (
            <span key={key} className="px-1.5 py-0.5 bg-fuchsia-50 text-fuchsia-600 rounded text-[10px] font-medium">{key}</span>
          ))}
        </div>
      )}

      <div className="flex items-center justify-between pt-3 border-t border-gray-100">
        <div className="flex items-center gap-2">
          <Switch
            checked={integration.active}
            onCheckedChange={() => onToggle(integration)}
            data-testid={`toggle-${integration.id}`}
          />
          <span className="text-[10px] text-gray-400">{integration.active ? "Deaktivieren" : "Aktivieren"}</span>
        </div>
        <div className="flex items-center gap-1">
          <button onClick={() => onEdit(integration)} className="p-1.5 text-gray-400 hover:text-fuchsia-600 transition-colors" data-testid={`edit-integration-${integration.id}`}>
            <Pencil className="w-4 h-4" />
          </button>
          <button onClick={() => onDelete(integration)} className="p-1.5 text-gray-400 hover:text-red-500 transition-colors" data-testid={`delete-integration-${integration.id}`}>
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
}

const DEFAULT_FIELD_MAPPINGS = {
  product_no: true,
  inventory_no: true,
  name: true,
  serial_no: true,
  is_active: true,
  pricing: true,
  stock_data: true,
  tech_data: true,
  group_of_goods: true,
  notes: false,
  accounting: false,
};

const FIELD_LABELS = {
  product_no: "Artikelnummer",
  inventory_no: "Inventarnummer",
  name: "Bezeichnung",
  serial_no: "Seriennummer",
  is_active: "Aktiv-Status",
  pricing: "Preise",
  stock_data: "Bestandsdaten",
  tech_data: "Technische Daten",
  group_of_goods: "Warengruppen",
  notes: "Notizen",
  accounting: "Buchhaltung",
};

const EMPTY_INTEGRATION = {
  name: "",
  type: "ERP",
  api_url: "",
  api_key: "",
  active: true,
  field_mappings: { ...DEFAULT_FIELD_MAPPINGS },
  username: "",
  password: "",
  sync_interval_minutes: 60,
  notes: "",
};

export default function AdminSettingsPage() {
  const navigate = useNavigate();
  const [integrations, setIntegrations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [formData, setFormData] = useState({ ...EMPTY_INTEGRATION });
  const [showApiKey, setShowApiKey] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState(null);

  const loadIntegrations = useCallback(async () => {
    try {
      const res = await api.get("/admin/integrations");
      setIntegrations(res.data);
    } catch {
      // No integrations yet
      setIntegrations([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadIntegrations(); }, [loadIntegrations]);

  const openCreate = () => {
    setEditing(null);
    setFormData({ ...EMPTY_INTEGRATION, field_mappings: { ...DEFAULT_FIELD_MAPPINGS } });
    setShowApiKey(false);
    setModalOpen(true);
  };

  const openEdit = (integration) => {
    setEditing(integration);
    setFormData({
      name: integration.name || "",
      type: integration.type || "ERP",
      api_url: integration.api_url || "",
      api_key: integration.api_key || "",
      active: integration.active ?? true,
      field_mappings: integration.field_mappings || { ...DEFAULT_FIELD_MAPPINGS },
      username: integration.username || "",
      password: integration.password || "",
      sync_interval_minutes: integration.sync_interval_minutes || 60,
      notes: integration.notes || "",
    });
    setShowApiKey(false);
    setModalOpen(true);
  };

  const handleSave = async () => {
    if (!formData.name.trim()) {
      toast.error("Name ist erforderlich");
      return;
    }
    try {
      if (editing) {
        await api.put(`/admin/integrations/${editing.id}`, formData);
        toast.success("Schnittstelle aktualisiert");
      } else {
        await api.post("/admin/integrations", formData);
        toast.success("Schnittstelle angelegt");
      }
      setModalOpen(false);
      loadIntegrations();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Fehler beim Speichern");
    }
  };

  const handleToggle = async (integration) => {
    try {
      await api.put(`/admin/integrations/${integration.id}`, {
        ...integration,
        active: !integration.active,
      });
      toast.success(integration.active ? "Schnittstelle deaktiviert" : "Schnittstelle aktiviert");
      loadIntegrations();
    } catch {
      toast.error("Fehler");
    }
  };

  const handleDelete = async (id) => {
    try {
      await api.delete(`/admin/integrations/${id}`);
      toast.success("Schnittstelle gelöscht");
      setDeleteConfirm(null);
      loadIntegrations();
    } catch {
      toast.error("Fehler beim Löschen");
    }
  };

  const update = (field, value) => setFormData(prev => ({ ...prev, [field]: value }));
  const toggleField = (field) => setFormData(prev => ({
    ...prev,
    field_mappings: { ...prev.field_mappings, [field]: !prev.field_mappings[field] }
  }));

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col" data-testid="admin-settings">
      <header className="bg-white border-b border-gray-200 p-4">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Button variant="ghost" size="sm" onClick={() => navigate("/admin")} className="text-gray-600 hover:text-fuchsia-600" data-testid="back-to-admin-btn">
              <ArrowLeft className="w-4 h-4 mr-2" /> Zurück
            </Button>
            <div className="h-6 w-px bg-gray-200" />
            <h1 className="text-lg font-semibold text-gray-900">Administrative Einstellungen</h1>
          </div>
          <div className="flex items-center gap-2">
            <Button size="sm" onClick={openCreate} className="bg-fuchsia-600 hover:bg-fuchsia-700 text-white" data-testid="new-integration-btn">
              <Plus className="w-4 h-4 mr-1" /> Neue Schnittstelle
            </Button>
            <Logo size="small" />
          </div>
        </div>
      </header>

      <main className="flex-1 p-4 md:p-6">
        <div className="max-w-7xl mx-auto">
          <div className="mb-6">
            <h2 className="text-sm font-semibold text-gray-900 mb-1">Schnittstellen</h2>
            <p className="text-xs text-gray-400">Externe Systeme und API-Verbindungen verwalten</p>
          </div>

          {loading ? (
            <div className="text-center py-20 text-gray-400">Laden...</div>
          ) : integrations.length === 0 ? (
            <div className="text-center py-20">
              <Link2 className="w-12 h-12 text-gray-300 mx-auto mb-4" />
              <p className="text-gray-500 mb-4">Keine Schnittstellen konfiguriert</p>
              <Button size="sm" onClick={openCreate} className="bg-fuchsia-600 hover:bg-fuchsia-700 text-white" data-testid="empty-new-integration-btn">
                <Plus className="w-4 h-4 mr-1" /> Erste Schnittstelle anlegen
              </Button>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4" data-testid="integrations-grid">
              {integrations.map(i => (
                <IntegrationCard
                  key={i.id}
                  integration={i}
                  onEdit={openEdit}
                  onDelete={setDeleteConfirm}
                  onToggle={handleToggle}
                />
              ))}
            </div>
          )}
        </div>
      </main>

      {/* Create/Edit Modal */}
      {modalOpen && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-start justify-center pt-8 overflow-y-auto">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-2xl mx-4 mb-8" data-testid="integration-modal">
            <div className="flex items-center justify-between p-5 border-b border-gray-200">
              <h2 className="text-lg font-semibold text-gray-900">
                {editing ? "Schnittstelle bearbeiten" : "Neue Schnittstelle"}
              </h2>
              <button onClick={() => setModalOpen(false)} className="text-gray-400 hover:text-gray-600">
                <XCircle className="w-5 h-5" />
              </button>
            </div>

            <div className="p-5 space-y-5 max-h-[70vh] overflow-y-auto">
              {/* Basic Info */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label className="text-gray-700 text-sm">Name *</Label>
                  <Input value={formData.name} onChange={e => update("name", e.target.value)} placeholder="z.B. EpiRent ERP" className="mt-1" data-testid="integration-name-input" />
                </div>
                <div>
                  <Label className="text-gray-700 text-sm">Typ</Label>
                  <select
                    value={formData.type}
                    onChange={e => update("type", e.target.value)}
                    className="w-full mt-1 px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:border-fuchsia-500 bg-white"
                    data-testid="integration-type-select"
                  >
                    <option value="ERP">ERP-System</option>
                    <option value="CRM">CRM</option>
                    <option value="MQTT">MQTT Broker</option>
                    <option value="API">Sonstige API</option>
                  </select>
                </div>
              </div>

              {/* Connection */}
              <div className="border-t border-gray-100 pt-4">
                <h3 className="text-sm font-medium text-gray-900 mb-3">Verbindung</h3>
                <div className="space-y-3">
                  <div>
                    <Label className="text-gray-700 text-sm">API-URL</Label>
                    <Input value={formData.api_url} onChange={e => update("api_url", e.target.value)} placeholder="https://api.example.com/v1" className="mt-1 font-mono text-sm" data-testid="integration-url-input" />
                  </div>
                  <div>
                    <Label className="text-gray-700 text-sm">API-Key</Label>
                    <div className="flex gap-2 mt-1">
                      <Input
                        type={showApiKey ? "text" : "password"}
                        value={formData.api_key}
                        onChange={e => update("api_key", e.target.value)}
                        placeholder="API-Schlüssel"
                        className="font-mono text-sm flex-1"
                        data-testid="integration-apikey-input"
                      />
                      <Button variant="outline" size="sm" onClick={() => setShowApiKey(!showApiKey)} className="shrink-0">
                        {showApiKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                      </Button>
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <Label className="text-gray-700 text-sm">Benutzer</Label>
                      <Input value={formData.username} onChange={e => update("username", e.target.value)} placeholder="Optional" className="mt-1" data-testid="integration-user-input" />
                    </div>
                    <div>
                      <Label className="text-gray-700 text-sm">Passwort</Label>
                      <Input type="password" value={formData.password} onChange={e => update("password", e.target.value)} placeholder="Optional" className="mt-1" data-testid="integration-pass-input" />
                    </div>
                  </div>
                </div>
              </div>

              {/* Field Mapping */}
              <div className="border-t border-gray-100 pt-4">
                <h3 className="text-sm font-medium text-gray-900 mb-1">Feld-Zuordnung</h3>
                <p className="text-[10px] text-gray-400 mb-3">Welche Datenfelder sollen synchronisiert werden?</p>
                <div className="grid grid-cols-2 gap-2" data-testid="field-mappings">
                  {Object.entries(FIELD_LABELS).map(([key, label]) => (
                    <label key={key} className="flex items-center gap-2 px-3 py-2 bg-gray-50 rounded-lg cursor-pointer hover:bg-gray-100 transition-colors" data-testid={`field-${key}`}>
                      <input
                        type="checkbox"
                        checked={formData.field_mappings?.[key] ?? false}
                        onChange={() => toggleField(key)}
                        className="rounded border-gray-300 text-fuchsia-600 focus:ring-fuchsia-500"
                      />
                      <span className="text-xs text-gray-700">{label}</span>
                    </label>
                  ))}
                </div>
              </div>

              {/* Notes */}
              <div className="border-t border-gray-100 pt-4">
                <Label className="text-gray-700 text-sm">Notizen</Label>
                <textarea
                  value={formData.notes}
                  onChange={e => update("notes", e.target.value)}
                  rows={2}
                  placeholder="Zusätzliche Informationen..."
                  className="mt-1 w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:border-fuchsia-500"
                  data-testid="integration-notes-input"
                />
              </div>
            </div>

            <div className="flex justify-end gap-3 p-5 border-t border-gray-200">
              <Button variant="outline" onClick={() => setModalOpen(false)} data-testid="cancel-integration-btn">Abbrechen</Button>
              <Button onClick={handleSave} className="bg-fuchsia-600 hover:bg-fuchsia-700 text-white" data-testid="save-integration-btn">
                <Save className="w-4 h-4 mr-1" />
                {editing ? "Speichern" : "Anlegen"}
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Delete Confirm */}
      {deleteConfirm && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center">
          <div className="bg-white rounded-xl shadow-xl p-6 max-w-sm mx-4" data-testid="delete-integration-confirm">
            <h3 className="text-lg font-semibold text-gray-900 mb-2">Schnittstelle löschen?</h3>
            <p className="text-sm text-gray-500 mb-4">
              <strong>{deleteConfirm.name}</strong> wird unwiderruflich gelöscht.
            </p>
            <div className="flex justify-end gap-3">
              <Button variant="outline" onClick={() => setDeleteConfirm(null)}>Abbrechen</Button>
              <Button onClick={() => handleDelete(deleteConfirm.id)} className="bg-red-600 hover:bg-red-700 text-white" data-testid="confirm-delete-integration-btn">Löschen</Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
