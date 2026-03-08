import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { Logo } from "../components/Logo";
import api, { getErrorMsg } from "../lib/api";
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
  Link2,
  CheckCircle,
  XCircle,
  Eye,
  EyeOff,
  Save,
  Wifi,
  WifiOff,
  Loader2,
  Globe,
  RefreshCw,
  Terminal,
} from "lucide-react";

/* ───── EpiRent-specific field config ───── */
const KENNZEICHNUNGEN = [
  { key: "kaution_all_inclusive", label: "Kaution all inclusive" },
  { key: "abgesagt", label: "Abgesagt" },
  { key: "bestaetigt", label: "Bestätigt" },
  { key: "versicherung", label: "Versicherung" },
  { key: "mrp", label: "MRP" },
  { key: "vermietung", label: "Vermietung" },
  { key: "verkauf", label: "Verkauf" },
  { key: "selbstabholer", label: "Selbstabholer" },
  { key: "selbstruecklieferer", label: "Selbstrücklieferer" },
  { key: "personalplanung", label: "Personalplanung" },
  { key: "wochenend_tarif", label: "Wochenend-Tarif" },
];

const DEFAULT_SETTINGS = {
  name: "",
  type: "ERP",
  api_url: "",
  api_key: "",
  active: true,
  ssl_skip: true,
  mandant_id: 0,
  mandant_name: "",
  auftraege_als: "jobs",
  zeitraum: "event",
  unterjobs: "keine",
  mehrtaegig_splitten: false,
  kennzeichnungen: Object.fromEntries(KENNZEICHNUNGEN.map(k => [k.key, "nicht_pruefen"])),
  notes: "",
};

/* ───── Integration Card ───── */
function IntegrationCard({ integration, onEdit, onDelete, onToggle, onTest }) {
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState(null);

  const handleTest = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      const res = await api.post(`/admin/integrations/${integration.id}/test`);
      setTestResult(res.data);
    } catch {
      setTestResult({ success: false, message: "Fehler beim Testen" });
    } finally {
      setTesting(false);
    }
  };

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
        <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium ${integration.active ? "bg-emerald-100 text-emerald-700" : "bg-gray-100 text-gray-500"}`}>
          {integration.active ? <CheckCircle className="w-3 h-3" /> : <XCircle className="w-3 h-3" />}
          {integration.active ? "Aktiv" : "Inaktiv"}
        </span>
      </div>

      <div className="text-xs text-gray-400 mb-3 font-mono truncate">{integration.api_url || "—"}</div>

      {/* Test Result */}
      {testResult && (
        <div className={`flex items-center gap-2 px-3 py-2 rounded-lg mb-3 text-xs font-medium ${testResult.success ? "bg-emerald-50 text-emerald-700" : "bg-red-50 text-red-700"}`} data-testid="test-result">
          {testResult.success ? <Wifi className="w-3.5 h-3.5" /> : <WifiOff className="w-3.5 h-3.5" />}
          {testResult.message}
          {testResult.product_count !== undefined && (
            <span className="text-gray-500 ml-1">({testResult.product_count} Artikel, {testResult.stock_count} Bestände)</span>
          )}
        </div>
      )}

      <div className="flex items-center justify-between pt-3 border-t border-gray-100">
        <div className="flex items-center gap-3">
          <Switch checked={integration.active} onCheckedChange={() => onToggle(integration)} data-testid={`toggle-${integration.id}`} />
          <Button variant="outline" size="sm" onClick={handleTest} disabled={testing} className="text-xs h-7" data-testid={`test-${integration.id}`}>
            {testing ? <Loader2 className="w-3 h-3 mr-1 animate-spin" /> : <Wifi className="w-3 h-3 mr-1" />}
            API testen
          </Button>
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

/* ───── Radio Group Helper ───── */
function RadioOption({ name, value, current, onChange, label }) {
  return (
    <label className="flex items-center gap-2 cursor-pointer py-1">
      <input
        type="radio"
        name={name}
        value={value}
        checked={current === value}
        onChange={() => onChange(value)}
        className="w-4 h-4 text-fuchsia-600 border-gray-300 focus:ring-fuchsia-500"
      />
      <span className="text-sm text-gray-700">{label}</span>
    </label>
  );
}

/* ───── Emergent.sh Bridge ───── */
function EmergentBridge() {
  const [config, setConfig] = useState({ name: "Emergent.sh", api_url: "", api_key: "", active: false });
  const [loaded, setLoaded] = useState(false);
  const [showKey, setShowKey] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api.get("/admin/emergent-config").then(res => {
      if (res.data.configured) {
        setConfig(prev => ({ ...prev, ...res.data }));
      }
      setLoaded(true);
    }).catch(() => setLoaded(true));
  }, []);

  const handleSave = async () => {
    setSaving(true);
    try {
      const res = await api.post("/admin/emergent-config", { ...config, type: "EMERGENT" });
      setConfig(prev => ({ ...prev, ...res.data }));
      toast.success("Emergent-Konfiguration gespeichert");
    } catch { toast.error("Fehler beim Speichern"); }
    finally { setSaving(false); }
  };

  const handleTest = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      // Save first to ensure ID exists
      const saveRes = await api.post("/admin/emergent-config", { ...config, type: "EMERGENT" });
      const id = saveRes.data.id;
      setConfig(prev => ({ ...prev, ...saveRes.data }));
      const res = await api.post(`/admin/integrations/${id}/test`);
      setTestResult(res.data);
    } catch { setTestResult({ success: false, message: "Testfehler" }); }
    finally { setTesting(false); }
  };

  if (!loaded) return null;

  return (
    <div className="bg-white border border-gray-200 rounded-lg overflow-hidden" data-testid="emergent-bridge">
      <div className="flex items-center justify-between px-5 py-4 bg-gradient-to-r from-gray-900 to-gray-800">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-emerald-500/20 flex items-center justify-center">
            <Terminal className="w-5 h-5 text-emerald-400" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-white">Emergent.sh</h3>
            <p className="text-[10px] text-gray-400">Live-Entwicklungsbrücke zum lokalen Server</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {config.active && (
            <span className="flex items-center gap-1.5 px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-400 text-[10px] font-medium">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" /> Live
            </span>
          )}
          <Switch
            checked={config.active}
            onCheckedChange={v => setConfig(prev => ({ ...prev, active: v }))}
            data-testid="emergent-toggle"
          />
        </div>
      </div>

      <div className="p-5 space-y-4">
        <div>
          <Label className="text-sm text-gray-600">Emergent URL</Label>
          <Input
            value={config.api_url}
            onChange={e => setConfig(prev => ({ ...prev, api_url: e.target.value }))}
            placeholder="https://event-invoicing.preview.emergentagent.com"
            className="mt-1 font-mono text-sm"
            data-testid="emergent-url-input"
          />
        </div>
        <div>
          <Label className="text-sm text-gray-600">API-Key</Label>
          <div className="flex gap-2 mt-1">
            <Input
              type={showKey ? "text" : "password"}
              value={config.api_key}
              onChange={e => setConfig(prev => ({ ...prev, api_key: e.target.value }))}
              placeholder="Emergent API-Schlüssel"
              className="font-mono text-sm flex-1"
              data-testid="emergent-key-input"
            />
            <Button variant="outline" size="sm" onClick={() => setShowKey(!showKey)} className="shrink-0">
              {showKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
            </Button>
          </div>
        </div>

        <div className="flex items-center gap-3 pt-1 flex-wrap">
          <Button size="sm" onClick={handleSave} disabled={saving} className="bg-gray-900 hover:bg-gray-800 text-white" data-testid="emergent-save-btn">
            {saving ? <Loader2 className="w-4 h-4 mr-1.5 animate-spin" /> : <Save className="w-4 h-4 mr-1.5" />}
            Speichern
          </Button>
          <Button variant="outline" size="sm" onClick={handleTest} disabled={testing} data-testid="emergent-test-btn">
            {testing ? <Loader2 className="w-4 h-4 mr-1.5 animate-spin" /> : <Globe className="w-4 h-4 mr-1.5" />}
            Verbindung testen
          </Button>
          {testResult && (
            <span className={`flex items-center gap-1.5 text-xs font-medium ${testResult.success ? "text-emerald-600" : "text-red-600"}`} data-testid="emergent-test-result">
              {testResult.success ? <CheckCircle className="w-4 h-4" /> : <XCircle className="w-4 h-4" />}
              {testResult.message}
            </span>
          )}
        </div>

        <div className="bg-gray-50 rounded-lg p-3 border border-gray-100">
          <p className="text-[10px] text-gray-500 leading-relaxed">
            <strong>Sync-Modus:</strong> Frontend + Backend + Konfiguration. Nach dem Umzug auf den lokalen Server ermöglicht diese Verbindung
            Live-Entwicklung über die Emergent-Plattform. Änderungen werden direkt auf den lokalen Server übertragen.
          </p>
          <div className="flex gap-3 mt-2">
            <span className="px-1.5 py-0.5 bg-fuchsia-50 text-fuchsia-600 rounded text-[10px] font-medium">Frontend</span>
            <span className="px-1.5 py-0.5 bg-fuchsia-50 text-fuchsia-600 rounded text-[10px] font-medium">Backend</span>
            <span className="px-1.5 py-0.5 bg-fuchsia-50 text-fuchsia-600 rounded text-[10px] font-medium">Konfiguration</span>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ───── Main Page ───── */
export default function AdminSettingsPage() {
  const navigate = useNavigate();
  const [integrations, setIntegrations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [formData, setFormData] = useState({ ...DEFAULT_SETTINGS });
  const [showApiKey, setShowApiKey] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState(null);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState(null);

  const loadIntegrations = useCallback(async () => {
    try {
      const res = await api.get("/admin/integrations");
      setIntegrations(res.data);
    } catch {
      setIntegrations([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadIntegrations(); }, [loadIntegrations]);

  const openCreate = () => {
    setEditing(null);
    setFormData({ ...DEFAULT_SETTINGS, kennzeichnungen: Object.fromEntries(KENNZEICHNUNGEN.map(k => [k.key, "nicht_pruefen"])) });
    setShowApiKey(false);
    setTestResult(null);
    setModalOpen(true);
  };

  const openEdit = (integration) => {
    setEditing(integration);
    setFormData({
      ...DEFAULT_SETTINGS,
      ...integration,
      kennzeichnungen: integration.kennzeichnungen || Object.fromEntries(KENNZEICHNUNGEN.map(k => [k.key, "nicht_pruefen"])),
    });
    setShowApiKey(false);
    setTestResult(null);
    setModalOpen(true);
  };

  const handleSave = async () => {
    if (!formData.name.trim()) { toast.error("Name ist erforderlich"); return; }
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
      toast.error(getErrorMsg(err, "Fehler beim Speichern"));
    }
  };

  const handleToggle = async (integration) => {
    try {
      await api.put(`/admin/integrations/${integration.id}`, { ...integration, active: !integration.active });
      toast.success(integration.active ? "Deaktiviert" : "Aktiviert");
      loadIntegrations();
    } catch { toast.error("Fehler"); }
  };

  const handleDelete = async (id) => {
    try {
      await api.delete(`/admin/integrations/${id}`);
      toast.success("Schnittstelle gelöscht");
      setDeleteConfirm(null);
      loadIntegrations();
    } catch { toast.error("Fehler beim Löschen"); }
  };

  const handleTestInModal = async () => {
    if (!formData.api_url || !formData.api_key) { toast.error("URL und API-Key erforderlich"); return; }
    setTesting(true);
    setTestResult(null);
    try {
      // Save first if new, then test
      let integrationId = editing?.id;
      if (!integrationId) {
        if (!formData.name.trim()) { toast.error("Name ist erforderlich"); setTesting(false); return; }
        const res = await api.post("/admin/integrations", formData);
        integrationId = res.data.id;
        setEditing(res.data);
      } else {
        await api.put(`/admin/integrations/${integrationId}`, formData);
      }
      const res = await api.post(`/admin/integrations/${integrationId}/test`);
      setTestResult(res.data);
      if (res.data.success) toast.success("Verbindung erfolgreich!");
      else toast.error(res.data.message);
    } catch (err) {
      setTestResult({ success: false, message: "Testfehler" });
    } finally {
      setTesting(false);
    }
  };

  const update = (field, value) => setFormData(prev => ({ ...prev, [field]: value }));
  const updateKennz = (key, value) => setFormData(prev => ({
    ...prev, kennzeichnungen: { ...prev.kennzeichnungen, [key]: value }
  }));

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col" data-testid="admin-settings">
      <header className="bg-white border-b border-gray-200 sticky top-0 z-30">
        <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Button variant="ghost" size="sm" onClick={() => navigate("/admin")} className="text-gray-600 hover:text-fuchsia-600" data-testid="back-to-admin-btn">
              <ArrowLeft className="w-4 h-4 mr-2" /> Zurück
            </Button>
            <h1 className="text-lg font-semibold text-gray-900">Administrative Einstellungen</h1>
          </div>
          <div className="flex items-center gap-2">
            <Button size="sm" onClick={openCreate} className="bg-fuchsia-600 hover:bg-fuchsia-700 text-white" data-testid="new-integration-btn">
              <Plus className="w-4 h-4 mr-1" /> Neue Schnittstelle
            </Button>
            <Button variant="outline" size="sm" onClick={() => navigate("/mqtt-config")} className="text-gray-600 hover:text-fuchsia-600" data-testid="mqtt-config-link">
              <Wifi className="w-4 h-4 mr-1" /> MQTT
            </Button>
            <Logo size="small" />
          </div>
        </div>
      </header>

      <main className="flex-1 p-4 md:p-6">
        <div className="max-w-7xl mx-auto space-y-8">
          {/* Emergent.sh Bridge */}
          <EmergentBridge />

          {/* Schnittstellen */}
          <div>
            <div className="mb-4">
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
              {integrations.filter(i => i.type !== "EMERGENT").map(i => (
                <IntegrationCard key={i.id} integration={i} onEdit={openEdit} onDelete={setDeleteConfirm} onToggle={handleToggle} />
              ))}
            </div>
          )}
          </div>
        </div>
      </main>

      {/* ─── Create/Edit Modal ─── */}
      {modalOpen && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-start justify-center pt-4 overflow-y-auto">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-3xl mx-4 mb-8" data-testid="integration-modal">
            <div className="flex items-center justify-between p-5 border-b border-gray-200">
              <h2 className="text-lg font-semibold text-gray-900">
                {editing ? "Schnittstelle bearbeiten" : "Neue Schnittstelle"}
              </h2>
              <button onClick={() => setModalOpen(false)} className="text-gray-400 hover:text-gray-600"><XCircle className="w-5 h-5" /></button>
            </div>

            <div className="p-5 space-y-6 max-h-[75vh] overflow-y-auto">

              {/* ── Verbindung ── */}
              <section className="bg-gray-50 rounded-lg p-4 space-y-3" data-testid="section-connection">
                <h3 className="text-sm font-semibold text-gray-900">Einstellungen</h3>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <Label className="text-sm text-gray-600">Name *</Label>
                    <Input value={formData.name} onChange={e => update("name", e.target.value)} placeholder="z.B. EpiRent ERP" className="mt-1" data-testid="integration-name-input" />
                  </div>
                  <div>
                    <Label className="text-sm text-gray-600">Typ</Label>
                    <select value={formData.type} onChange={e => update("type", e.target.value)}
                      className="w-full mt-1 px-3 py-2 border border-gray-200 rounded-lg text-sm bg-white" data-testid="integration-type-select">
                      <option value="ERP">ERP-System</option>
                      <option value="CRM">CRM</option>
                      <option value="MQTT">MQTT Broker</option>
                      <option value="API">Sonstige API</option>
                    </select>
                  </div>
                </div>

                <div>
                  <Label className="text-sm text-gray-600">URL</Label>
                  <Input value={formData.api_url} onChange={e => update("api_url", e.target.value)} placeholder="http://217.86.214.29:18081/" className="mt-1 font-mono" data-testid="integration-url-input" />
                </div>

                <label className="flex items-center gap-2 cursor-pointer">
                  <input type="checkbox" checked={formData.ssl_skip || false} onChange={e => update("ssl_skip", e.target.checked)}
                    className="rounded border-gray-300 text-fuchsia-600" data-testid="ssl-skip-checkbox" />
                  <span className="text-sm text-gray-600">SSL-Zertifikatprüfung deaktivieren <span className="text-gray-400 text-xs">(notwendig bei selbst signierten Zertifikaten)</span></span>
                </label>

                <div>
                  <Label className="text-sm text-gray-600">API-Token</Label>
                  <div className="flex gap-2 mt-1">
                    <Input type={showApiKey ? "text" : "password"} value={formData.api_key} onChange={e => update("api_key", e.target.value)}
                      placeholder="API-Schlüssel" className="font-mono flex-1" data-testid="integration-apikey-input" />
                    <Button variant="outline" size="sm" onClick={() => setShowApiKey(!showApiKey)} className="shrink-0">
                      {showApiKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    </Button>
                  </div>
                </div>

                {/* Test Button + Result */}
                <div className="flex items-center gap-3 pt-1">
                  <Button variant="outline" size="sm" onClick={handleTestInModal} disabled={testing} className="bg-gray-800 text-white hover:bg-gray-900 border-0" data-testid="test-api-btn">
                    {testing ? <Loader2 className="w-4 h-4 mr-1.5 animate-spin" /> : <Wifi className="w-4 h-4 mr-1.5" />}
                    API-Abruf testen
                  </Button>
                  {testResult && (
                    <div className={`flex items-center gap-1.5 text-xs font-medium ${testResult.success ? "text-emerald-600" : "text-red-600"}`} data-testid="modal-test-result">
                      {testResult.success ? <CheckCircle className="w-4 h-4" /> : <XCircle className="w-4 h-4" />}
                      {testResult.message}
                      {testResult.product_count !== undefined && <span className="text-gray-400">({testResult.product_count} Artikel, {testResult.stock_count} Bestände)</span>}
                    </div>
                  )}
                </div>
              </section>

              {/* ── Mandanten ── */}
              <section className="bg-gray-50 rounded-lg p-4" data-testid="section-mandanten">
                <h3 className="text-sm font-semibold text-gray-900 mb-2">Mandanten</h3>
                <label className="flex items-center gap-2 cursor-pointer">
                  <input type="checkbox" checked={true} readOnly className="rounded border-gray-300 text-fuchsia-600" />
                  <span className="text-sm text-gray-700">{formData.mandant_id || 0} - {formData.mandant_name || "Eventenergie Deutschland GmbH & Co. KG"}</span>
                </label>
              </section>

              {/* ── Aufträge ── */}
              <section className="bg-gray-50 rounded-lg p-4 space-y-3" data-testid="section-auftraege">
                <h3 className="text-sm font-semibold text-gray-900">Aufträge</h3>
                <div className="flex items-center gap-3 flex-wrap">
                  <span className="text-sm text-gray-600">Epirent-Aufträge anlegen als</span>
                  <select value={formData.auftraege_als || "jobs"} onChange={e => update("auftraege_als", e.target.value)}
                    className="px-3 py-1.5 border border-gray-200 rounded-lg text-sm bg-white" data-testid="auftraege-als-select">
                    <option value="jobs">Jobs</option>
                    <option value="projekte">Projekte</option>
                    <option value="auftraege">Aufträge</option>
                  </select>
                </div>
                <div className="ml-4 space-y-1">
                  <RadioOption name="zeitraum" value="event" current={formData.zeitraum || "event"} onChange={v => update("zeitraum", v)} label="Event-Zeitraum übernehmen" />
                  <RadioOption name="zeitraum" value="dispo" current={formData.zeitraum || "event"} onChange={v => update("zeitraum", v)} label="Dispo-Zeitraum übernehmen" />
                </div>
              </section>

              {/* ── Unterjobs ── */}
              <section className="bg-gray-50 rounded-lg p-4 space-y-1" data-testid="section-unterjobs">
                <h3 className="text-sm font-semibold text-gray-900 mb-2">Unterjobs</h3>
                <RadioOption name="unterjobs" value="keine" current={formData.unterjobs || "keine"} onChange={v => update("unterjobs", v)} label="Keine Unterjobs anlegen" />
                <RadioOption name="unterjobs" value="zeitplan" current={formData.unterjobs || "keine"} onChange={v => update("unterjobs", v)} label="Zeitplan als Unterjobs übernehmen" />
                {formData.unterjobs === "zeitplan" && (
                  <label className="flex items-center gap-2 ml-6 cursor-pointer py-1">
                    <input type="checkbox" checked={formData.mehrtaegig_splitten || false} onChange={e => update("mehrtaegig_splitten", e.target.checked)}
                      className="rounded border-gray-300 text-fuchsia-600" data-testid="mehrtaegig-checkbox" />
                    <span className="text-sm text-gray-600">Mehrtägige Einträge in einzelne Tage splitten</span>
                  </label>
                )}
                <RadioOption name="unterjobs" value="kapitel" current={formData.unterjobs || "keine"} onChange={v => update("unterjobs", v)} label="Kapitel des Auftrags als Unterjobs übernehmen" />
              </section>

              {/* ── Vorbedingungen / Kennzeichnungen ── */}
              <section className="bg-gray-50 rounded-lg p-4" data-testid="section-kennzeichnungen">
                <h3 className="text-sm font-semibold text-gray-900 mb-1">Vorbedingungen</h3>
                <p className="text-xs text-gray-400 mb-3 font-medium">Kennzeichnungen</p>
                <div className="border border-gray-200 rounded-lg overflow-hidden bg-white">
                  <table className="w-full text-sm" data-testid="kennzeichnungen-table">
                    <thead>
                      <tr className="bg-gray-50 border-b border-gray-200">
                        <th className="text-left px-4 py-2 text-gray-600 font-medium">Feld</th>
                        <th className="text-center px-2 py-2 text-gray-600 font-medium w-20">Ja</th>
                        <th className="text-center px-2 py-2 text-gray-600 font-medium w-20">Nein</th>
                        <th className="text-center px-2 py-2 text-gray-600 font-medium w-28">Nicht prüfen</th>
                      </tr>
                    </thead>
                    <tbody>
                      {KENNZEICHNUNGEN.map((k, i) => (
                        <tr key={k.key} className={i % 2 === 0 ? "bg-white" : "bg-gray-50"}>
                          <td className="px-4 py-2.5 text-gray-700">{k.label}</td>
                          {["ja", "nein", "nicht_pruefen"].map(val => (
                            <td key={val} className="text-center px-2 py-2.5">
                              <input
                                type="radio"
                                name={`kennz_${k.key}`}
                                value={val}
                                checked={(formData.kennzeichnungen?.[k.key] || "nicht_pruefen") === val}
                                onChange={() => updateKennz(k.key, val)}
                                className="w-4 h-4 text-fuchsia-600 border-gray-300 focus:ring-fuchsia-500"
                                data-testid={`kennz-${k.key}-${val}`}
                              />
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>

              {/* ── Notizen ── */}
              <section className="bg-gray-50 rounded-lg p-4">
                <Label className="text-sm text-gray-600">Notizen</Label>
                <textarea value={formData.notes} onChange={e => update("notes", e.target.value)} rows={2}
                  placeholder="Zusätzliche Informationen..."
                  className="mt-1 w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:border-fuchsia-500 bg-white"
                  data-testid="integration-notes-input" />
              </section>
            </div>

            <div className="flex justify-end gap-3 p-5 border-t border-gray-200">
              <Button variant="outline" onClick={() => setModalOpen(false)} data-testid="cancel-integration-btn">Abbrechen</Button>
              <Button onClick={handleSave} className="bg-fuchsia-600 hover:bg-fuchsia-700 text-white" data-testid="save-integration-btn">
                <Save className="w-4 h-4 mr-1" /> {editing ? "Speichern" : "Anlegen"}
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
            <p className="text-sm text-gray-500 mb-4"><strong>{deleteConfirm.name}</strong> wird unwiderruflich gelöscht.</p>
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
