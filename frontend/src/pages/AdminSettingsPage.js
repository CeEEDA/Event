import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { Logo } from "../components/Logo";
import api, { getErrorMsg, BACKEND_URL } from "../lib/api";
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
  Mail,
  Download,
  Cpu,
  FileCode,
  Settings2,
  FileText,
  Package,
  Shield,
  Server,
  Database,
  FolderArchive,
  Clock,
  Play,
  Trash,
  HardDrive,
  Activity,
  MonitorSmartphone,
  Wrench,
  Zap,
  Upload,
  Radio,
  Check,
  Monitor,
  Laptop,
  CircleDollarSign,
  MapPin,
} from "lucide-react";
import { openExternal } from "../lib/openExternal";
import OllamaConfigSection from "../components/OllamaConfigSection";
import StorageHealthSection from "../components/StorageHealthSection";

/* ───── System Status Dashboard ───── */
function SystemStatusDashboard() {
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [autoRefresh, setAutoRefresh] = useState(true);

  const loadStatus = useCallback(async () => {
    try {
      const res = await api.get("/system/status");
      setStatus(res.data);
    } catch {
      setStatus(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadStatus();
    if (!autoRefresh) return;
    const interval = setInterval(loadStatus, 30000);
    return () => clearInterval(interval);
  }, [loadStatus, autoRefresh]);

  if (loading) return (
    <div className="bg-white border border-gray-200 rounded-lg p-6">
      <div className="flex items-center gap-2 text-gray-400"><Loader2 className="w-4 h-4 animate-spin" /> System-Status laden...</div>
    </div>
  );

  if (!status) return (
    <div className="bg-white border border-red-200 rounded-lg p-6">
      <div className="flex items-center gap-2 text-red-500"><XCircle className="w-4 h-4" /> System-Status nicht verfügbar</div>
    </div>
  );

  const StatusDot = ({ ok }) => (
    <span className="relative flex h-2.5 w-2.5">
      {ok && <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>}
      <span className={`relative inline-flex rounded-full h-2.5 w-2.5 ${ok ? "bg-emerald-500" : "bg-red-400"}`}></span>
    </span>
  );

  return (
    <div data-testid="system-status-dashboard">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-sm font-semibold text-gray-900 mb-1 flex items-center gap-2">
            <Activity className="w-4 h-4 text-fuchsia-500" /> System-Status
          </h2>
          <p className="text-xs text-gray-400">Live-Übersicht aller Systemkomponenten</p>
        </div>
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-1.5 text-[11px] text-gray-400 cursor-pointer">
            <Switch checked={autoRefresh} onCheckedChange={setAutoRefresh} className="scale-75" />
            Auto
          </label>
          <Button variant="ghost" size="sm" onClick={loadStatus} className="h-7 w-7 p-0 text-gray-400 hover:text-fuchsia-600" data-testid="refresh-status-btn">
            <RefreshCw className="w-3.5 h-3.5" />
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {/* MongoDB */}
        <div className="bg-white border border-gray-200 rounded-lg p-4 flex flex-col gap-2" data-testid="status-mongodb">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-xs font-medium text-gray-600">
              <Database className="w-4 h-4 text-emerald-500" /> MongoDB
            </div>
            <StatusDot ok={status.mongodb?.connected} />
          </div>
          <p className={`text-sm font-semibold ${status.mongodb?.connected ? "text-emerald-600" : "text-red-500"}`}>
            {status.mongodb?.connected ? "Verbunden" : "Getrennt"}
          </p>
          <p className="text-[10px] text-gray-400">{status.collections} Collections</p>
        </div>

        {/* Users */}
        <div className="bg-white border border-gray-200 rounded-lg p-4 flex flex-col gap-2" data-testid="status-users">
          <div className="flex items-center gap-2 text-xs font-medium text-gray-600">
            <Shield className="w-4 h-4 text-blue-500" /> Benutzer
          </div>
          <p className="text-sm font-semibold text-gray-900">{status.users}</p>
          <p className="text-[10px] text-gray-400">registriert</p>
        </div>

        {/* Devices Online */}
        <div className="bg-white border border-gray-200 rounded-lg p-4 flex flex-col gap-2" data-testid="status-devices">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-xs font-medium text-gray-600">
              <Cpu className="w-4 h-4 text-fuchsia-500" /> Geräte
            </div>
            {status.devices?.online > 0 && <StatusDot ok={true} />}
          </div>
          <p className="text-sm font-semibold text-gray-900">
            <span className="text-emerald-600">{status.devices?.online || 0}</span>
            <span className="text-gray-400 font-normal text-xs"> / {status.devices?.total || 0}</span>
          </p>
          <p className="text-[10px] text-gray-400">{status.devices?.online || 0} online, {status.devices?.active || 0} aktiv</p>
        </div>

        {/* Generators */}
        <div className="bg-white border border-gray-200 rounded-lg p-4 flex flex-col gap-2" data-testid="status-generators">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-xs font-medium text-gray-600">
              <Server className="w-4 h-4 text-amber-500" /> Generatoren
            </div>
            {status.generators?.online > 0 && <StatusDot ok={true} />}
          </div>
          <p className="text-sm font-semibold text-gray-900">
            <span className="text-emerald-600">{status.generators?.online || 0}</span>
            <span className="text-gray-400 font-normal text-xs"> / {status.generators?.total || 0}</span>
          </p>
          <p className="text-[10px] text-gray-400">{status.recent_activity?.emu_records_last_hour || 0} EMU-Datensätze/Std</p>
        </div>
      </div>

      <p className="text-[10px] text-gray-300 mt-2 text-right">
        Stand: {new Date(status.timestamp).toLocaleString("de-DE")} {autoRefresh && "· Auto-Refresh 30s"}
      </p>
    </div>
  );
}

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
  const [syncStatus, setSyncStatus] = useState(null);
  const [syncInterval, setSyncInterval] = useState(30);
  const [savingInterval, setSavingInterval] = useState(false);

  useEffect(() => {
    api.get("/orders/sync/status").then(res => {
      setSyncStatus(res.data);
      setSyncInterval(res.data.interval_minutes || 30);
    }).catch(() => {});
  }, []);

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

  const saveSyncInterval = async () => {
    setSavingInterval(true);
    try {
      await api.post("/orders/sync/settings", { interval_minutes: parseInt(syncInterval) });
      toast.success(`Sync-Intervall auf ${syncInterval} Min gesetzt`);
    } catch { toast.error("Fehler"); }
    finally { setSavingInterval(false); }
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

      {/* Sync Settings */}
      <div className="bg-gray-50 rounded-lg p-3 mb-3">
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs font-medium text-gray-600">Automatischer Sync</span>
          {syncStatus?.last_synced && (
            <span className="text-[10px] text-gray-400">
              Letzter Sync: {new Date(syncStatus.last_synced).toLocaleString("de-DE", {hour: "2-digit", minute: "2-digit", day: "2-digit", month: "2-digit"})}
              {syncStatus.last_count != null && ` (${syncStatus.last_count} Auftraege)`}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-500">Intervall:</span>
          <input
            type="number" min="1" max="1440"
            value={syncInterval}
            onChange={e => setSyncInterval(e.target.value)}
            className="w-16 px-2 py-1 text-xs border border-gray-200 rounded text-center font-mono"
            data-testid="sync-interval-input"
          />
          <span className="text-xs text-gray-500">Minuten</span>
          <button
            onClick={saveSyncInterval}
            disabled={savingInterval}
            className="px-2 py-1 text-xs bg-fuchsia-100 text-fuchsia-700 rounded hover:bg-fuchsia-200 transition-colors"
            data-testid="save-sync-interval-btn"
          >
            {savingInterval ? "..." : "Speichern"}
          </button>
        </div>
      </div>

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
            placeholder="https://eventenergie.app"
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

/* ───── SMTP / E-Mail Config ───── */
function SmtpConfig() {
  const [config, setConfig] = useState({ smtp_host: "", smtp_port: 465, smtp_user: "", smtp_password: "", smtp_sender_name: "" });
  const [loaded, setLoaded] = useState(false);
  const [showPw, setShowPw] = useState(false);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState(null);

  useEffect(() => {
    api.get("/admin/smtp-config").then(res => { setConfig(res.data); setLoaded(true); }).catch(() => setLoaded(true));
  }, []);

  const handleSave = async () => {
    setSaving(true);
    try {
      await api.put("/admin/smtp-config", config);
      toast.success("E-Mail-Konfiguration gespeichert");
    } catch { toast.error("Fehler beim Speichern"); }
    finally { setSaving(false); }
  };

  const handleTest = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      await api.put("/admin/smtp-config", config);
      const res = await api.post("/admin/smtp-config/test");
      setTestResult(res.data);
      if (res.data.success) toast.success(res.data.message);
      else toast.error(res.data.message);
    } catch { setTestResult({ success: false, message: "Testfehler" }); }
    finally { setTesting(false); }
  };

  if (!loaded) return null;

  return (
    <div className="bg-white border border-gray-200 rounded-lg overflow-hidden" data-testid="smtp-config">
      <div className="flex items-center justify-between px-5 py-4 bg-gradient-to-r from-fuchsia-600 to-fuchsia-500">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-white/20 flex items-center justify-center">
            <Mail className="w-5 h-5 text-white" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-white">E-Mail-Konfiguration</h3>
            <p className="text-[10px] text-fuchsia-100">SMTP-Zugangsdaten für den E-Mail-Versand</p>
          </div>
        </div>
      </div>

      <div className="p-5 space-y-4">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <Label className="text-sm text-gray-600">SMTP-Host</Label>
            <Input value={config.smtp_host} onChange={e => setConfig(prev => ({ ...prev, smtp_host: e.target.value }))} placeholder="smtp.example.com" className="mt-1 font-mono text-sm" data-testid="smtp-host-input" />
          </div>
          <div>
            <Label className="text-sm text-gray-600">Port</Label>
            <Input type="number" value={config.smtp_port} onChange={e => setConfig(prev => ({ ...prev, smtp_port: parseInt(e.target.value) || 465 }))} placeholder="465" className="mt-1 font-mono text-sm" data-testid="smtp-port-input" />
          </div>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <Label className="text-sm text-gray-600">Benutzername / E-Mail</Label>
            <Input value={config.smtp_user} onChange={e => setConfig(prev => ({ ...prev, smtp_user: e.target.value }))} placeholder="user@example.com" className="mt-1 font-mono text-sm" data-testid="smtp-user-input" />
          </div>
          <div>
            <Label className="text-sm text-gray-600">Passwort</Label>
            <div className="flex gap-2 mt-1">
              <Input type={showPw ? "text" : "password"} value={config.smtp_password} onChange={e => setConfig(prev => ({ ...prev, smtp_password: e.target.value }))} placeholder="SMTP-Passwort" className="font-mono text-sm flex-1" data-testid="smtp-password-input" />
              <Button variant="outline" size="sm" onClick={() => setShowPw(!showPw)} className="shrink-0">
                {showPw ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </Button>
            </div>
          </div>
        </div>
        <div>
          <Label className="text-sm text-gray-600">Absender-Name</Label>
          <Input value={config.smtp_sender_name} onChange={e => setConfig(prev => ({ ...prev, smtp_sender_name: e.target.value }))} placeholder="Eventenergie Portal" className="mt-1 text-sm" data-testid="smtp-sender-input" />
        </div>

        <div className="flex items-center gap-3 pt-1 flex-wrap">
          <Button size="sm" onClick={handleSave} disabled={saving} className="bg-fuchsia-600 hover:bg-fuchsia-700 text-white" data-testid="smtp-save-btn">
            {saving ? <Loader2 className="w-4 h-4 mr-1.5 animate-spin" /> : <Save className="w-4 h-4 mr-1.5" />}
            Speichern
          </Button>
          <Button variant="outline" size="sm" onClick={handleTest} disabled={testing} data-testid="smtp-test-btn">
            {testing ? <Loader2 className="w-4 h-4 mr-1.5 animate-spin" /> : <Mail className="w-4 h-4 mr-1.5" />}
            Verbindung testen
          </Button>
          {testResult && (
            <span className={`flex items-center gap-1.5 text-xs font-medium ${testResult.success ? "text-emerald-600" : "text-red-600"}`} data-testid="smtp-test-result">
              {testResult.success ? <CheckCircle className="w-4 h-4" /> : <XCircle className="w-4 h-4" />}
              {testResult.message}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}

/* ───── Update-Paket Export ───── */
function UpdatePackageSection() {
  const [downloading, setDownloading] = useState(false);

  const handleDownload = async () => {
    setDownloading(true);
    try {
      const res = await api.get("/download/update-package", { responseType: "blob" });
      const disposition = res.headers["content-disposition"] || "";
      const match = disposition.match(/filename="?([^"]+)"?/);
      const filename = match ? match[1] : "eventenergie_update.zip";
      const { saveAs } = await import("file-saver");
      saveAs(new Blob([res.data], { type: "application/zip" }), filename);
      toast.success("Update-Paket heruntergeladen");
    } catch (err) {
      toast.error(getErrorMsg(err, "Download fehlgeschlagen"));
    } finally {
      setDownloading(false);
    }
  };

  return (
    <div className="bg-white border border-gray-200 rounded-lg overflow-hidden" data-testid="update-package-section">
      <div className="flex items-center justify-between px-5 py-4 bg-gradient-to-r from-fuchsia-700 to-fuchsia-500">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-white/20 flex items-center justify-center">
            <Package className="w-5 h-5 text-white" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-white">Server Update-Paket</h3>
            <p className="text-[10px] text-fuchsia-100">Sicheres Update fuer den Live-Server</p>
          </div>
        </div>
      </div>

      <div className="p-5 space-y-4">
        <p className="text-xs text-gray-500 leading-relaxed">
          Erstellt ein ZIP-Paket mit dem aktuellen Quellcode fuer den Windows-Server.
          <strong className="text-gray-700"> .env Dateien werden NICHT enthalten</strong> - Ihre Zugangsdaten und Datenbank-Verbindungen bleiben geschuetzt.
        </p>

        <Button
          onClick={handleDownload}
          disabled={downloading}
          className="w-full bg-fuchsia-600 hover:bg-fuchsia-700 text-white"
          data-testid="download-update-package-btn"
        >
          {downloading ? (
            <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> Paket wird erstellt...</>
          ) : (
            <><Download className="w-4 h-4 mr-2" /> Update-Paket herunterladen (ZIP)</>
          )}
        </Button>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
          <a
            href={`${BACKEND_URL}/api/download/frontend-env`}
            download=".env"
            className="flex items-center gap-3 px-3 py-2.5 rounded-lg border border-fuchsia-200 bg-fuchsia-50 hover:border-fuchsia-400 transition-all hover:shadow-sm"
            data-testid="download-frontend-env"
          >
            <FileText className="w-4 h-4 text-fuchsia-600 shrink-0" />
            <div className="min-w-0 flex-1">
              <div className="text-xs font-medium text-gray-900">frontend/.env</div>
              <div className="text-[10px] text-gray-400">Produktions-Konfiguration</div>
            </div>
            <Download className="w-3.5 h-3.5 text-gray-400 shrink-0" />
          </a>
          <a
            href={`${BACKEND_URL}/api/download/backend-env-example`}
            download=".env.example"
            className="flex items-center gap-3 px-3 py-2.5 rounded-lg border border-gray-200 bg-gray-50 hover:border-gray-300 transition-all hover:shadow-sm"
            data-testid="download-backend-env-example"
          >
            <FileText className="w-4 h-4 text-gray-500 shrink-0" />
            <div className="min-w-0 flex-1">
              <div className="text-xs font-medium text-gray-900">backend/.env.example</div>
              <div className="text-[10px] text-gray-400">Vorlage (Werte anpassen!)</div>
            </div>
            <Download className="w-3.5 h-3.5 text-gray-400 shrink-0" />
          </a>
          <a
            href={`${BACKEND_URL}/api/download/caddyfile`}
            download="Caddyfile"
            className="flex items-center gap-3 px-3 py-2.5 rounded-lg border border-orange-200 bg-orange-50 hover:border-orange-400 transition-all hover:shadow-sm"
            data-testid="download-caddyfile"
          >
            <FileText className="w-4 h-4 text-orange-600 shrink-0" />
            <div className="min-w-0 flex-1">
              <div className="text-xs font-medium text-gray-900">Caddyfile</div>
              <div className="text-[10px] text-gray-400">Reverse-Proxy Konfiguration</div>
            </div>
            <Download className="w-3.5 h-3.5 text-gray-400 shrink-0" />
          </a>
        </div>

        <div className="bg-gray-50 rounded-lg p-3 border border-gray-100 space-y-2">
          <p className="text-[10px] font-semibold text-gray-700">Erstinstallation (einmalig):</p>
          <ol className="text-[10px] text-gray-500 leading-relaxed space-y-1 list-decimal list-inside">
            <li>Caddy herunterladen: <a href="https://caddyserver.com/download" target="_blank" rel="noreferrer" className="text-fuchsia-600 underline">caddyserver.com/download</a> (Windows amd64)</li>
            <li><code className="bg-gray-200 px-1 rounded">caddy.exe</code> nach <code className="bg-gray-200 px-1 rounded">C:\eventenergie\</code> kopieren</li>
            <li>Caddyfile herunterladen und nach <code className="bg-gray-200 px-1 rounded">C:\eventenergie\</code> legen</li>
            <li><code className="bg-gray-200 px-1 rounded">frontend/.env</code> und <code className="bg-gray-200 px-1 rounded">backend/.env</code> konfigurieren</li>
          </ol>
          <p className="text-[10px] font-semibold text-gray-700 pt-1">Update-Prozess:</p>
          <ol className="text-[10px] text-gray-500 leading-relaxed space-y-1 list-decimal list-inside">
            <li>Update-ZIP herunterladen und entpacken</li>
            <li><code className="bg-gray-200 px-1 rounded">update.bat</code> als Administrator ausfuehren</li>
            <li>Skript aktualisiert nur Code - .env, Datenbank und Caddy bleiben unberuehrt</li>
          </ol>
        </div>

        <div className="flex flex-wrap gap-2">
          <span className="px-1.5 py-0.5 bg-green-50 text-green-700 rounded text-[10px] font-medium">.env geschuetzt</span>
          <span className="px-1.5 py-0.5 bg-green-50 text-green-700 rounded text-[10px] font-medium">Datenbank sicher</span>
          <span className="px-1.5 py-0.5 bg-blue-50 text-blue-700 rounded text-[10px] font-medium">Inkl. npm run build</span>
          <span className="px-1.5 py-0.5 bg-blue-50 text-blue-700 rounded text-[10px] font-medium">Inkl. Migration</span>
        </div>
      </div>
    </div>
  );
}

/* ───── Einsatzzentrale Pi-Kioske - Setup & Verwaltung ───── */
function EinsatzzentralePiSection() {
  const [pis, setPis] = useState([]);
  const [loading, setLoading] = useState(true);
  const [piName, setPiName] = useState("");
  const [standort, setStandort] = useState("");
  const [generating, setGenerating] = useState(false);
  const [setupCmd, setSetupCmd] = useState(null);
  const [copied, setCopied] = useState(false);

  const loadPis = async () => {
    try {
      const res = await api.get("/einsatzzentrale/pis");
      setPis(res.data.pis || []);
    } catch (e) {
      toast.error("Pi-Liste konnte nicht geladen werden: " + (e.response?.data?.detail || e.message));
    } finally { setLoading(false); }
  };
  useEffect(() => { loadPis(); }, []);

  const generateSetup = async () => {
    if (!piName.trim()) { toast.error("Bitte Pi-Namen eingeben"); return; }
    setGenerating(true);
    try {
      const res = await api.post("/einsatzzentrale/pis/generate-setup", {
        pi_name: piName.trim(),
        standort: standort.trim() || null,
      });
      // Setup-Befehl im Frontend zusammenbauen mit der bekannten echten
      // Backend-URL (REACT_APP_BACKEND_URL). Das ist robuster als die URL
      // vom Backend zu nehmen - hinter K8s-Ingress kann der Origin-Header
      // auf eine interne cluster-URL zeigen, die von ausserhalb nicht
      // erreichbar ist (HTTP 403 vom Cloudflare-Layer).
      const portalUrl = (process.env.REACT_APP_BACKEND_URL || window.location.origin).replace(/\/$/, "");
      const kioskUrl = `${portalUrl}/api/einsatzzentrale/kiosk-page?pi_id=${res.data.pi_id}&key=${res.data.plain_key}`;
      const installUrl = `${portalUrl}/api/einsatzzentrale/install-script`;
      const cmd = `curl -sL "${installUrl}" | sudo bash -s -- "${kioskUrl}"`;
      setSetupCmd(cmd);
      setPiName(""); setStandort("");
      toast.success("Setup-Befehl generiert");
      loadPis();
    } catch (e) {
      toast.error("Fehler: " + (e.response?.data?.detail || e.message));
    } finally { setGenerating(false); }
  };

  const copyToClipboard = () => {
    navigator.clipboard.writeText(setupCmd);
    setCopied(true);
    toast.success("In Zwischenablage kopiert");
    setTimeout(() => setCopied(false), 3000);
  };

  const deletePi = async (pi) => {
    if (!window.confirm(`Pi "${pi.name}" wirklich entfernen?`)) return;
    try {
      await api.delete(`/einsatzzentrale/pis/${pi.id}`);
      toast.success("Pi entfernt");
      loadPis();
    } catch (e) {
      toast.error("Fehler: " + (e.response?.data?.detail || e.message));
    }
  };

  const fmtSeen = (iso) => {
    if (!iso) return "noch nie";
    const d = new Date(iso); const now = new Date();
    const min = Math.round((now - d) / 60000);
    if (min < 1) return "gerade eben";
    if (min < 60) return `vor ${min} Min`;
    if (min < 1440) return `vor ${Math.round(min / 60)} h`;
    return d.toLocaleString("de-DE", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
  };

  return (
    <div className="bg-white border border-gray-200 rounded-lg overflow-hidden" data-testid="einsatzzentrale-pi-section">
      <div className="flex items-center justify-between px-5 py-4 bg-gradient-to-r from-fuchsia-600 to-purple-600">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-white/20 flex items-center justify-center">
            <Cpu className="w-5 h-5 text-white" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-white">Einsatzzentrale Pi-Kioske</h3>
            <p className="text-[10px] text-fuchsia-100">Raspberry Pi für TV-Wandanzeige in der Einsatzzentrale</p>
          </div>
        </div>
      </div>

      <div className="p-5 space-y-4">
        <p className="text-xs text-gray-500 leading-relaxed">
          Generiert einen One-Liner für jeden neuen Pi. Mehrere Pis möglich (z.B. Bauwagen, Büro, Lager).
          Der Pi installiert automatisch Chromium-Kiosk + meldet sich beim Portal an.
        </p>

        <div className="flex gap-2 items-end flex-wrap">
          <div className="flex-1 min-w-[180px]">
            <label className="text-xs font-medium text-gray-700 mb-1 block">Pi-Name *</label>
            <Input value={piName} onChange={e => setPiName(e.target.value)} placeholder="z.B. EZ-Bauwagen-01" className="text-sm" data-testid="ez-pi-name" />
          </div>
          <div className="flex-1 min-w-[160px]">
            <label className="text-xs font-medium text-gray-700 mb-1 block">Standort (optional)</label>
            <Input value={standort} onChange={e => setStandort(e.target.value)} placeholder="Bauwagen, Büro..." className="text-sm" data-testid="ez-pi-standort" />
          </div>
          <Button onClick={generateSetup} disabled={generating} className="bg-fuchsia-600 hover:bg-fuchsia-700 text-white text-xs" data-testid="ez-pi-generate-btn">
            {generating ? "Generiere..." : "Setup generieren"}
          </Button>
        </div>

        {setupCmd && (
          <div className="space-y-2">
            <label className="text-xs font-medium text-gray-700">Diesen Befehl auf dem Pi einfügen:</label>
            <div className="relative">
              <pre className="bg-gray-900 text-green-400 rounded-lg p-3 text-[11px] font-mono overflow-x-auto whitespace-pre-wrap break-all select-all">{setupCmd}</pre>
              <button onClick={copyToClipboard} className={`absolute top-2 right-2 px-2 py-1 text-[10px] rounded ${copied ? "bg-green-600 text-white" : "bg-gray-700 text-gray-300 hover:bg-gray-600"}`} data-testid="ez-copy-setup-cmd">
                {copied ? "Kopiert!" : "Kopieren"}
              </button>
            </div>
            <p className="text-[10px] text-gray-400">
              Nach ca. 2 Minuten ist der Pi bereit und erscheint unten in der Liste.
            </p>
          </div>
        )}

        {/* Pi-Liste */}
        <div className="border-t border-gray-200 pt-4">
          <div className="flex items-center justify-between mb-2">
            <h4 className="text-xs font-semibold text-gray-700">Registrierte Pis ({pis.length})</h4>
            <button onClick={loadPis} className="text-[10px] text-fuchsia-600 hover:underline" data-testid="ez-pi-reload">↻ Aktualisieren</button>
          </div>
          {loading ? (
            <div className="text-center py-4 text-xs text-gray-400">Lade…</div>
          ) : !pis.length ? (
            <div className="text-center py-6 text-xs text-gray-400">Noch keine Pis registriert. Generiere oben einen Setup-Befehl.</div>
          ) : (
            <div className="space-y-2" data-testid="ez-pi-list">
              {pis.map(p => (
                <div key={p.id} className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg border border-gray-200" data-testid={`ez-pi-row-${p.id}`}>
                  <div className={`w-2.5 h-2.5 rounded-full ${p.status === "online" ? "bg-green-500" : "bg-gray-400"}`} />
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium text-gray-900">{p.name}</div>
                    <div className="text-[11px] text-gray-500">
                      {p.standort && <span>{p.standort} · </span>}
                      Zuletzt online: {fmtSeen(p.last_seen)}
                      {" · "}
                      Key: <code className="text-gray-400">{p.device_key_prefix}…</code>
                    </div>
                  </div>
                  <button onClick={() => deletePi(p)} className="px-2 py-1 text-[10px] text-red-600 hover:bg-red-50 rounded" data-testid={`ez-pi-del-${p.id}`}>Entfernen</button>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="flex gap-2 flex-wrap">
          <span className="px-1.5 py-0.5 bg-fuchsia-50 text-fuchsia-700 rounded text-[10px] font-medium">Chromium Kiosk</span>
          <span className="px-1.5 py-0.5 bg-fuchsia-50 text-fuchsia-700 rounded text-[10px] font-medium">Auto-Start</span>
          <span className="px-1.5 py-0.5 bg-fuchsia-50 text-fuchsia-700 rounded text-[10px] font-medium">Mehrfach-Setup</span>
          <span className="px-1.5 py-0.5 bg-fuchsia-50 text-fuchsia-700 rounded text-[10px] font-medium">Auto-Heartbeat</span>
        </div>
      </div>
    </div>
  );
}


/* ───── Einsatzzentrale Browser-Tokens (temporaerer Browser-Zugang) ───── */
function EinsatzzentraleBrowserTokensSection() {
  const [tokens, setTokens] = useState([]);
  const [loading, setLoading] = useState(true);
  const [label, setLabel] = useState("");
  // Default: in 8 Stunden ablaufen
  const defaultValidUntil = () => {
    const d = new Date();
    d.setHours(d.getHours() + 8);
    // YYYY-MM-DDTHH:MM (lokal, ohne Sekunden) — passt zu <input type=datetime-local>
    const pad = (n) => String(n).padStart(2, "0");
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
  };
  const [validUntil, setValidUntil] = useState(defaultValidUntil());
  const [creating, setCreating] = useState(false);
  const [lastLink, setLastLink] = useState(null);
  const [copiedId, setCopiedId] = useState(null);

  const load = useCallback(async () => {
    try {
      const res = await api.get("/einsatzzentrale/browser-tokens");
      setTokens(res.data.tokens || []);
    } catch (e) {
      toast.error("Tokens konnten nicht geladen werden: " + (e.response?.data?.detail || e.message));
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => { load(); }, [load]);

  const buildKioskUrl = (token) => {
    const portalUrl = (process.env.REACT_APP_BACKEND_URL || window.location.origin).replace(/\/$/, "");
    return `${portalUrl}/einsatzzentrale?bt=${token}`;
  };

  const createToken = async () => {
    if (!label.trim()) { toast.error("Bitte Bezeichnung eingeben"); return; }
    if (!validUntil) { toast.error("Bitte Ablaufdatum waehlen"); return; }
    setCreating(true);
    try {
      // datetime-local liefert lokale Zeit ohne TZ — wir ergaenzen den lokalen Offset
      // damit der Server die Eingabe als europaeisches Datum interpretiert.
      const local = new Date(validUntil);
      const iso = local.toISOString();
      const res = await api.post("/einsatzzentrale/browser-tokens", {
        label: label.trim(),
        valid_until: iso,
      });
      // Prefer locally-constructed URL using REACT_APP_BACKEND_URL because
      // the backend's auto-detected URL can point to an internal cluster host.
      setLastLink(buildKioskUrl(res.data.token));
      setLabel("");
      setValidUntil(defaultValidUntil());
      toast.success("Browser-Link erstellt");
      load();
    } catch (e) {
      toast.error("Fehler: " + (e.response?.data?.detail || e.message));
    } finally {
      setCreating(false);
    }
  };

  const copyLink = (url, id) => {
    navigator.clipboard.writeText(url);
    setCopiedId(id);
    toast.success("Link kopiert");
    setTimeout(() => setCopiedId(null), 2000);
  };

  const revoke = async (t) => {
    if (!window.confirm(`Link "${t.label}" wirklich widerrufen?`)) return;
    try {
      await api.delete(`/einsatzzentrale/browser-tokens/${t.id}`);
      toast.success("Link widerrufen");
      load();
    } catch (e) {
      toast.error("Fehler: " + (e.response?.data?.detail || e.message));
    }
  };

  const fmtRel = (iso) => {
    if (!iso) return "nie";
    const d = new Date(iso); const now = new Date();
    const min = Math.round((now - d) / 60000);
    if (min < 1) return "gerade eben";
    if (min < 60) return `vor ${min} Min`;
    if (min < 1440) return `vor ${Math.round(min / 60)} h`;
    return d.toLocaleString("de-DE", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
  };
  const fmtDate = (iso) => {
    if (!iso) return "—";
    try { return new Date(iso).toLocaleString("de-DE", { day: "2-digit", month: "2-digit", year: "2-digit", hour: "2-digit", minute: "2-digit" }); }
    catch { return iso; }
  };
  const statusBadge = (s) => {
    if (s === "aktiv") return "bg-green-100 text-green-700";
    if (s === "abgelaufen") return "bg-gray-100 text-gray-600";
    return "bg-red-100 text-red-700"; // widerrufen
  };

  return (
    <div className="bg-white border border-gray-200 rounded-lg overflow-hidden" data-testid="einsatzzentrale-browser-tokens-section">
      <div className="flex items-center justify-between px-5 py-4 bg-gradient-to-r from-violet-600 to-fuchsia-600">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-white/20 flex items-center justify-center">
            <Link2 className="w-5 h-5 text-white" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-white">Einsatzzentrale — Browser-Zugang (temporaer)</h3>
            <p className="text-[10px] text-violet-100">Link erzeugen, im Browser oeffnen, zeitlich gesperrt</p>
          </div>
        </div>
      </div>

      <div className="p-5 space-y-4">
        <p className="text-xs text-gray-500 leading-relaxed">
          Erzeugt einen einmaligen Link, der die Einsatzzentrale-Oberflaeche in einem normalen Browser-Tab oeffnet.
          Funktioniert auf beliebig vielen Geraeten parallel bis zum Ablauf. Praktisch fuer Vertretungen oder externe Disponenten ohne dediziertem Pi.
        </p>

        <div className="flex gap-2 items-end flex-wrap">
          <div className="flex-1 min-w-[180px]">
            <label className="text-xs font-medium text-gray-700 mb-1 block">Bezeichnung *</label>
            <Input
              value={label}
              onChange={e => setLabel(e.target.value)}
              placeholder="z.B. Vertretung Bereitschaft Mai"
              className="text-sm"
              data-testid="ez-bt-label"
            />
          </div>
          <div className="flex-1 min-w-[200px]">
            <label className="text-xs font-medium text-gray-700 mb-1 block">Gueltig bis *</label>
            <Input
              type="datetime-local"
              value={validUntil}
              onChange={e => setValidUntil(e.target.value)}
              className="text-sm"
              data-testid="ez-bt-valid-until"
            />
          </div>
          <Button
            onClick={createToken}
            disabled={creating}
            className="bg-violet-600 hover:bg-violet-700 text-white text-xs"
            data-testid="ez-bt-create-btn"
          >
            {creating ? "Erstelle..." : "Link erzeugen"}
          </Button>
        </div>

        {lastLink && (
          <div className="space-y-2 bg-violet-50 border border-violet-200 rounded-lg p-3" data-testid="ez-bt-last-link">
            <div className="text-[11px] font-medium text-violet-900">Neuer Link bereit — direkt kopieren oder oeffnen:</div>
            <div className="relative">
              <pre className="bg-white border border-violet-200 rounded p-2 text-[11px] font-mono overflow-x-auto whitespace-pre-wrap break-all select-all">{lastLink}</pre>
              <button
                onClick={() => copyLink(lastLink, "last")}
                className={`absolute top-2 right-2 px-2 py-1 text-[10px] rounded ${copiedId === "last" ? "bg-green-600 text-white" : "bg-violet-600 text-white hover:bg-violet-700"}`}
                data-testid="ez-bt-copy-last"
              >
                {copiedId === "last" ? "Kopiert!" : "Kopieren"}
              </button>
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => window.open(lastLink, "_blank", "noopener,noreferrer")}
                className="text-[11px] text-violet-700 hover:underline"
                data-testid="ez-bt-open-last"
              >
                In neuem Tab oeffnen →
              </button>
            </div>
          </div>
        )}

        <div className="border-t border-gray-200 pt-4">
          <div className="flex items-center justify-between mb-2">
            <h4 className="text-xs font-semibold text-gray-700">Bestehende Links ({tokens.length})</h4>
            <button onClick={load} className="text-[10px] text-violet-600 hover:underline" data-testid="ez-bt-reload">↻ Aktualisieren</button>
          </div>
          {loading ? (
            <div className="text-center py-4 text-xs text-gray-400">Lade…</div>
          ) : !tokens.length ? (
            <div className="text-center py-6 text-xs text-gray-400">Noch keine Browser-Links erstellt.</div>
          ) : (
            <div className="space-y-2" data-testid="ez-bt-list">
              {tokens.map(t => {
                const url = buildKioskUrl(t.token);
                return (
                  <div key={t.id} className="p-3 bg-gray-50 rounded-lg border border-gray-200" data-testid={`ez-bt-row-${t.id}`}>
                    <div className="flex items-center gap-3 flex-wrap">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="text-sm font-medium text-gray-900">{t.label}</span>
                          <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${statusBadge(t.status)}`}>{t.status}</span>
                          {(t.click_count > 0) && (
                            <span className="text-[10px] px-1.5 py-0.5 rounded bg-violet-100 text-violet-700" title="Anzahl Aufrufe">
                              {t.click_count} Aufruf{t.click_count === 1 ? "" : "e"}
                            </span>
                          )}
                        </div>
                        <div className="text-[11px] text-gray-500 mt-0.5">
                          Gueltig bis: <span className="font-mono">{fmtDate(t.valid_until)}</span>
                          {" · "}
                          Erstellt {fmtRel(t.created_at)} von {t.created_by || "—"}
                        </div>
                        {(t.last_used_at) && (
                          <div className="text-[11px] text-gray-400 mt-0.5">
                            Letzte Nutzung: {fmtRel(t.last_used_at)}
                            {t.last_used_ip && <> · IP <code className="text-gray-500">{t.last_used_ip}</code></>}
                            {t.last_used_ua && <span className="ml-1 text-gray-400" title={t.last_used_ua}>· {(t.last_used_ua || "").slice(0, 40)}…</span>}
                          </div>
                        )}
                      </div>
                      <div className="flex items-center gap-1">
                        {t.status === "aktiv" && (
                          <>
                            <button
                              onClick={() => copyLink(url, t.id)}
                              className={`px-2 py-1 text-[10px] rounded ${copiedId === t.id ? "bg-green-600 text-white" : "bg-violet-600 text-white hover:bg-violet-700"}`}
                              data-testid={`ez-bt-copy-${t.id}`}
                            >
                              {copiedId === t.id ? "Kopiert!" : "Link kopieren"}
                            </button>
                            <button
                              onClick={() => window.open(url, "_blank", "noopener,noreferrer")}
                              className="px-2 py-1 text-[10px] rounded text-violet-700 hover:bg-violet-50 border border-violet-200"
                              data-testid={`ez-bt-open-${t.id}`}
                            >
                              Oeffnen
                            </button>
                            <button
                              onClick={() => revoke(t)}
                              className="px-2 py-1 text-[10px] text-red-600 hover:bg-red-50 rounded"
                              data-testid={`ez-bt-revoke-${t.id}`}
                            >
                              Widerrufen
                            </button>
                          </>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        <div className="flex gap-2 flex-wrap">
          <span className="px-1.5 py-0.5 bg-violet-50 text-violet-700 rounded text-[10px] font-medium">Browser-Only</span>
          <span className="px-1.5 py-0.5 bg-violet-50 text-violet-700 rounded text-[10px] font-medium">Mehrfach-Geraet</span>
          <span className="px-1.5 py-0.5 bg-violet-50 text-violet-700 rounded text-[10px] font-medium">Zeitlich begrenzt</span>
          <span className="px-1.5 py-0.5 bg-violet-50 text-violet-700 rounded text-[10px] font-medium">Audit-Log</span>
        </div>
      </div>
    </div>
  );
}


/* ───── Tankbeleg Pi - One-Liner Setup Generator ───── */
function TankbelegPiSection() {
  const [deviceName, setDeviceName] = useState("");
  const [generating, setGenerating] = useState(false);
  const [setupCmd, setSetupCmd] = useState(null);
  const [copied, setCopied] = useState(false);

  const generateSetup = async () => {
    if (!deviceName.trim()) { toast.error("Bitte Gerätenamen eingeben"); return; }
    setGenerating(true);
    try {
      const res = await api.post("/kirmes/tankbeleg-pi/generate-setup", { device_name: deviceName.trim() });
      setSetupCmd(res.data.setup_command);
      toast.success("Setup-Befehl generiert");
    } catch (e) {
      toast.error("Fehler: " + (e.response?.data?.detail || e.message));
    } finally { setGenerating(false); }
  };

  const copyToClipboard = () => {
    navigator.clipboard.writeText(setupCmd);
    setCopied(true);
    toast.success("In Zwischenablage kopiert");
    setTimeout(() => setCopied(false), 3000);
  };

  return (
    <div className="bg-white border border-gray-200 rounded-lg overflow-hidden" data-testid="tankbeleg-pi-section">
      <div className="flex items-center justify-between px-5 py-4 bg-gradient-to-r from-amber-600 to-orange-500">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-white/20 flex items-center justify-center">
            <Cpu className="w-5 h-5 text-white" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-white">Tankbeleg Pi - Setup Generator</h3>
            <p className="text-[10px] text-amber-100">Raspberry Pi fuer Epson TM-U295 Belegerfassung</p>
          </div>
        </div>
      </div>

      <div className="p-5 space-y-4">
        <p className="text-xs text-gray-500 leading-relaxed">
          Generiert einen Einzeiler-Befehl der auf dem Pi eingefügt wird.
          Das Script installiert alles automatisch: Python, ESC/POS Parser, GPS, Sync-Service.
        </p>

        <div className="flex gap-2 items-end">
          <div className="flex-1">
            <label className="text-xs font-medium text-gray-700 mb-1 block">Gerätename (z.B. Tankwagen-01)</label>
            <Input
              value={deviceName}
              onChange={e => setDeviceName(e.target.value)}
              placeholder="Tankwagen-01"
              className="text-sm"
              data-testid="tankbeleg-device-name"
            />
          </div>
          <Button
            onClick={generateSetup}
            disabled={generating}
            className="bg-amber-600 hover:bg-amber-700 text-white text-xs"
            data-testid="tankbeleg-generate-btn"
          >
            {generating ? "Generiere..." : "Setup generieren"}
          </Button>
        </div>

        {setupCmd && (
          <div className="space-y-2">
            <label className="text-xs font-medium text-gray-700">Diesen Befehl auf dem Pi einfügen:</label>
            <div className="relative">
              <pre className="bg-gray-900 text-green-400 rounded-lg p-3 text-[11px] font-mono overflow-x-auto whitespace-pre-wrap break-all select-all">
                {setupCmd}
              </pre>
              <button
                onClick={copyToClipboard}
                className={`absolute top-2 right-2 px-2 py-1 text-[10px] rounded ${copied ? "bg-green-600 text-white" : "bg-gray-700 text-gray-300 hover:bg-gray-600"}`}
                data-testid="copy-setup-cmd"
              >
                {copied ? "Kopiert!" : "Kopieren"}
              </button>
            </div>
            <p className="text-[10px] text-gray-400">
              Der Pi installiert automatisch alle Abhängigkeiten, erstellt die Config und startet den Service.
              Nach ca. 2 Minuten ist der Pi bereit und erscheint im Portal.
            </p>
          </div>
        )}

        <div className="flex gap-2 flex-wrap">
          <span className="px-1.5 py-0.5 bg-amber-50 text-amber-700 rounded text-[10px] font-medium">ESC/POS Parser</span>
          <span className="px-1.5 py-0.5 bg-amber-50 text-amber-700 rounded text-[10px] font-medium">GPS (gpsd)</span>
          <span className="px-1.5 py-0.5 bg-amber-50 text-amber-700 rounded text-[10px] font-medium">SQLite Offline</span>
          <span className="px-1.5 py-0.5 bg-amber-50 text-amber-700 rounded text-[10px] font-medium">Auto-Sync</span>
          <span className="px-1.5 py-0.5 bg-amber-50 text-amber-700 rounded text-[10px] font-medium">Auto API-Key</span>
        </div>
      </div>
    </div>
  );
}

/* ───── Mosquitto MQTT Broker Setup ───── */
function MosquittoSetupSection() {
  const API = BACKEND_URL;

  const mqttFiles = [
    { name: "Komplettpaket (ZIP)", desc: "Setup-Script + Konfiguration", icon: Package, url: `${API}/api/download/mosquitto-bundle`, filename: "mosquitto_setup_bundle.zip" },
    { name: "setup_mosquitto.sh", desc: "Interaktives Installations-Script", icon: Terminal, url: `${API}/api/download/mosquitto-setup`, filename: "setup_mosquitto.sh" },
    { name: "mosquitto_eventenergie.conf", desc: "Broker-Konfiguration (TLS + Auth)", icon: Settings2, url: `${API}/api/download/mosquitto-config`, filename: "mosquitto_eventenergie.conf" },
  ];

  return (
    <div className="bg-white border border-gray-200 rounded-lg overflow-hidden" data-testid="mosquitto-setup-section">
      <div className="flex items-center justify-between px-5 py-4 bg-gradient-to-r from-emerald-600 to-teal-500">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-white/20 flex items-center justify-center">
            <Server className="w-5 h-5 text-white" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-white">Mosquitto MQTT Broker - Self-Hosted</h3>
            <p className="text-[10px] text-emerald-100">TLS-verschluesselter Broker fuer DSE Webnet Gateways</p>
          </div>
        </div>
        <div className="flex items-center gap-1.5 bg-white/15 rounded-full px-2.5 py-1">
          <Shield className="w-3.5 h-3.5 text-white" />
          <span className="text-[10px] text-white font-medium">Let's Encrypt TLS</span>
        </div>
      </div>

      <div className="p-5 space-y-3">
        <p className="text-xs text-gray-500 leading-relaxed">
          Installiert einen eigenen Mosquitto MQTT Broker mit automatischer TLS-Verschluesselung
          (Let's Encrypt). Unterstuetzt MQTTS (Port 8883), WebSockets (Port 9883) und lokale
          Verbindungen (Port 1883). Ideal fuer DSE Webnet Gateways und das Portal-Backend.
        </p>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
          {mqttFiles.map((file) => {
            const Icon = file.icon;
            return (
              <a
                key={file.filename}
                href={file.url}
                download={file.filename}
                className={`flex items-center gap-3 px-3 py-2.5 rounded-lg border transition-all hover:shadow-sm ${
                  file.filename.endsWith('.zip')
                    ? 'border-emerald-200 bg-emerald-50 hover:border-emerald-400'
                    : 'border-gray-200 bg-gray-50 hover:border-gray-300'
                }`}
                data-testid={`download-${file.filename.replace(/\./g, '-')}`}
              >
                <Icon className={`w-4 h-4 shrink-0 ${file.filename.endsWith('.zip') ? 'text-emerald-600' : 'text-gray-500'}`} />
                <div className="min-w-0 flex-1">
                  <div className="text-xs font-medium text-gray-900 truncate">{file.name}</div>
                  <div className="text-[10px] text-gray-400 truncate">{file.desc}</div>
                </div>
                <Download className="w-3.5 h-3.5 text-gray-400 shrink-0" />
              </a>
            );
          })}
        </div>

        <div className="bg-gray-50 rounded-lg p-3 border border-gray-100 mt-3 space-y-2">
          <p className="text-[10px] text-gray-500 leading-relaxed">
            <strong>Installation:</strong> Dateien auf den Server kopieren und{" "}
            <code className="bg-gray-200 px-1 rounded">sudo bash setup_mosquitto.sh</code> ausfuehren.
            Das Script fragt Domain, E-Mail und Zugangsdaten interaktiv ab.
          </p>
          <p className="text-[10px] text-gray-500 leading-relaxed">
            <strong>Voraussetzung:</strong> Domain muss per DNS A-Record auf den Server zeigen,
            Ports 80 (Zertifikat), 8883 (MQTTS) und 9883 (WSS) muessen offen sein.
          </p>
          <div className="flex gap-2 mt-1 flex-wrap">
            <span className="px-1.5 py-0.5 bg-emerald-50 text-emerald-700 rounded text-[10px] font-medium">MQTTS :8883</span>
            <span className="px-1.5 py-0.5 bg-emerald-50 text-emerald-700 rounded text-[10px] font-medium">WSS :9883</span>
            <span className="px-1.5 py-0.5 bg-emerald-50 text-emerald-700 rounded text-[10px] font-medium">Lokal :1883</span>
            <span className="px-1.5 py-0.5 bg-emerald-50 text-emerald-700 rounded text-[10px] font-medium">Auto-Renewal</span>
            <span className="px-1.5 py-0.5 bg-emerald-50 text-emerald-700 rounded text-[10px] font-medium">DSE Webnet</span>
          </div>
        </div>
      </div>
    </div>
  );
}


/* ───── Hilfsmittel / Pi-Werkzeuge ───── */
function HilfsmittelSection() {
  return (
    <div className="bg-white border border-gray-200 rounded-lg overflow-hidden" data-testid="hilfsmittel-section">
      <div className="flex items-center justify-between px-5 py-4 bg-gradient-to-r from-fuchsia-600 to-purple-500">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-white/20 flex items-center justify-center">
            <Wrench className="w-5 h-5 text-white" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-white">Hilfsmittel</h3>
            <p className="text-[10px] text-fuchsia-100">Diagnose- und Konfigurationswerkzeuge fuer Raspberry Pi</p>
          </div>
        </div>
      </div>
      <div className="p-5 space-y-3">
        {/* Modbus Diagnose Tool */}
        <div className="flex items-start gap-4 p-4 border border-gray-100 rounded-lg hover:border-fuchsia-200 hover:bg-fuchsia-50/30 transition-colors" data-testid="tool-diagnose-modbus">
          <div className="w-10 h-10 rounded-lg bg-fuchsia-100 flex items-center justify-center flex-shrink-0">
            <Terminal className="w-5 h-5 text-fuchsia-600" />
          </div>
          <div className="flex-1 min-w-0">
            <h3 className="text-sm font-semibold text-gray-900">Modbus RTU Diagnose</h3>
            <p className="text-xs text-gray-500 mt-0.5">
              Testet automatisch alle Baudraten, Paritaeten und Slave-IDs um die korrekte DSE 5510 Konfiguration zu finden.
            </p>
            <div className="mt-2 bg-gray-900 rounded-lg p-3 font-mono text-[11px] text-gray-300 overflow-x-auto">
              <p className="text-gray-500"># Auf dem Pi ausfuehren:</p>
              <p>sudo systemctl stop dse5510_sync</p>
              <p>sudo wget "{window.location.origin}/api/generators/diagnose-modbus" -O /opt/dse5510/diagnose_modbus.py</p>
              <p>sudo /opt/dse5510/venv/bin/python3 /opt/dse5510/diagnose_modbus.py</p>
            </div>
          </div>
          <a
            href="/api/generators/diagnose-modbus"
            download="diagnose_modbus.py"
            className="flex items-center gap-1.5 px-3 py-2 bg-fuchsia-600 hover:bg-fuchsia-700 text-white text-xs font-medium rounded-lg transition-colors flex-shrink-0"
            data-testid="download-diagnose-btn"
          >
            <Download className="w-3.5 h-3.5" /> Download
          </a>
        </div>

        {/* DSE 5510 Sync Script */}
        <div className="flex items-start gap-4 p-4 border border-gray-100 rounded-lg hover:border-emerald-200 hover:bg-emerald-50/30 transition-colors" data-testid="tool-sync-script">
          <div className="w-10 h-10 rounded-lg bg-emerald-100 flex items-center justify-center flex-shrink-0">
            <Activity className="w-5 h-5 text-emerald-600" />
          </div>
          <div className="flex-1 min-w-0">
            <h3 className="text-sm font-semibold text-gray-900">DSE 5510 Sync-Skript</h3>
            <p className="text-xs text-gray-500 mt-0.5">
              Haupt-Synchronisationsskript fuer DSE 5510 Controller via RS232 Modbus RTU. Liest Telemetrie jede Sekunde, speichert lokal (SQLite) und synchronisiert mit dem Portal.
            </p>
            <p className="text-[10px] text-gray-400 mt-1">
              Wird ueber Geraeteverwaltung &rarr; Pi Setup automatisch installiert.
            </p>
          </div>
        </div>

        {/* Kirmeskiste Script Info */}
        <div className="flex items-start gap-4 p-4 border border-gray-100 rounded-lg hover:border-sky-200 hover:bg-sky-50/30 transition-colors" data-testid="tool-kirmeskiste">
          <div className="w-10 h-10 rounded-lg bg-sky-100 flex items-center justify-center flex-shrink-0">
            <Zap className="w-5 h-5 text-sky-600" />
          </div>
          <div className="flex-1 min-w-0">
            <h3 className="text-sm font-semibold text-gray-900">Kirmeskiste / Messkoffer Setup</h3>
            <p className="text-xs text-gray-500 mt-0.5">
              Setup-Skript fuer Kirmeskisten und Messkoffer. Wird automatisch ueber die Geraeteverwaltung generiert.
            </p>
            <p className="text-[10px] text-gray-400 mt-1">
              Geraeteverwaltung &rarr; Geraet bearbeiten &rarr; Pi Setup &rarr; Setup generieren
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ───── Software Downloads ───── */
function SoftwareDownloadsSection() {
  const [info, setInfo] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get("/system/downloads/info").then(res => {
      setInfo(res.data);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  const handleDownload = (filename) => {
    const routeMap = {
      "install-mac.sh": "mac",
      "install-win.bat": "win-bat",
      "install-win.ps1": "win-ps1",
      "server-setup-win.ps1": "server-setup-win",
      "db-migrate-win.ps1": "db-migrate-win",
      "deploy-win.ps1": "deploy-win",
      "build-mobile.ps1": "build-mobile-win",
      "build-mobile.sh": "build-mobile-mac",
    };
    openExternal(`${BACKEND_URL}/api/system/downloads/${routeMap[filename] || filename}`);
  };

  const formatSize = (bytes) => {
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1048576) return (bytes / 1024).toFixed(1) + " KB";
    return (bytes / 1048576).toFixed(1) + " MB";
  };

  const platformIcon = (p) => p === "mac" ? <Laptop className="w-4 h-4" /> : p === "linux" ? <Server className="w-4 h-4" /> : <Monitor className="w-4 h-4" />;

  const desktopFiles = info?.files?.filter(f => f.category === "desktop" && f.available) || [];
  const serverFiles = info?.files?.filter(f => f.category === "server" && f.available) || [];
  const mobileFiles = info?.files?.filter(f => f.category === "mobile" && f.available) || [];

  return (
    <div className="bg-white border border-gray-200 rounded-lg overflow-hidden" data-testid="software-downloads-section">
      <div className="bg-gradient-to-r from-violet-600 to-fuchsia-600 px-5 py-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Download className="w-5 h-5 text-white" />
          <h3 className="text-sm font-semibold text-white">Software Downloads</h3>
          {info?.version && <span className="bg-white/20 text-white text-[10px] font-bold px-2 py-0.5 rounded-full">v{info.version}</span>}
        </div>
      </div>
      <div className="p-5">
        {loading ? (
          <div className="flex items-center justify-center py-6">
            <Loader2 className="w-5 h-5 animate-spin text-gray-400" />
          </div>
        ) : !info ? (
          <p className="text-sm text-gray-500 text-center py-4">Downloads nicht verfügbar</p>
        ) : (
          <div className="space-y-5">
            {/* Desktop Apps */}
            {desktopFiles.length > 0 && (
              <div>
                <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Desktop Apps</h4>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                  {desktopFiles.map(f => (
                    <button key={f.filename} onClick={() => handleDownload(f.filename)}
                      className="flex items-center gap-3 p-4 rounded-lg border border-gray-200 hover:border-fuchsia-300 hover:bg-fuchsia-50 transition-all text-left group"
                      data-testid={`download-${f.filename.replace(/\./g, '-')}`}>
                      <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${f.platform === "mac" ? "bg-gray-900 text-white" : "bg-blue-600 text-white"}`}>
                        {platformIcon(f.platform)}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="text-sm font-medium text-gray-900 group-hover:text-fuchsia-700">{f.label}</div>
                        <div className="text-xs text-gray-400">{formatSize(f.size_bytes)}</div>
                      </div>
                      <Download className="w-4 h-4 text-gray-300 group-hover:text-fuchsia-500" />
                    </button>
                  ))}
                </div>
                <div className="mt-3 bg-gray-50 rounded-lg p-3 text-xs text-gray-500 space-y-1">
                  <p><strong>Mac:</strong> Terminal öffnen und eintippen: <code className="bg-gray-200 px-1.5 py-0.5 rounded text-gray-700">bash ~/Downloads/install-mac.sh</code></p>
                  <p><strong>Windows:</strong> Die .bat Datei doppelklicken</p>
                </div>
              </div>
            )}

            {/* Mobile Apps */}
            {mobileFiles.length > 0 && (
              <div>
                <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Mobile Apps (Android / iOS)</h4>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {mobileFiles.map(f => (
                    <button key={f.filename} onClick={() => handleDownload(f.filename)}
                      className="flex items-center gap-3 p-4 rounded-lg border border-gray-200 hover:border-emerald-300 hover:bg-emerald-50 transition-all text-left group"
                      data-testid={`download-${f.filename.replace(/\./g, '-')}`}>
                      <div className="w-10 h-10 rounded-lg flex items-center justify-center bg-emerald-600 text-white">
                        <MonitorSmartphone className="w-4 h-4" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="text-sm font-medium text-gray-900 group-hover:text-emerald-700">{f.label}</div>
                        <div className="text-xs text-gray-400">{formatSize(f.size_bytes)}</div>
                      </div>
                      <Download className="w-4 h-4 text-gray-300 group-hover:text-emerald-500" />
                    </button>
                  ))}
                </div>
                <div className="mt-3 bg-gray-50 rounded-lg p-3 text-xs text-gray-500 space-y-1">
                  <p><strong>Android APK:</strong> <code className="bg-gray-200 px-1.5 py-0.5 rounded text-gray-700">.\build-mobile.ps1 android</code> (braucht Android Studio + JDK 17)</p>
                  <p><strong>iOS App:</strong> <code className="bg-gray-200 px-1.5 py-0.5 rounded text-gray-700">bash build-mobile.sh ios</code> (braucht Mac + Xcode + Apple Developer Account)</p>
                </div>
              </div>
            )}

            {/* Server Scripts */}
            {serverFiles.length > 0 && (
              <div>
                <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Server-Administration</h4>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                  {serverFiles.map(f => (
                    <button key={f.filename} onClick={() => handleDownload(f.filename)}
                      className="flex items-center gap-3 p-3 rounded-lg border border-gray-200 hover:border-violet-300 hover:bg-violet-50 transition-all text-left group"
                      data-testid={`download-${f.filename.replace(/\./g, '-')}`}>
                      <div className="w-9 h-9 rounded-lg flex items-center justify-center bg-slate-700 text-white">
                        {platformIcon(f.platform)}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="text-sm font-medium text-gray-900 group-hover:text-violet-700">{f.label}</div>
                        <div className="text-xs text-gray-400">{formatSize(f.size_bytes)}</div>
                      </div>
                      <Download className="w-4 h-4 text-gray-300 group-hover:text-violet-500" />
                    </button>
                  ))}
                </div>
                <div className="mt-3 bg-gray-50 rounded-lg p-3 text-xs text-gray-500 space-y-1">
                  <p><strong>1.</strong> Neuer Server (Win 2019): PowerShell als Admin <code className="bg-gray-200 px-1.5 py-0.5 rounded text-gray-700">.\server-setup-win.ps1</code></p>
                  <p><strong>2.</strong> Alter Server: <code className="bg-gray-200 px-1.5 py-0.5 rounded text-gray-700">.\db-migrate-win.ps1 export</code> → Datei auf neuen Server kopieren</p>
                  <p><strong>3.</strong> Neuer Server: <code className="bg-gray-200 px-1.5 py-0.5 rounded text-gray-700">.\db-migrate-win.ps1 import backup.gz</code></p>
                  <p><strong>4.</strong> Code deployen: <code className="bg-gray-200 px-1.5 py-0.5 rounded text-gray-700">.\deploy-win.ps1 https://github.com/REPO.git</code></p>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

/* ───── Kirmeskiste OTA Update Management ───── */
function OtaUpdateSection() {
  const [devices, setDevices] = useState([]);
  const [typeStats, setTypeStats] = useState({});
  const [scriptTypes, setScriptTypes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [actionBusy, setActionBusy] = useState("");

  const token = localStorage.getItem("token");

  const loadData = useCallback(async () => {
    try {
      const res = await api.get("/system/ota/devices", { headers: { Authorization: `Bearer ${token}` } });
      setDevices(res.data?.devices || []);
      setTypeStats(res.data?.type_stats || {});
      setScriptTypes(res.data?.script_types || []);
    } catch {}
    setLoading(false);
  }, [token]);

  useEffect(() => { loadData(); }, [loadData]);

  const forceUpdateOne = async (device) => {
    if (!window.confirm(`Update für "${device.device_name || device.device_id}" erzwingen?\nDas Gerät lädt das aktuelle Skript beim nächsten Polling neu (innerhalb weniger Minuten).`)) return;
    setActionBusy(device.device_id);
    try {
      await api.post(`/system/ota/devices/${device.device_id}/force-update`, null, { headers: { Authorization: `Bearer ${token}` } });
      toast.success(`Force-Update für ${device.device_name || device.device_id.slice(0, 8)} gesetzt`);
      loadData();
    } catch (e) {
      toast.error(`Fehler: ${e?.response?.data?.detail || e.message}`);
    }
    setActionBusy("");
  };

  const cancelForceUpdate = async (device) => {
    setActionBusy(device.device_id);
    try {
      await api.post(`/system/ota/devices/${device.device_id}/cancel-force-update`, null, { headers: { Authorization: `Bearer ${token}` } });
      toast.success("Force-Update abgebrochen");
      loadData();
    } catch (e) {
      toast.error(`Fehler: ${e?.response?.data?.detail || e.message}`);
    }
    setActionBusy("");
  };

  const forceUpdateAll = async (deviceType) => {
    const label = deviceType ? typeLabels[deviceType] || deviceType : "ALLE Geräte";
    if (!window.confirm(`Update für ${label} erzwingen?\nAlle betroffenen Geräte laden das aktuelle Skript beim nächsten Polling neu.`)) return;
    setActionBusy("bulk");
    try {
      const res = await api.post(`/system/ota/devices/force-update-all`, { device_type: deviceType || "" }, { headers: { Authorization: `Bearer ${token}` } });
      toast.success(`Force-Update gesetzt für ${res.data?.matched || 0} Geräte`);
      loadData();
    } catch (e) {
      toast.error(`Fehler: ${e?.response?.data?.detail || e.message}`);
    }
    setActionBusy("");
  };

  const totalDevices = devices.length;
  const needsUpdate = devices.filter(d => d.needs_update).length;
  const upToDate = totalDevices - needsUpdate;

  const typeLabels = { kirmeskiste: "Kirmeskiste", messkoffer: "Messkoffer", lkw: "LKW", stromerzeuger: "Stromerzeuger", dse: "DSE Gateway", tankwagen: "Tankwagen-Pi" };
  const typeColors = { kirmeskiste: "bg-sky-100 text-sky-700 border-sky-200", messkoffer: "bg-purple-100 text-purple-700 border-purple-200", lkw: "bg-amber-100 text-amber-700 border-amber-200", stromerzeuger: "bg-emerald-100 text-emerald-700 border-emerald-200", dse: "bg-rose-100 text-rose-700 border-rose-200", tankwagen: "bg-orange-100 text-orange-700 border-orange-200" };

  return (
    <div className="bg-white border border-gray-200 rounded-lg overflow-hidden" data-testid="ota-update-section">
      <div className="bg-gradient-to-r from-sky-600 to-indigo-600 px-5 py-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Radio className="w-5 h-5 text-white" />
          <h3 className="text-sm font-semibold text-white">Geräte OTA-Updates</h3>
          {totalDevices > 0 && <span className="bg-white/20 text-white text-[10px] font-bold px-2 py-0.5 rounded-full">{totalDevices} Geräte</span>}
        </div>
        <div className="flex items-center gap-2">
          {totalDevices > 0 && (
            <Button size="sm" onClick={() => forceUpdateAll("")} disabled={actionBusy === "bulk"} className="bg-amber-500/90 hover:bg-amber-500 text-white text-xs" data-testid="ota-force-update-all">
              <Upload className="w-3.5 h-3.5 mr-1" /> Alle updaten
            </Button>
          )}
          <Button size="sm" onClick={loadData} className="bg-white/20 hover:bg-white/30 text-white text-xs">
            <RefreshCw className="w-3.5 h-3.5 mr-1" /> Aktualisieren
          </Button>
        </div>
      </div>

      <div className="p-4 space-y-4">
        {/* Typ-Übersicht mit "Alle updaten"-Button pro Typ */}
        {Object.keys(typeStats).length > 0 && (
          <div>
            <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Nach Gerätetyp</h4>
            <div className="flex flex-wrap gap-2">
              {Object.entries(typeStats).map(([type, stats]) => (
                <div key={type} className={`px-3 py-2 rounded-lg border text-xs ${typeColors[type] || "bg-gray-100 text-gray-700 border-gray-200"}`}>
                  <div className="flex items-center justify-between gap-2 mb-0.5">
                    <p className="font-semibold">{typeLabels[type] || type}</p>
                    <button
                      onClick={() => forceUpdateAll(type)}
                      disabled={actionBusy === "bulk" || stats.total === 0}
                      title={`Update für alle ${typeLabels[type] || type}-Geräte erzwingen`}
                      className="text-[10px] underline opacity-70 hover:opacity-100 disabled:opacity-40"
                      data-testid={`ota-force-type-${type}`}
                    >
                      Alle updaten
                    </button>
                  </div>
                  <p>{stats.total} Geräte · <span className="text-green-700">{stats.up_to_date} aktuell</span>{stats.needs_update > 0 && <span className="text-orange-600"> · {stats.needs_update} Update</span>}</p>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Gesamtstatus */}
        {totalDevices > 0 && (
          <div className="flex items-center gap-4 text-xs">
            <div className="flex items-center gap-1.5"><Check className="w-4 h-4 text-green-600" /><span className="text-green-700 font-semibold">{upToDate} aktuell</span></div>
            {needsUpdate > 0 && <div className="flex items-center gap-1.5"><Upload className="w-4 h-4 text-orange-500" /><span className="text-orange-600 font-semibold">{needsUpdate} Update ausstehend</span></div>}
          </div>
        )}

        {/* Geräteliste mit Per-Device-Force-Update-Button */}
        {loading ? (
          <div className="flex items-center gap-2 text-gray-400 text-xs"><Loader2 className="w-4 h-4 animate-spin" /> Laden...</div>
        ) : devices.length === 0 ? (
          <p className="text-xs text-gray-400">Noch keine Geräte verbunden. Die Geräte melden sich automatisch beim ersten Start.</p>
        ) : (
          <div>
            <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Alle Geräte ({totalDevices})</h4>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
              {devices.map(d => (
                <div key={d.device_id} className={`flex items-center gap-3 px-3 py-2 rounded-lg border text-xs ${
                  d.force_update ? "border-amber-300 bg-amber-50" : d.needs_update ? "border-orange-200 bg-orange-50" : "border-green-200 bg-green-50"
                }`} data-testid={`ota-device-${d.device_id}`}>
                  <div className={`w-2 h-2 rounded-full flex-shrink-0 ${d.force_update ? "bg-amber-500 animate-pulse" : d.needs_update ? "bg-orange-400" : "bg-green-500"}`} />
                  <div className="flex-1 min-w-0">
                    <p className="font-semibold text-gray-800 truncate">{d.device_name || d.serial || d.device_id?.slice(0, 8)}</p>
                    <div className="flex items-center gap-1.5 flex-wrap">
                      <span className={`px-1.5 py-0.5 rounded text-[9px] font-medium ${typeColors[d.device_type] || "bg-gray-100 text-gray-600"}`}>{typeLabels[d.device_type] || d.device_type}</span>
                      {d.current_version && <span className="text-gray-500">v{d.current_version}</span>}
                      {d.force_update && <span className="text-amber-700 font-semibold">⚡ Force-Update pending</span>}
                      {!d.force_update && d.needs_update && <span className="text-orange-600">→ Update</span>}
                    </div>
                  </div>
                  <div className="flex items-center gap-1 flex-shrink-0">
                    <p className="text-gray-400 text-[10px]">{d.last_seen?.slice(11, 16) || "—"}</p>
                    {d.force_update ? (
                      <button
                        onClick={() => cancelForceUpdate(d)}
                        disabled={actionBusy === d.device_id}
                        title="Pending Force-Update abbrechen"
                        className="text-amber-700 hover:text-amber-900 disabled:opacity-40 px-1"
                        data-testid={`ota-cancel-force-${d.device_id}`}
                      >
                        <XCircle className="w-3.5 h-3.5" />
                      </button>
                    ) : (
                      <button
                        onClick={() => forceUpdateOne(d)}
                        disabled={actionBusy === d.device_id}
                        title="Update erzwingen (auch wenn Hash identisch)"
                        className="text-sky-600 hover:text-sky-800 disabled:opacity-40 px-1"
                        data-testid={`ota-force-${d.device_id}`}
                      >
                        <Upload className="w-3.5 h-3.5" />
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}


/* ───── FinTS Banking Integration ───── */
function FinTSBankingSection() {
  const [status, setStatus] = useState(null);
  const [testing, setTesting] = useState(false);
  const [checking, setChecking] = useState(false);
  const [lastResult, setLastResult] = useState(null);
  const [transactions, setTransactions] = useState(null);
  const [enabled, setEnabled] = useState(false);
  const [toggling, setToggling] = useState(false);
  const [stateInfo, setStateInfo] = useState(null);
  const [resetting, setResetting] = useState(false);

  const loadStateInfo = async () => {
    try {
      const r = await api.get("/kirmes/fints/state-info");
      setStateInfo(r.data);
    } catch { setStateInfo(null); }
  };

  const resetState = async () => {
    if (!window.confirm("Bank-Anmeldung zurücksetzen? Beim nächsten Abruf wird wieder eine pushTAN angefordert.")) return;
    setResetting(true);
    try {
      await api.post("/kirmes/fints/reset-state");
      toast.success("Bank-Anmeldung zurückgesetzt");
      await loadStateInfo();
    } catch { toast.error("Fehler beim Zurücksetzen"); }
    finally { setResetting(false); }
  };

  const checkStatus = async () => {
    try {
      const res = await api.post("/kirmes/fints/save-credentials");
      setStatus(res.data);
      if (res.data.last_result) setLastResult(res.data.last_result);
      setEnabled(res.data.enabled !== false);
    } catch { setStatus({ status: "error", message: "Fehler beim Prüfen" }); }
  };

  const toggleEnabled = async () => {
    setToggling(true);
    try {
      const res = await api.post("/kirmes/fints/toggle", { enabled: !enabled });
      setEnabled(res.data.enabled);
      toast.success(res.data.enabled ? "FinTS Abgleich aktiviert" : "FinTS Abgleich deaktiviert");
    } catch { toast.error("Fehler"); }
    finally { setToggling(false); }
  };

  const testConnection = async () => {
    setTesting(true);
    setTransactions(null);
    try {
      const res = await api.post("/kirmes/fints/test-connection");
      const d = res.data || {};
      if (d.ok) {
        toast.success(`Verbindung OK – ${d.accounts_found} Konto(s) gefunden`);
        setTransactions({ test_ok: true, ...d });
      } else {
        toast.error(`Login fehlgeschlagen (${d.stage})`);
        setTransactions({ test_ok: false, ...d });
      }
    } catch (e) {
      toast.error("Verbindung fehlgeschlagen: " + (e.response?.data?.detail || e.message));
    } finally { setTesting(false); loadStateInfo(); }
  };

  const loadTransactions = async () => {
    setTesting(true);
    try {
      const res = await api.get("/kirmes/fints/transactions?days=7");
      setTransactions(res.data);
      toast.success(`${res.data.count} Transaktionen geladen`);
    } catch (e) {
      toast.error("Abruf fehlgeschlagen: " + (e.response?.data?.detail || e.message));
    } finally { setTesting(false); loadStateInfo(); }
  };

  const runCheck = async () => {
    setChecking(true);
    try {
      const res = await api.post("/kirmes/fints/check-payments");
      setLastResult(res.data);
      toast.success(`Abgleich: ${res.data.matched} Zuordnungen, ${res.data.auto_marked} automatisch bezahlt`);
    } catch (e) {
      toast.error("Fehler: " + (e.response?.data?.detail || e.message));
    } finally { setChecking(false); loadStateInfo(); }
  };

  useEffect(() => { checkStatus(); loadStateInfo(); }, []);

  const isConfigured = status?.status === "configured";

  return (
    <div className="bg-white border border-gray-200 rounded-lg overflow-hidden" data-testid="fints-banking-section">
      <div className="px-5 py-4 bg-gray-50 border-b border-gray-200 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <CircleDollarSign className="w-5 h-5 text-emerald-500" />
          <h3 className="text-sm font-semibold text-gray-900">FinTS Banking (Sparkasse Mayen)</h3>
        </div>
        <div className="flex items-center gap-3">
          <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${isConfigured ? "bg-emerald-100 text-emerald-700" : "bg-amber-100 text-amber-700"}`}>
            {isConfigured ? "Konfiguriert" : "Nicht konfiguriert"}
          </span>
          {isConfigured && (
            <button
              onClick={toggleEnabled}
              disabled={toggling}
              className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${enabled ? "bg-emerald-500" : "bg-gray-300"}`}
              data-testid="fints-toggle"
            >
              <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${enabled ? "translate-x-6" : "translate-x-1"}`} />
            </button>
          )}
        </div>
      </div>
      <div className="p-5 space-y-4">
        {/* Bank-Anmeldung-Indikator (MoneyMoney-Stil) */}
        {stateInfo && (() => {
          const has = stateInfo.has_state;
          const ageDays = stateInfo.age_days;
          const renewIn = stateInfo.sca_renewal_in_days;
          let bg = "bg-gray-50 border-gray-200";
          let dot = "bg-gray-400";
          let label = "Keine Bank-Anmeldung";
          let sub = "Beim ersten Abruf wird eine pushTAN angefordert.";
          if (has && renewIn !== null && renewIn !== undefined) {
            if (renewIn > 30) {
              bg = "bg-emerald-50 border-emerald-200"; dot = "bg-emerald-500 animate-pulse";
              label = "Bank-Verbindung aktiv";
              sub = `Nächste pushTAN-Bestätigung in ${renewIn} Tagen fällig.`;
            } else if (renewIn > 0) {
              bg = "bg-amber-50 border-amber-200"; dot = "bg-amber-500 animate-pulse";
              label = "Bank-Verbindung aktiv – Erneuerung bald";
              sub = `Nur noch ${renewIn} Tag${renewIn === 1 ? "" : "e"} bis zur nächsten pushTAN.`;
            } else {
              bg = "bg-rose-50 border-rose-200"; dot = "bg-rose-500";
              label = "pushTAN-Bestätigung fällig";
              sub = "90-Tage-Frist abgelaufen – nächster Abruf erfordert pushTAN.";
            }
          }
          return (
            <div className={`border rounded-lg p-3 flex items-start justify-between gap-3 ${bg}`} data-testid="fints-state-indicator">
              <div className="flex items-start gap-3 min-w-0">
                <span className={`mt-1.5 inline-block w-2.5 h-2.5 rounded-full ${dot} flex-shrink-0`} />
                <div className="min-w-0">
                  <div className="text-sm font-semibold text-gray-900">{label}</div>
                  <div className="text-xs text-gray-600 mt-0.5">{sub}</div>
                  {has && ageDays !== null && (
                    <div className="text-[11px] text-gray-400 mt-1">
                      Anmeldung gespeichert vor {ageDays} Tag{ageDays === 1 ? "" : "en"}
                      {stateInfo.updated_at && ` (${new Date(stateInfo.updated_at).toLocaleDateString("de-DE")})`}
                    </div>
                  )}
                </div>
              </div>
              {has && (
                <button
                  onClick={resetState}
                  disabled={resetting}
                  className="text-xs text-gray-500 hover:text-rose-600 underline whitespace-nowrap flex-shrink-0"
                  data-testid="fints-reset-state-btn"
                  title="Bank-Anmeldung zurücksetzen (erfordert neue pushTAN)"
                >
                  Zurücksetzen
                </button>
              )}
            </div>
          );
        })()}

        <div className="text-sm text-gray-600">
          <p>Automatischer Kontoabgleich mit offenen Rechnungen (alle 6 Stunden).</p>
          <p className="text-xs text-gray-400 mt-1">IBAN: DE28 5765 0010 0098 0667 56 · BLZ: 57650010</p>
          {status?.last_check && (
            <p className="text-xs text-emerald-600 mt-1">Letzter Abgleich: {new Date(status.last_check).toLocaleString("de-DE")}</p>
          )}
        </div>

        {!isConfigured && (
          <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 text-sm text-amber-800">
            Bitte auf dem Server in der <code className="bg-amber-100 px-1 rounded">.env</code> Datei eintragen:
            <pre className="mt-2 text-xs bg-amber-100 p-2 rounded">
{`FINTS_USER=deine_kennung
FINTS_PIN=dein_pin
FINTS_IBAN=DE28576500100098066756`}
            </pre>
          </div>
        )}

        <div className="flex flex-wrap gap-2">
          <Button
            size="sm"
            variant="outline"
            onClick={testConnection}
            disabled={testing || !isConfigured}
            className="text-xs"
            data-testid="fints-test-btn"
          >
            {testing ? "Teste..." : "Verbindung testen"}
          </Button>
          <Button
            size="sm"
            onClick={runCheck}
            disabled={checking || !isConfigured}
            className="text-xs bg-emerald-600 hover:bg-emerald-700 text-white"
            data-testid="fints-check-btn"
          >
            {checking ? "Prüfe..." : "Jetzt Rechnungen abgleichen"}
          </Button>
        </div>

        {lastResult && (
          <div className="bg-gray-50 border border-gray-200 rounded-lg p-3 text-sm space-y-1">
            <p className="font-medium text-gray-900">Letzter Abgleich:</p>
            <div className="grid grid-cols-2 gap-x-4 text-xs text-gray-600">
              <span>Transaktionen geprüft:</span><span className="font-mono">{lastResult.checked}</span>
              <span>Zuordnungen gefunden:</span><span className="font-mono">{lastResult.matched}</span>
              <span>Automatisch bezahlt:</span><span className="font-mono font-semibold text-emerald-600">{lastResult.auto_marked}</span>
              <span>Vorschläge für Admin:</span><span className="font-mono">{lastResult.suggestions || 0}</span>
            </div>
          </div>
        )}

        {transactions && transactions.test_ok === false && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-sm space-y-2" data-testid="fints-test-error">
            <div className="flex items-center gap-2 font-semibold text-red-800">
              <XCircle className="w-4 h-4" /> FinTS-Login fehlgeschlagen
            </div>
            <div className="text-xs text-red-700 font-mono whitespace-pre-wrap break-all">{transactions.error}</div>
            <div className="text-xs text-gray-700 bg-white border border-red-100 rounded p-2">
              <span className="font-semibold">Hinweis:</span> {transactions.hint}
            </div>
            <div className="text-[10px] text-gray-500">
              BLZ: {transactions.blz} · URL: {transactions.url} · User: {transactions.user_first_chars}
            </div>
          </div>
        )}

        {transactions && transactions.test_ok === true && (
          <div className="bg-emerald-50 border border-emerald-200 rounded-lg p-3 text-sm space-y-2" data-testid="fints-test-ok">
            <div className="flex items-center gap-2 font-semibold text-emerald-800">
              <Check className="w-4 h-4" /> FinTS-Login erfolgreich
            </div>
            {transactions.primary_found ? (
              <div className="text-xs text-emerald-700">
                Hauptkonto gefunden:
                <div className="mt-1 bg-white border border-emerald-200 rounded px-2 py-1 font-mono text-gray-800">
                  {transactions.primary_iban} ({(transactions.accounts || [])[0]?.bic})
                </div>
              </div>
            ) : (
              <div className="text-xs text-amber-700">
                <strong>Warnung:</strong> Hauptkonto <span className="font-mono">{transactions.primary_iban}</span> nicht gefunden.
                <div className="mt-1">Verfügbare Konten:</div>
                <ul className="text-xs text-gray-700 ml-4 list-disc">
                  {(transactions.accounts || []).map((a, i) => (
                    <li key={i} className="font-mono">{a.iban} ({a.bic})</li>
                  ))}
                </ul>
                <div className="mt-1 text-gray-600">
                  Bitte <code>FINTS_IBAN</code> in der <code>.env</code> auf eine dieser IBANs setzen.
                </div>
              </div>
            )}
            <Button size="sm" variant="outline" onClick={loadTransactions} className="text-xs mt-2" data-testid="fints-load-tx-btn">
              Transaktionen der letzten 7 Tage laden
            </Button>
          </div>
        )}

        {transactions && transactions.transactions && (
          <div className="bg-gray-50 border border-gray-200 rounded-lg p-3">
            <p className="text-sm font-medium text-gray-900 mb-2">Letzte {transactions.count} Transaktionen (7 Tage):</p>
            <div className="max-h-48 overflow-y-auto space-y-1">
              {transactions.transactions.slice(0, 15).map((tx, i) => (
                <div key={i} className="text-xs flex justify-between border-b border-gray-100 py-1">
                  <div className="flex-1 min-w-0">
                    <span className="text-gray-500">{tx.date}</span>
                    <span className="ml-2 text-gray-700 truncate">{tx.applicant_name || tx.posting_text}</span>
                  </div>
                  <span className={`font-mono ml-2 ${tx.amount > 0 ? "text-emerald-600" : "text-red-600"}`}>
                    {tx.amount > 0 ? "+" : ""}{tx.amount?.toFixed(2)} EUR
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}


/* ───── Backup-System Einstellungen ───── */
function FinTSVRBankingSection() {
  const [status, setStatus] = useState(null);
  const [testing, setTesting] = useState(false);
  const [checking, setChecking] = useState(false);
  const [lastResult, setLastResult] = useState(null);
  const [transactions, setTransactions] = useState(null);
  const [enabled, setEnabled] = useState(false);
  const [toggling, setToggling] = useState(false);
  const [stateInfo, setStateInfo] = useState(null);
  const [resetting, setResetting] = useState(false);

  const withToken = (extra = {}) => ({ params: { token: localStorage.getItem("token"), ...extra } });

  const loadStateInfo = async () => {
    try { const r = await api.get("/fints/vr/state-info", withToken()); setStateInfo(r.data); }
    catch { setStateInfo(null); }
  };

  const resetState = async () => {
    if (!window.confirm("VR-Bank-Anmeldung zurücksetzen? Beim nächsten Abruf wird eine pushTAN angefordert.")) return;
    setResetting(true);
    try { await api.post("/fints/vr/reset-state", null, withToken()); toast.success("VR-Bank-Anmeldung zurückgesetzt"); await loadStateInfo(); }
    catch { toast.error("Fehler beim Zurücksetzen"); }
    finally { setResetting(false); }
  };

  const checkStatus = async () => {
    try {
      const res = await api.post("/fints/vr/save-credentials", null, withToken());
      setStatus(res.data);
      if (res.data.last_result) setLastResult(res.data.last_result);
      setEnabled(res.data.enabled !== false);
    } catch { setStatus({ status: "error", message: "Fehler beim Prüfen" }); }
  };

  const toggleEnabled = async () => {
    setToggling(true);
    try {
      const res = await api.post("/fints/vr/toggle", { enabled: !enabled }, withToken());
      setEnabled(res.data.enabled);
      toast.success(res.data.enabled ? "VR-FinTS aktiviert" : "VR-FinTS deaktiviert");
    } catch { toast.error("Fehler"); }
    finally { setToggling(false); }
  };

  const testConnection = async () => {
    setTesting(true); setTransactions(null);
    try {
      const res = await api.post("/fints/vr/test-connection", null, { ...withToken(), timeout: 180000 });
      const d = res.data || {};
      if (d.ok) { toast.success(`Verbindung OK – ${d.accounts_found} Konto(s) gefunden`); setTransactions({ test_ok: true, ...d }); }
      else { toast.error(`Login fehlgeschlagen (${d.stage})`); setTransactions({ test_ok: false, ...d }); }
    } catch (e) { toast.error("Verbindung fehlgeschlagen: " + (e.response?.data?.detail || e.message)); }
    finally { setTesting(false); loadStateInfo(); }
  };

  const loadTransactions = async () => {
    setTesting(true);
    try {
      const res = await api.get("/fints/vr/transactions", { ...withToken({ days: 7 }), timeout: 180000 });
      setTransactions(res.data);
      toast.success(`${res.data.count} Transaktionen geladen`);
    } catch (e) { toast.error("Abruf fehlgeschlagen: " + (e.response?.data?.detail || e.message)); }
    finally { setTesting(false); loadStateInfo(); }
  };

  const runCheck = async () => {
    setChecking(true);
    try {
      const res = await api.post("/fints/vr/check-payments", null, { ...withToken(), timeout: 180000 });
      setLastResult(res.data);
      toast.success(`Abgleich: ${res.data.matched} Zuordnungen, ${res.data.auto_marked} auto-bezahlt`);
    } catch (e) { toast.error("Fehler: " + (e.response?.data?.detail || e.message)); }
    finally { setChecking(false); loadStateInfo(); }
  };

  useEffect(() => { checkStatus(); loadStateInfo(); }, []);

  const isConfigured = status?.status === "configured";

  return (
    <div className="bg-white border border-gray-200 rounded-lg overflow-hidden" data-testid="fints-vr-banking-section">
      <div className="px-5 py-4 bg-gray-50 border-b border-gray-200 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <CircleDollarSign className="w-5 h-5 text-purple-500" />
          <h3 className="text-sm font-semibold text-gray-900">FinTS Banking (Volksbank / VR-Bank)</h3>
        </div>
        <div className="flex items-center gap-3">
          <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${isConfigured ? "bg-emerald-100 text-emerald-700" : "bg-amber-100 text-amber-700"}`}>
            {isConfigured ? "Konfiguriert" : "Nicht konfiguriert"}
          </span>
          {isConfigured && (
            <button onClick={toggleEnabled} disabled={toggling}
              className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${enabled ? "bg-emerald-500" : "bg-gray-300"}`}
              data-testid="fints-vr-toggle">
              <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${enabled ? "translate-x-6" : "translate-x-1"}`} />
            </button>
          )}
        </div>
      </div>
      <div className="p-5 space-y-4">
        {stateInfo && (() => {
          const has = stateInfo.has_state;
          const ageDays = stateInfo.age_days;
          const renewIn = stateInfo.sca_renewal_in_days;
          let bg = "bg-gray-50 border-gray-200"; let dot = "bg-gray-400";
          let label = "Keine Bank-Anmeldung"; let sub = "Beim ersten Abruf wird eine pushTAN angefordert.";
          if (has && renewIn !== null && renewIn !== undefined) {
            if (renewIn > 30) { bg = "bg-emerald-50 border-emerald-200"; dot = "bg-emerald-500 animate-pulse"; label = "Bank-Verbindung aktiv"; sub = `Nächste pushTAN in ${renewIn} Tagen fällig.`; }
            else if (renewIn > 0) { bg = "bg-amber-50 border-amber-200"; dot = "bg-amber-500 animate-pulse"; label = "Erneuerung bald"; sub = `Nur noch ${renewIn} Tag${renewIn === 1 ? "" : "e"} bis pushTAN.`; }
            else { bg = "bg-rose-50 border-rose-200"; dot = "bg-rose-500"; label = "pushTAN-Bestätigung fällig"; sub = "90-Tage-Frist abgelaufen."; }
          }
          return (
            <div className={`border rounded-lg p-3 flex items-start justify-between gap-3 ${bg}`} data-testid="fints-vr-state-indicator">
              <div className="flex items-start gap-3 min-w-0">
                <span className={`mt-1.5 inline-block w-2.5 h-2.5 rounded-full ${dot} flex-shrink-0`} />
                <div className="min-w-0">
                  <div className="text-sm font-semibold text-gray-900">{label}</div>
                  <div className="text-xs text-gray-600 mt-0.5">{sub}</div>
                  {has && ageDays !== null && (
                    <div className="text-[11px] text-gray-400 mt-1">
                      Anmeldung gespeichert vor {ageDays} Tag{ageDays === 1 ? "" : "en"}
                      {stateInfo.updated_at && ` (${new Date(stateInfo.updated_at).toLocaleDateString("de-DE")})`}
                    </div>
                  )}
                </div>
              </div>
              {has && (
                <button onClick={resetState} disabled={resetting}
                  className="text-xs text-gray-500 hover:text-rose-600 underline whitespace-nowrap flex-shrink-0"
                  data-testid="fints-vr-reset-state-btn">
                  Zurücksetzen
                </button>
              )}
            </div>
          );
        })()}

        <div className="text-sm text-gray-600">
          <p>Zweite Bank für Kontoabgleich mit offenen Eingangsrechnungen.</p>
          {status?.iban && <p className="text-xs text-gray-400 mt-1">IBAN: {status.iban} · BLZ: {status.blz}</p>}
          {status?.last_check && (
            <p className="text-xs text-emerald-600 mt-1">Letzter Abgleich: {new Date(status.last_check).toLocaleString("de-DE")}</p>
          )}
        </div>

        {!isConfigured && (
          <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 text-sm text-amber-800">
            Bitte auf dem Server in der <code className="bg-amber-100 px-1 rounded">.env</code> Datei eintragen:
            <pre className="mt-2 text-xs bg-amber-100 p-2 rounded">
{`FINTS_VB_URL=https://hbci-pintan-vr.fiducia.de/cgi-bin/hbciservlet
FINTS_VB_BLZ=deine_vr_blz
FINTS_VB_USER=vr_netkey_oder_alias
FINTS_VB_PIN=dein_online_banking_pin
FINTS_VB_IBAN=DE...`}
            </pre>
            <p className="text-xs mt-2">Nach dem Speichern Backend neu starten (<code>sudo supervisorctl restart backend</code>).</p>
          </div>
        )}

        <div className="flex flex-wrap gap-2">
          <Button size="sm" variant="outline" onClick={testConnection} disabled={testing || !isConfigured}
            className="text-xs" data-testid="fints-vr-test-btn">
            {testing ? "Teste..." : "Verbindung testen"}
          </Button>
          <Button size="sm" onClick={runCheck} disabled={checking || !isConfigured}
            className="text-xs bg-purple-600 hover:bg-purple-700 text-white" data-testid="fints-vr-check-btn">
            {checking ? "Prüfe..." : "Jetzt Rechnungen abgleichen"}
          </Button>
        </div>

        {lastResult && (
          <div className="bg-gray-50 border border-gray-200 rounded-lg p-3 text-sm space-y-1">
            <p className="font-medium text-gray-900">Letzter Abgleich:</p>
            <div className="grid grid-cols-2 gap-x-4 text-xs text-gray-600">
              <span>Transaktionen geprüft:</span><span className="font-mono">{lastResult.checked}</span>
              <span>Zuordnungen gefunden:</span><span className="font-mono">{lastResult.matched}</span>
              <span>Automatisch bezahlt:</span><span className="font-mono font-semibold text-emerald-600">{lastResult.auto_marked}</span>
              <span>Admin-Aufgaben:</span><span className="font-mono">{lastResult.admin_tasks || 0}</span>
              <span>Mehrdeutig:</span><span className="font-mono">{lastResult.ambiguous || 0}</span>
            </div>
          </div>
        )}

        {transactions && transactions.test_ok === false && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-sm space-y-2" data-testid="fints-vr-test-error">
            <div className="flex items-center gap-2 font-semibold text-red-800">
              <XCircle className="w-4 h-4" /> VR-FinTS-Login fehlgeschlagen
            </div>
            <div className="text-xs text-red-700 font-mono whitespace-pre-wrap break-all">{transactions.error}</div>
            <div className="text-xs text-gray-700 bg-white border border-red-100 rounded p-2">
              <span className="font-semibold">Hinweis:</span> {transactions.hint}
            </div>
            <div className="text-[10px] text-gray-500">
              BLZ: {transactions.blz} · URL: {transactions.url} · User: {transactions.user_first_chars} (numeric: {String(transactions.user_is_numeric)}, {transactions.user_length} Zeichen) · PIN: {transactions.pin_length} Zeichen · Stage: {transactions.stage}
            </div>
            {transactions.log_trace && (
              <details className="text-xs">
                <summary className="cursor-pointer text-gray-600 hover:text-gray-900 font-medium">FinTS-Log-Trace anzeigen ({transactions.log_trace.length} Zeichen)</summary>
                <pre className="mt-2 text-[10px] bg-gray-900 text-gray-100 p-2 rounded max-h-96 overflow-auto whitespace-pre-wrap break-all">{transactions.log_trace}</pre>
              </details>
            )}
          </div>
        )}

        {transactions && transactions.test_ok === true && (
          <div className="bg-emerald-50 border border-emerald-200 rounded-lg p-3 text-sm space-y-2" data-testid="fints-vr-test-ok">
            <div className="flex items-center gap-2 font-semibold text-emerald-800">
              <Check className="w-4 h-4" /> VR-FinTS-Login erfolgreich
            </div>
            {transactions.primary_found ? (
              <div className="text-xs text-emerald-700">
                Hauptkonto gefunden:
                <div className="mt-1 bg-white border border-emerald-200 rounded px-2 py-1 font-mono text-gray-800">
                  {transactions.primary_iban} ({(transactions.accounts || [])[0]?.bic})
                </div>
              </div>
            ) : (
              <div className="text-xs text-amber-700">
                <strong>Warnung:</strong> Hauptkonto <span className="font-mono">{transactions.primary_iban}</span> nicht gefunden.
                <div className="mt-1">Verfügbare Konten:</div>
                <ul className="text-xs text-gray-700 ml-4 list-disc">
                  {(transactions.accounts || []).map((a, i) => (
                    <li key={i} className="font-mono">{a.iban} ({a.bic})</li>
                  ))}
                </ul>
                <div className="mt-1 text-gray-600">Bitte <code>FINTS_VB_IBAN</code> in <code>.env</code> anpassen.</div>
              </div>
            )}
            <Button size="sm" variant="outline" onClick={loadTransactions} className="text-xs mt-2" data-testid="fints-vr-load-tx-btn">
              Transaktionen der letzten 7 Tage laden
            </Button>
          </div>
        )}

        {transactions && transactions.transactions && (
          <div className="bg-gray-50 border border-gray-200 rounded-lg p-3">
            <p className="text-sm font-medium text-gray-900 mb-2">Letzte {transactions.count} Transaktionen (7 Tage):</p>
            <div className="max-h-48 overflow-y-auto space-y-1">
              {transactions.transactions.slice(0, 15).map((tx, i) => (
                <div key={i} className="text-xs flex justify-between border-b border-gray-100 py-1">
                  <div className="flex-1 min-w-0">
                    <span className="text-gray-500">{tx.date}</span>
                    <span className="ml-2 text-gray-700 truncate">{tx.applicant_name || tx.posting_text}</span>
                  </div>
                  <span className={`font-mono ml-2 ${tx.amount > 0 ? "text-emerald-600" : "text-red-600"}`}>
                    {tx.amount > 0 ? "+" : ""}{tx.amount?.toFixed(2)} EUR
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}


/* ───── HalloPetra KI-Telefonassistent ───── */
function HalloPetraSection() {
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(false);
  const [testing, setTesting] = useState(false);
  const [simulating, setSimulating] = useState(false);
  const [testResult, setTestResult] = useState(null);
  const [recent, setRecent] = useState([]);

  const withToken = (extra = {}) => ({ params: { token: localStorage.getItem("token"), ...extra } });

  const loadStatus = async () => {
    setLoading(true);
    try {
      const r = await api.get("/hallopetra/status", withToken());
      setStatus(r.data);
    } catch { setStatus(null); }
    finally { setLoading(false); }
  };

  const loadRecent = async () => {
    try {
      const r = await api.get("/hallopetra/recent-calls", withToken({ limit: 10 }));
      setRecent(r.data.tasks || []);
    } catch { /* still */ }
  };

  useEffect(() => { loadStatus(); loadRecent(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const testOutbound = async () => {
    setTesting(true); setTestResult(null);
    try {
      const r = await api.post("/hallopetra/test-outbound", null, withToken());
      setTestResult(r.data);
      if (r.data.ok) toast.success(`HalloPetra API erreichbar (${r.data.status_code})`);
      else toast.error(r.data.error || `Fehler ${r.data.status_code}`);
    } catch (e) { toast.error("Test fehlgeschlagen"); setTestResult({ ok: false, error: String(e) }); }
    finally { setTesting(false); }
  };

  const simulateCall = async (isEmergency) => {
    setSimulating(true);
    try {
      await api.post("/hallopetra/simulate-call", {
        is_emergency: isEmergency,
        caller_name: isEmergency ? "Peter Notfall" : "Anna Muster",
        caller_phone: "+493081234567",
        summary: isEmergency ? "Aggregat XBSG_125 komplett ausgefallen" : "Anfrage Stromversorgung Sommerfest",
      }, withToken());
      toast.success(isEmergency ? "🚨 Notfall-Task erstellt" : "Task erstellt");
      await loadRecent();
      await loadStatus();
    } catch { toast.error("Fehler beim Simulieren"); }
    finally { setSimulating(false); }
  };

  const webhookUrl = ((process.env.REACT_APP_BACKEND_URL || window.location.origin).replace(/\/$/, "")) + "/api/hallopetra/webhook";

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6" data-testid="hallopetra-section">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-pink-500 to-rose-600 flex items-center justify-center text-white font-bold">P</div>
          <div>
            <h2 className="text-lg font-semibold text-gray-900">HalloPetra – KI-Telefonassistent</h2>
            <p className="text-xs text-gray-500">Qualifizierte Anrufe landen automatisch als Aufgabe im Hub</p>
          </div>
        </div>
        <Button onClick={loadStatus} disabled={loading} size="sm" variant="outline" data-testid="petra-refresh">
          {loading ? "..." : "Aktualisieren"}
        </Button>
      </div>

      {/* Status-Zeile */}
      {status && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
          <div className={`rounded-lg border p-3 ${status.configured ? "bg-emerald-50 border-emerald-200" : "bg-amber-50 border-amber-200"}`}>
            <p className="text-[10px] uppercase font-semibold text-gray-500">Status</p>
            <p className={`text-sm font-bold ${status.configured ? "text-emerald-700" : "text-amber-700"}`} data-testid="petra-status">
              {status.configured ? "Konfiguriert" : "Nicht konfiguriert"}
            </p>
          </div>
          <div className="rounded-lg border border-gray-200 bg-gray-50 p-3">
            <p className="text-[10px] uppercase font-semibold text-gray-500">Webhook-Secret</p>
            <p className={`text-sm font-bold ${status.webhook_secret_set ? "text-emerald-700" : "text-red-600"}`}>
              {status.webhook_secret_set ? "gesetzt" : "fehlt (unsicher!)"}
            </p>
          </div>
          <div className="rounded-lg border border-gray-200 bg-gray-50 p-3">
            <p className="text-[10px] uppercase font-semibold text-gray-500">Anrufe (7 Tage)</p>
            <p className="text-sm font-bold text-gray-900">{status.last_7d?.tasks_created ?? 0} Tasks</p>
            <p className="text-[10px] text-gray-400">{status.last_7d?.events_received ?? 0} Events empfangen</p>
          </div>
          <div className="rounded-lg border border-gray-200 bg-gray-50 p-3">
            <p className="text-[10px] uppercase font-semibold text-gray-500">Notfälle (7 T.)</p>
            <p className={`text-sm font-bold ${(status.last_7d?.emergencies || 0) > 0 ? "text-red-600" : "text-gray-900"}`}>
              🚨 {status.last_7d?.emergencies ?? 0}
            </p>
          </div>
        </div>
      )}

      {/* Webhook-URL */}
      <div className="rounded-lg border border-indigo-200 bg-indigo-50 p-3 mb-4">
        <p className="text-xs font-semibold text-indigo-900 mb-1">📥 Webhook-URL für Petra-Dashboard</p>
        <div className="flex items-center gap-2">
          <code className="flex-1 text-xs bg-white border border-indigo-200 rounded px-2 py-1 font-mono truncate">{webhookUrl}</code>
          <Button size="sm" variant="outline" onClick={() => { navigator.clipboard.writeText(webhookUrl); toast.success("URL kopiert"); }} data-testid="copy-webhook-url">Kopieren</Button>
        </div>
        <p className="text-[10px] text-indigo-700 mt-1">Diese URL bei HalloPetra unter Einstellungen → Integrationen → Webhooks eintragen. Signatur-Header: <code>X-Petra-Signature</code> (HMAC-SHA256)</p>
      </div>

      {/* Konfiguration Hinweis */}
      {!status?.configured && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 mb-4">
          <p className="text-xs font-semibold text-amber-900 mb-1">⚙️ Konfiguration in .env erforderlich</p>
          <pre className="text-[11px] bg-white border border-amber-200 rounded p-2 font-mono overflow-x-auto">{`HALLOPETRA_CLIENT_ID=hp_ck_...
HALLOPETRA_CLIENT_SECRET=hp_sk_...        # oder API_TOKEN
HALLOPETRA_API_TOKEN=                     # (alternativ zu Secret)
HALLOPETRA_AUTH_HEADER=Authorization      # anpassbar falls Petra anderen Namen nutzt
HALLOPETRA_AUTH_SCHEME=Bearer             # oder leer lassen
HALLOPETRA_WEBHOOK_SECRET=whsec_...       # aus Petra-Dashboard
HALLOPETRA_BASE_URL=https://api.hallopetra.de/api/v1`}</pre>
          <p className="text-[10px] text-amber-700 mt-1">Nach Änderung Backend neu starten. Webhook-Secret ist erforderlich für sichere Signatur-Prüfung.</p>
        </div>
      )}

      {/* Aktionen */}
      <div className="flex flex-wrap items-center gap-2 mb-4">
        <Button onClick={testOutbound} disabled={testing || !status?.api_token_set} size="sm" variant="outline" data-testid="petra-test-outbound">
          {testing ? "Teste..." : "🔌 Verbindung testen"}
        </Button>
        <Button onClick={() => simulateCall(false)} disabled={simulating} size="sm" variant="outline" data-testid="petra-simulate-normal">
          📞 Anruf simulieren
        </Button>
        <Button onClick={() => simulateCall(true)} disabled={simulating} size="sm" className="bg-red-600 hover:bg-red-700" data-testid="petra-simulate-emergency">
          🚨 Notfall simulieren
        </Button>
        <Button onClick={loadRecent} size="sm" variant="ghost" data-testid="petra-refresh-recent">
          Letzte Anrufe neu laden
        </Button>
      </div>

      {/* Test-Ergebnis */}
      {testResult && (
        <div className={`rounded-lg border p-3 mb-4 ${testResult.ok ? "bg-emerald-50 border-emerald-200" : "bg-red-50 border-red-200"}`}>
          <p className={`text-xs font-semibold ${testResult.ok ? "text-emerald-900" : "text-red-900"}`}>
            {testResult.ok ? "✓ API erreichbar" : "✗ API-Fehler"} {testResult.status_code && `(HTTP ${testResult.status_code})`}
          </p>
          {testResult.body_preview && <pre className="text-[10px] mt-1 font-mono max-h-32 overflow-auto whitespace-pre-wrap">{testResult.body_preview}</pre>}
          {testResult.error && <p className="text-[11px] text-red-700 mt-1">{testResult.error}</p>}
        </div>
      )}

      {/* Letzte Anrufe */}
      <div>
        <p className="text-xs font-semibold text-gray-700 mb-2">Letzte {recent.length} Anrufe</p>
        {recent.length === 0 ? (
          <p className="text-xs text-gray-400 italic py-4 text-center">Noch keine Anrufe von Petra empfangen. Simuliere einen oben um zu testen.</p>
        ) : (
          <div className="border border-gray-200 rounded-lg divide-y divide-gray-100 max-h-80 overflow-y-auto">
            {recent.map(t => (
              <div key={t.id} className="p-3 hover:bg-gray-50 flex items-start gap-3">
                <span className={`text-lg flex-shrink-0 ${t.is_emergency ? "text-red-600" : "text-gray-400"}`}>
                  {t.is_emergency ? "🚨" : "📞"}
                </span>
                <div className="flex-1 min-w-0">
                  <p className={`text-sm font-medium ${t.is_emergency ? "text-red-800" : "text-gray-900"} truncate`}>{t.title}</p>
                  <p className="text-[11px] text-gray-500">
                    {t.caller_name || "Unbekannt"} · {t.caller_phone || "keine Tel."} · {new Date(t.created_at).toLocaleString("de-DE", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" })}
                    {t.customer_id && <span className="ml-1 text-emerald-600">· 🎯 Kunde erkannt</span>}
                  </p>
                  {t.description && <p className="text-[11px] text-gray-600 mt-0.5 line-clamp-2">{t.description}</p>}
                </div>
                <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full flex-shrink-0 ${
                  t.priority === "urgent" ? "bg-red-100 text-red-700" :
                  t.priority === "high" ? "bg-amber-100 text-amber-700" :
                  "bg-gray-100 text-gray-600"
                }`}>{t.priority}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}



/* ───── Backup-System Einstellungen ───── */
function BackupSettingsSection() {
  const [settings, setSettings] = useState({
    db_backup_enabled: true,
    db_backup_interval_hours: 12,
    files_backup_enabled: true,
    files_backup_interval_hours: 72,
    retention_days: 7,
  });
  const [backups, setBackups] = useState([]);
  const [loaded, setLoaded] = useState(false);
  const [saving, setSaving] = useState(false);
  const [triggeringDb, setTriggeringDb] = useState(false);
  const [triggeringFiles, setTriggeringFiles] = useState(false);
  const [deletingId, setDeletingId] = useState(null);

  const loadData = useCallback(async () => {
    try {
      const [settingsRes, backupsRes] = await Promise.all([
        api.get("/backup/settings"),
        api.get("/backup/list"),
      ]);
      setSettings(settingsRes.data);
      setBackups(backupsRes.data);
    } catch {
      /* ignore */
    } finally {
      setLoaded(true);
    }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  const handleSave = async () => {
    setSaving(true);
    try {
      await api.post("/backup/settings", settings);
      toast.success("Backup-Einstellungen gespeichert");
    } catch { toast.error("Fehler beim Speichern"); }
    finally { setSaving(false); }
  };

  const handleTriggerDb = async () => {
    setTriggeringDb(true);
    try {
      await api.post("/backup/trigger/db");
      toast.success("Datenbank-Backup erstellt");
      loadData();
    } catch (err) { toast.error(getErrorMsg(err, "DB-Backup fehlgeschlagen")); }
    finally { setTriggeringDb(false); }
  };

  const handleTriggerFiles = async () => {
    setTriggeringFiles(true);
    try {
      await api.post("/backup/trigger/files");
      toast.success("Dateien-Backup erstellt");
      loadData();
    } catch (err) { toast.error(getErrorMsg(err, "Dateien-Backup fehlgeschlagen")); }
    finally { setTriggeringFiles(false); }
  };

  const handleDelete = async (id) => {
    setDeletingId(id);
    try {
      await api.delete(`/backup/${id}`);
      toast.success("Backup gelöscht");
      setBackups(prev => prev.filter(b => b.id !== id));
    } catch { toast.error("Fehler beim Löschen"); }
    finally { setDeletingId(null); }
  };

  const formatSize = (bytes) => {
    if (!bytes) return "0 B";
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const formatDate = (iso) => {
    if (!iso) return "-";
    return new Date(iso).toLocaleString("de-DE", {
      day: "2-digit", month: "2-digit", year: "numeric",
      hour: "2-digit", minute: "2-digit",
    });
  };

  if (!loaded) return null;

  return (
    <div className="bg-white border border-gray-200 rounded-lg overflow-hidden" data-testid="backup-settings-section">
      <div className="flex items-center justify-between px-5 py-4 bg-gradient-to-r from-blue-700 to-indigo-600">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-white/20 flex items-center justify-center">
            <HardDrive className="w-5 h-5 text-white" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-white">Backup-System</h3>
            <p className="text-[10px] text-blue-100">Automatische Sicherung von Datenbank und Quellcode</p>
          </div>
        </div>
      </div>

      <div className="p-5 space-y-5">
        {/* ── Einstellungen ── */}
        <div className="space-y-4">
          <h4 className="text-sm font-semibold text-gray-900 flex items-center gap-2">
            <Settings2 className="w-4 h-4 text-blue-600" />
            Zeitplan-Einstellungen
          </h4>

          {/* DB Backup Row */}
          <div className="bg-gray-50 rounded-lg p-4 space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Database className="w-4 h-4 text-blue-600" />
                <span className="text-sm font-medium text-gray-800">Datenbank-Backup</span>
              </div>
              <Switch
                checked={settings.db_backup_enabled}
                onCheckedChange={v => setSettings(p => ({ ...p, db_backup_enabled: v }))}
                data-testid="db-backup-toggle"
              />
            </div>
            {settings.db_backup_enabled && (
              <div className="flex items-center gap-2 ml-6">
                <Clock className="w-3.5 h-3.5 text-gray-400" />
                <span className="text-xs text-gray-500">Intervall:</span>
                <input
                  type="number" min="1" max="720"
                  value={settings.db_backup_interval_hours}
                  onChange={e => setSettings(p => ({ ...p, db_backup_interval_hours: parseInt(e.target.value) || 12 }))}
                  className="w-16 px-2 py-1 text-xs border border-gray-200 rounded text-center font-mono"
                  data-testid="db-backup-interval-input"
                />
                <span className="text-xs text-gray-500">Stunden</span>
              </div>
            )}
          </div>

          {/* Files Backup Row */}
          <div className="bg-gray-50 rounded-lg p-4 space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <FolderArchive className="w-4 h-4 text-indigo-600" />
                <span className="text-sm font-medium text-gray-800">Quellcode-Backup</span>
              </div>
              <Switch
                checked={settings.files_backup_enabled}
                onCheckedChange={v => setSettings(p => ({ ...p, files_backup_enabled: v }))}
                data-testid="files-backup-toggle"
              />
            </div>
            {settings.files_backup_enabled && (
              <div className="flex items-center gap-2 ml-6">
                <Clock className="w-3.5 h-3.5 text-gray-400" />
                <span className="text-xs text-gray-500">Intervall:</span>
                <input
                  type="number" min="1" max="720"
                  value={settings.files_backup_interval_hours}
                  onChange={e => setSettings(p => ({ ...p, files_backup_interval_hours: parseInt(e.target.value) || 72 }))}
                  className="w-16 px-2 py-1 text-xs border border-gray-200 rounded text-center font-mono"
                  data-testid="files-backup-interval-input"
                />
                <span className="text-xs text-gray-500">Stunden</span>
              </div>
            )}
          </div>

          {/* Retention */}
          <div className="bg-gray-50 rounded-lg p-4">
            <div className="flex items-center gap-2">
              <Trash className="w-4 h-4 text-red-500" />
              <span className="text-sm font-medium text-gray-800">Aufbewahrung:</span>
              <input
                type="number" min="1" max="365"
                value={settings.retention_days}
                onChange={e => setSettings(p => ({ ...p, retention_days: parseInt(e.target.value) || 7 }))}
                className="w-16 px-2 py-1 text-xs border border-gray-200 rounded text-center font-mono"
                data-testid="retention-days-input"
              />
              <span className="text-xs text-gray-500">Tage (danach automatisch löschen)</span>
            </div>
          </div>

          {/* Save Button */}
          <Button size="sm" onClick={handleSave} disabled={saving} className="bg-blue-600 hover:bg-blue-700 text-white" data-testid="save-backup-settings-btn">
            {saving ? <Loader2 className="w-4 h-4 mr-1.5 animate-spin" /> : <Save className="w-4 h-4 mr-1.5" />}
            Einstellungen speichern
          </Button>
        </div>

        {/* ── Manuelles Backup ── */}
        <div className="border-t border-gray-100 pt-5 space-y-3">
          <h4 className="text-sm font-semibold text-gray-900 flex items-center gap-2">
            <Play className="w-4 h-4 text-blue-600" />
            Manuelles Backup
          </h4>
          <div className="flex flex-wrap gap-3">
            <Button
              size="sm" variant="outline"
              onClick={handleTriggerDb}
              disabled={triggeringDb}
              className="border-blue-200 text-blue-700 hover:bg-blue-50"
              data-testid="trigger-db-backup-btn"
            >
              {triggeringDb ? <Loader2 className="w-4 h-4 mr-1.5 animate-spin" /> : <Database className="w-4 h-4 mr-1.5" />}
              Datenbank jetzt sichern
            </Button>
            <Button
              size="sm" variant="outline"
              onClick={handleTriggerFiles}
              disabled={triggeringFiles}
              className="border-indigo-200 text-indigo-700 hover:bg-indigo-50"
              data-testid="trigger-files-backup-btn"
            >
              {triggeringFiles ? <Loader2 className="w-4 h-4 mr-1.5 animate-spin" /> : <FolderArchive className="w-4 h-4 mr-1.5" />}
              Quellcode jetzt sichern
            </Button>
          </div>
        </div>

        {/* ── Backup-Liste ── */}
        <div className="border-t border-gray-100 pt-5 space-y-3">
          <div className="flex items-center justify-between">
            <h4 className="text-sm font-semibold text-gray-900 flex items-center gap-2">
              <FolderArchive className="w-4 h-4 text-blue-600" />
              Vorhandene Backups
            </h4>
            <Button variant="ghost" size="sm" onClick={loadData} className="text-gray-400 hover:text-blue-600 h-7" data-testid="refresh-backups-btn">
              <RefreshCw className="w-3.5 h-3.5" />
            </Button>
          </div>

          {backups.length === 0 ? (
            <p className="text-xs text-gray-400 py-4 text-center">Noch keine Backups vorhanden</p>
          ) : (
            <div className="border border-gray-200 rounded-lg overflow-hidden">
              <table className="w-full text-xs" data-testid="backups-table">
                <thead>
                  <tr className="bg-gray-50 border-b border-gray-200">
                    <th className="text-left px-3 py-2 text-gray-600 font-medium">Typ</th>
                    <th className="text-left px-3 py-2 text-gray-600 font-medium">Datum</th>
                    <th className="text-left px-3 py-2 text-gray-600 font-medium">Größe</th>
                    <th className="text-left px-3 py-2 text-gray-600 font-medium">Auslöser</th>
                    <th className="text-right px-3 py-2 text-gray-600 font-medium">Aktionen</th>
                  </tr>
                </thead>
                <tbody>
                  {backups.map((b, i) => (
                    <tr key={b.id} className={i % 2 === 0 ? "bg-white" : "bg-gray-50"} data-testid={`backup-row-${b.id}`}>
                      <td className="px-3 py-2.5">
                        <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium ${
                          b.type === "database"
                            ? "bg-blue-50 text-blue-700"
                            : "bg-indigo-50 text-indigo-700"
                        }`}>
                          {b.type === "database" ? <Database className="w-3 h-3" /> : <FolderArchive className="w-3 h-3" />}
                          {b.type === "database" ? "Datenbank" : "Quellcode"}
                        </span>
                      </td>
                      <td className="px-3 py-2.5 text-gray-700">{formatDate(b.created_at)}</td>
                      <td className="px-3 py-2.5 text-gray-500 font-mono">{formatSize(b.file_size)}</td>
                      <td className="px-3 py-2.5">
                        <span className={`text-[10px] font-medium ${b.trigger === "auto" ? "text-green-600" : "text-gray-500"}`}>
                          {b.trigger === "auto" ? "Automatisch" : "Manuell"}
                        </span>
                      </td>
                      <td className="px-3 py-2.5 text-right">
                        <div className="flex items-center justify-end gap-1">
                          {b.file_exists && (
                            <a
                              href={`${BACKEND_URL}/api/backup/${b.id}/download`}
                              download
                              className="p-1 text-gray-400 hover:text-blue-600 transition-colors"
                              data-testid={`download-backup-${b.id}`}
                            >
                              <Download className="w-3.5 h-3.5" />
                            </a>
                          )}
                          <button
                            onClick={() => handleDelete(b.id)}
                            disabled={deletingId === b.id}
                            className="p-1 text-gray-400 hover:text-red-500 transition-colors"
                            data-testid={`delete-backup-${b.id}`}
                          >
                            {deletingId === b.id ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Trash2 className="w-3.5 h-3.5" />}
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Info */}
        <div className="bg-blue-50 rounded-lg p-3 border border-blue-100">
          <p className="text-[10px] text-blue-700 leading-relaxed">
            <strong>Hinweis:</strong> Datenbank-Backups nutzen <code className="bg-blue-100 px-1 rounded">mongodump</code> mit gzip-Komprimierung.
            Quellcode-Backups enthalten den gesamten Anwendungscode ohne .env-Dateien und node_modules.
            Der Scheduler prüft alle 15 Minuten, ob ein Backup fällig ist.
          </p>
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
            <Button variant="ghost" size="sm" onClick={() => navigate("/hub")} className="text-gray-600 hover:text-fuchsia-600" data-testid="back-to-admin-btn">
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
            <Button variant="outline" size="sm" onClick={() => navigate("/admin/gps-diagnose")} className="text-gray-600 hover:text-fuchsia-600" data-testid="gps-diagnose-link">
              <MapPin className="w-4 h-4 mr-1" /> GPS-Diagnose
            </Button>
            <Button variant="outline" size="sm" onClick={() => document.getElementById('hilfsmittel-section')?.scrollIntoView({ behavior: 'smooth' })} className="text-gray-600 hover:text-fuchsia-600" data-testid="hilfsmittel-link">
              <Wrench className="w-4 h-4 mr-1" /> Hilfsmittel
            </Button>
            <Logo size="small" />
          </div>
        </div>
      </header>

      <main className="flex-1 p-4 md:p-6">
        <div className="max-w-7xl mx-auto space-y-8">
          {/* System Status Dashboard */}
          <SystemStatusDashboard />

          {/* SMTP / E-Mail */}
          <SmtpConfig />

          {/* Backup-System */}
          <BackupSettingsSection />

          {/* FinTS Banking */}
          <FinTSBankingSection />

          {/* FinTS Banking Volksbank (VR) */}
          <FinTSVRBankingSection />

          {/* HalloPetra KI-Telefonassistent */}
          <HalloPetraSection />

          {/* Tankbeleg Pi */}
          <TankbelegPiSection />

          {/* Einsatzzentrale Pi-Kioske */}
          <EinsatzzentralePiSection />

          {/* Einsatzzentrale Browser-Tokens (temporaer) */}
          <EinsatzzentraleBrowserTokensSection />
          {/* Hilfsmittel */}
          <div id="hilfsmittel-section">
            <HilfsmittelSection />
          </div>

          {/* Software Downloads */}
          <SoftwareDownloadsSection />

          {/* Kirmeskiste OTA-Updates */}
          <OtaUpdateSection />

          {/* Mosquitto MQTT Broker */}
          <MosquittoSetupSection />

          {/* Ollama / KI-Dokumentanalyse */}
          <OllamaConfigSection />

          {/* Dokumentenablage Storage-Health */}
          <StorageHealthSection />

          {/* Schnittstellen */}
          <div>

          </div>
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
