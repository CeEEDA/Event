import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { Logo } from "../components/Logo";
import api, { getErrorMsg } from "../lib/api";
import { toast } from "sonner";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Switch } from "../components/ui/switch";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../components/ui/select";
import {
  ArrowLeft,
  Wifi,
  WifiOff,
  Settings,
  Plus,
  Trash2,
  RefreshCw,
  CheckCircle,
  XCircle,
  AlertTriangle,
  Radio,
  Link2,
  Terminal,
  ChevronDown,
  ChevronRight,
  Copy,
  Key,
  Shield,
  Eye,
  EyeOff,
} from "lucide-react";

const STATUS_CONFIG = {
  connected: { label: "Verbunden", color: "text-emerald-600", bg: "bg-emerald-50 border-emerald-200", Icon: CheckCircle },
  connecting: { label: "Verbinde...", color: "text-amber-600", bg: "bg-amber-50 border-amber-200", Icon: RefreshCw },
  disconnected: { label: "Getrennt", color: "text-gray-500", bg: "bg-gray-50 border-gray-200", Icon: WifiOff },
  error: { label: "Fehler", color: "text-red-600", bg: "bg-red-50 border-red-200", Icon: XCircle },
};

export default function MqttConfigPage() {
  const { user } = useAuth();
  const navigate = useNavigate();

  const [config, setConfig] = useState({
    enabled: false,
    broker_url: "",
    broker_port: 8883,
    username: "",
    password: "",
    use_tls: true,
    subscribe_topics: ["dse/#"],
  });
  const [status, setStatus] = useState({ connected: false, connection_status: "disconnected" });
  const [mappings, setMappings] = useState([]);
  const [generators, setGenerators] = useState([]);
  const [rawMessages, setRawMessages] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [showRaw, setShowRaw] = useState(false);
  const [showSetup, setShowSetup] = useState(false);
  const [newMapping, setNewMapping] = useState({ gateway_name: "", topic_prefix: "", generator_id: "", notes: "" });
  const [credentials, setCredentials] = useState([]);
  const [credentialModal, setCredentialModal] = useState(null);
  const [generatingCred, setGeneratingCred] = useState(null);
  const [showPassword, setShowPassword] = useState(false);

  const loadAll = useCallback(async () => {
    setLoading(true);
    try {
      const [configRes, statusRes, mappingsRes, gensRes, credsRes] = await Promise.all([
        api.get("/mqtt/config"),
        api.get("/mqtt/status"),
        api.get("/mqtt/mappings"),
        api.get("/generators").catch(() => ({ data: [] })),
        api.get("/mqtt/credentials").catch(() => ({ data: [] })),
      ]);
      setConfig(configRes.data);
      setStatus(statusRes.data);
      setMappings(mappingsRes.data);
      setGenerators(gensRes.data);
      setCredentials(credsRes.data);
    } catch {
      toast.error("Fehler beim Laden der MQTT-Konfiguration");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadAll(); }, [loadAll]);

  // Poll status every 5 seconds when connected or connecting
  useEffect(() => {
    if (!config.enabled) return;
    const interval = setInterval(async () => {
      try {
        const res = await api.get("/mqtt/status");
        setStatus(res.data);
      } catch {}
    }, 5000);
    return () => clearInterval(interval);
  }, [config.enabled]);

  const saveConfig = async () => {
    setSaving(true);
    try {
      const res = await api.put("/mqtt/config", config);
      setConfig(res.data);
      toast.success("MQTT-Konfiguration gespeichert");
      // Refresh status after save
      setTimeout(async () => {
        const s = await api.get("/mqtt/status");
        setStatus(s.data);
      }, 2000);
    } catch (err) {
      toast.error(getErrorMsg(err, "Fehler beim Speichern"));
    } finally {
      setSaving(false);
    }
  };

  const testConnection = async () => {
    setTesting(true);
    try {
      const res = await api.post("/mqtt/test-connection");
      if (res.data.success) {
        toast.success(res.data.message);
      } else {
        toast.error(res.data.message);
      }
    } catch (err) {
      toast.error("Verbindungstest fehlgeschlagen");
    } finally {
      setTesting(false);
    }
  };

  const loadRawMessages = async () => {
    try {
      const res = await api.get("/mqtt/raw-messages?limit=50");
      setRawMessages(res.data);
    } catch {}
  };

  const addMapping = async () => {
    if (!newMapping.gateway_name || !newMapping.topic_prefix || !newMapping.generator_id) {
      toast.error("Bitte alle Pflichtfelder ausfuellen");
      return;
    }
    try {
      await api.post("/mqtt/mappings", newMapping);
      toast.success("Gateway-Zuordnung erstellt");
      setNewMapping({ gateway_name: "", topic_prefix: "", generator_id: "", notes: "" });
      const res = await api.get("/mqtt/mappings");
      setMappings(res.data);
    } catch (err) {
      toast.error(getErrorMsg(err, "Fehler"));
    }
  };

  const deleteMapping = async (id) => {
    try {
      await api.delete(`/mqtt/mappings/${id}`);
      setMappings(mappings.filter(m => m.id !== id));
      toast.success("Zuordnung geloescht");
    } catch {}
  };

  const generateCredentials = async (generatorId) => {
    setGeneratingCred(generatorId);
    try {
      const res = await api.post(`/mqtt/credentials/${generatorId}/generate`);
      setCredentialModal(res.data);
      setShowPassword(true);
      const credsRes = await api.get("/mqtt/credentials");
      setCredentials(credsRes.data);
      toast.success("MQTT-Zugangsdaten generiert");
    } catch (err) {
      toast.error(getErrorMsg(err, "Fehler beim Generieren"));
    } finally {
      setGeneratingCred(null);
    }
  };

  const revokeCredentials = async (generatorId) => {
    if (!window.confirm("MQTT-Zugangsdaten wirklich widerrufen? Das Gateway verliert den Zugang.")) return;
    try {
      await api.delete(`/mqtt/credentials/${generatorId}`);
      setCredentials(credentials.map(c => c.generator_id === generatorId ? { ...c, has_credentials: false, mqtt_username: "", created_at: "" } : c));
      toast.success("Zugangsdaten widerrufen");
    } catch (err) {
      toast.error(getErrorMsg(err, "Fehler"));
    }
  };

  const statusCfg = STATUS_CONFIG[status.connection_status] || STATUS_CONFIG.disconnected;
  const StatusIcon = statusCfg.Icon;

  if (user?.role !== "admin") {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <p className="text-gray-500">Keine Berechtigung</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 sticky top-0 z-30">
        <div className="max-w-6xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <button onClick={() => navigate("/admin/settings")} className="text-gray-400 hover:text-gray-700 flex items-center gap-2 text-sm" data-testid="mqtt-back-btn">
              <ArrowLeft className="w-4 h-4" /> Zurück
            </button>
            <h1 className="text-lg font-semibold text-gray-900">MQTT-Integration</h1>
          </div>
          <div className="flex items-center gap-3">
            <div className={`flex items-center gap-2 px-3 py-1.5 rounded-full border text-sm ${statusCfg.bg}`}>
              <StatusIcon className={`w-4 h-4 ${statusCfg.color} ${status.connection_status === 'connecting' ? 'animate-spin' : ''}`} />
              <span className={statusCfg.color}>{statusCfg.label}</span>
            </div>
            <Logo size="small" />
          </div>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-4 py-6 space-y-6">
        {/* Connection Config */}
        <section className="bg-white rounded-xl border border-gray-200 p-6" data-testid="mqtt-config-section">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-fuchsia-100 flex items-center justify-center">
                <Settings className="w-5 h-5 text-fuchsia-600" />
              </div>
              <div>
                <h2 className="font-semibold text-gray-900">Broker-Konfiguration</h2>
                <p className="text-xs text-gray-500">MQTT-Broker Zugangsdaten</p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Label htmlFor="mqtt-enabled" className="text-sm text-gray-600">Aktiviert</Label>
              <Switch
                id="mqtt-enabled"
                checked={config.enabled}
                onCheckedChange={(v) => setConfig({ ...config, enabled: v })}
                data-testid="mqtt-enabled-switch"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <Label className="text-xs text-gray-600">Broker URL</Label>
              <Input
                value={config.broker_url}
                onChange={(e) => setConfig({ ...config, broker_url: e.target.value })}
                placeholder="z.B. broker.hivemq.com"
                data-testid="mqtt-broker-url"
              />
            </div>
            <div>
              <Label className="text-xs text-gray-600">Port</Label>
              <Input
                type="number"
                value={config.broker_port}
                onChange={(e) => setConfig({ ...config, broker_port: parseInt(e.target.value) || 1883 })}
                data-testid="mqtt-broker-port"
              />
            </div>
            <div>
              <Label className="text-xs text-gray-600">Benutzername</Label>
              <Input
                value={config.username}
                onChange={(e) => setConfig({ ...config, username: e.target.value })}
                placeholder="MQTT Benutzername"
                data-testid="mqtt-username"
              />
            </div>
            <div>
              <Label className="text-xs text-gray-600">Passwort</Label>
              <Input
                type="password"
                value={config.password}
                onChange={(e) => setConfig({ ...config, password: e.target.value })}
                placeholder="MQTT Passwort"
                data-testid="mqtt-password"
              />
            </div>
            <div>
              <Label className="text-xs text-gray-600">Topics (kommagetrennt)</Label>
              <Input
                value={(config.subscribe_topics || []).join(", ")}
                onChange={(e) => setConfig({ ...config, subscribe_topics: e.target.value.split(",").map(t => t.trim()).filter(Boolean) })}
                placeholder="dse/#"
                data-testid="mqtt-topics"
              />
            </div>
            <div className="flex items-end gap-2">
              <div className="flex items-center gap-2">
                <Switch
                  id="mqtt-tls"
                  checked={config.use_tls}
                  onCheckedChange={(v) => setConfig({ ...config, use_tls: v })}
                />
                <Label htmlFor="mqtt-tls" className="text-sm text-gray-600">TLS/SSL verwenden</Label>
              </div>
            </div>
          </div>

          <div className="flex gap-2 mt-4">
            <Button onClick={saveConfig} disabled={saving} data-testid="mqtt-save-btn">
              {saving ? <RefreshCw className="w-4 h-4 mr-2 animate-spin" /> : <CheckCircle className="w-4 h-4 mr-2" />}
              Speichern & Verbinden
            </Button>
            <Button variant="outline" onClick={testConnection} disabled={testing} data-testid="mqtt-test-btn">
              {testing ? <RefreshCw className="w-4 h-4 mr-2 animate-spin" /> : <Wifi className="w-4 h-4 mr-2" />}
              Verbindung testen
            </Button>
          </div>
        </section>

        {/* Gateway Mappings */}
        <section className="bg-white rounded-xl border border-gray-200 p-6" data-testid="mqtt-mappings-section">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-10 h-10 rounded-lg bg-sky-100 flex items-center justify-center">
              <Link2 className="w-5 h-5 text-sky-600" />
            </div>
            <div>
              <h2 className="font-semibold text-gray-900">Gateway-Zuordnungen</h2>
              <p className="text-xs text-gray-500">MQTT-Topics den Generatoren zuordnen</p>
            </div>
          </div>

          {/* Existing mappings */}
          {mappings.length > 0 && (
            <div className="space-y-2 mb-4">
              {mappings.map(m => (
                <div key={m.id} className="flex items-center justify-between bg-gray-50 rounded-lg p-3 border border-gray-100">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <Radio className="w-4 h-4 text-sky-500 shrink-0" />
                      <span className="font-medium text-sm text-gray-900 truncate">{m.gateway_name}</span>
                    </div>
                    <div className="ml-6 text-xs text-gray-500 mt-0.5">
                      Topic: <code className="bg-gray-200 px-1 rounded">{m.topic_prefix}</code>
                      {" → "}
                      <span className="text-gray-700">{m.generator_name || m.generator_serial || m.generator_id}</span>
                    </div>
                  </div>
                  <Button variant="ghost" size="sm" onClick={() => deleteMapping(m.id)} data-testid={`delete-mapping-${m.id}`}>
                    <Trash2 className="w-4 h-4 text-red-400" />
                  </Button>
                </div>
              ))}
            </div>
          )}

          {/* Add new mapping */}
          <div className="border border-dashed border-gray-300 rounded-lg p-4 space-y-3">
            <p className="text-sm font-medium text-gray-700 flex items-center gap-2">
              <Plus className="w-4 h-4" /> Neue Zuordnung
            </p>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
              <div>
                <Label className="text-xs text-gray-600">Gateway Name</Label>
                <Input
                  value={newMapping.gateway_name}
                  onChange={(e) => setNewMapping({ ...newMapping, gateway_name: e.target.value })}
                  placeholder="z.B. Gateway Baustelle HBF"
                  data-testid="mapping-gateway-name"
                />
              </div>
              <div>
                <Label className="text-xs text-gray-600">Topic Prefix</Label>
                <Input
                  value={newMapping.topic_prefix}
                  onChange={(e) => setNewMapping({ ...newMapping, topic_prefix: e.target.value })}
                  placeholder="z.B. dse/gateway1"
                  data-testid="mapping-topic-prefix"
                />
              </div>
              <div>
                <Label className="text-xs text-gray-600">Generator</Label>
                <Select
                  value={newMapping.generator_id}
                  onValueChange={(v) => setNewMapping({ ...newMapping, generator_id: v })}
                >
                  <SelectTrigger data-testid="mapping-generator-select">
                    <SelectValue placeholder="Generator wählen..." />
                  </SelectTrigger>
                  <SelectContent>
                    {generators.map(g => (
                      <SelectItem key={g.id} value={g.id}>
                        {g.name} ({g.serial_number})
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="flex items-end">
                <Button onClick={addMapping} className="w-full" data-testid="add-mapping-btn">
                  <Plus className="w-4 h-4 mr-1" /> Hinzufügen
                </Button>
              </div>
            </div>
          </div>
        </section>

        {/* Gateway MQTT Credentials */}
        <section className="bg-white rounded-xl border border-gray-200 p-6" data-testid="mqtt-credentials-section">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-10 h-10 rounded-lg bg-violet-100 flex items-center justify-center">
              <Shield className="w-5 h-5 text-violet-600" />
            </div>
            <div>
              <h2 className="font-semibold text-gray-900">Gateway-Zugangsdaten</h2>
              <p className="text-xs text-gray-500">Eigener MQTT-User pro DSE-Gateway (Mosquitto wird automatisch aktualisiert)</p>
            </div>
          </div>

          {credentials.length === 0 ? (
            <p className="text-sm text-gray-400 italic">Keine Generatoren vorhanden. Erstellen Sie zuerst einen Generator.</p>
          ) : (
            <div className="space-y-2">
              {credentials.map(c => (
                <div key={c.generator_id} className="flex items-center justify-between bg-gray-50 rounded-lg p-3 border border-gray-100" data-testid={`credential-row-${c.generator_id}`}>
                  <div className="flex items-center gap-3 flex-1 min-w-0">
                    <Key className={`w-4 h-4 shrink-0 ${c.has_credentials ? "text-emerald-500" : "text-gray-300"}`} />
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-gray-900 truncate">{c.name || c.serial_number}</p>
                      <p className="text-xs text-gray-500">
                        {c.has_credentials ? (
                          <>User: <code className="bg-gray-200 px-1 rounded">{c.mqtt_username}</code> · seit {new Date(c.created_at).toLocaleDateString("de-DE")}</>
                        ) : (
                          "Keine Zugangsdaten"
                        )}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2 shrink-0 ml-3">
                    <Button
                      size="sm"
                      variant={c.has_credentials ? "outline" : "default"}
                      onClick={() => generateCredentials(c.generator_id)}
                      disabled={generatingCred === c.generator_id}
                      data-testid={`generate-cred-${c.generator_id}`}
                    >
                      {generatingCred === c.generator_id ? (
                        <RefreshCw className="w-3 h-3 mr-1 animate-spin" />
                      ) : (
                        <Key className="w-3 h-3 mr-1" />
                      )}
                      {c.has_credentials ? "Neu generieren" : "Generieren"}
                    </Button>
                    {c.has_credentials && (
                      <Button size="sm" variant="ghost" onClick={() => revokeCredentials(c.generator_id)} data-testid={`revoke-cred-${c.generator_id}`}>
                        <Trash2 className="w-3 h-3 text-red-400" />
                      </Button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>

        {/* Credential Modal */}
        {credentialModal && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={() => setCredentialModal(null)}>
            <div className="bg-white rounded-xl shadow-2xl max-w-lg w-full mx-4 p-6" onClick={e => e.stopPropagation()} data-testid="credential-modal">
              <div className="flex items-center gap-3 mb-4">
                <div className="w-10 h-10 rounded-lg bg-emerald-100 flex items-center justify-center">
                  <Shield className="w-5 h-5 text-emerald-600" />
                </div>
                <div>
                  <h3 className="font-semibold text-gray-900">MQTT-Zugangsdaten generiert</h3>
                  <p className="text-xs text-gray-500">{credentialModal.generator_name} ({credentialModal.serial_number})</p>
                </div>
              </div>

              <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 mb-4">
                <p className="text-sm text-amber-800 font-medium">Das Passwort wird nur jetzt angezeigt! Bitte kopieren Sie es sofort.</p>
              </div>

              <div className="space-y-3">
                <div>
                  <label className="text-xs text-gray-500 uppercase tracking-wider">Benutzername</label>
                  <div className="flex items-center gap-2 mt-1">
                    <code className="flex-1 bg-gray-100 rounded px-3 py-2 text-sm font-mono" data-testid="cred-username">{credentialModal.username}</code>
                    <button onClick={() => { navigator.clipboard.writeText(credentialModal.username); toast.success("Kopiert"); }} className="p-2 hover:bg-gray-100 rounded" data-testid="copy-username">
                      <Copy className="w-4 h-4 text-gray-500" />
                    </button>
                  </div>
                </div>
                <div>
                  <label className="text-xs text-gray-500 uppercase tracking-wider">Passwort</label>
                  <div className="flex items-center gap-2 mt-1">
                    <code className="flex-1 bg-gray-100 rounded px-3 py-2 text-sm font-mono" data-testid="cred-password">
                      {showPassword ? credentialModal.password : "••••••••••••••••"}
                    </code>
                    <button onClick={() => setShowPassword(!showPassword)} className="p-2 hover:bg-gray-100 rounded">
                      {showPassword ? <EyeOff className="w-4 h-4 text-gray-500" /> : <Eye className="w-4 h-4 text-gray-500" />}
                    </button>
                    <button onClick={() => { navigator.clipboard.writeText(credentialModal.password); toast.success("Kopiert"); }} className="p-2 hover:bg-gray-100 rounded" data-testid="copy-password">
                      <Copy className="w-4 h-4 text-gray-500" />
                    </button>
                  </div>
                </div>
              </div>

              <div className="bg-gray-900 text-gray-100 rounded-lg p-4 text-sm font-mono space-y-1 mt-4">
                <p className="text-gray-400 text-xs mb-2">DSE Gateway MQTT-Einstellungen:</p>
                <p><span className="text-gray-500">Broker URL:</span> <span className="text-emerald-400">eventenergie.app</span></p>
                <p><span className="text-gray-500">Port:</span> <span className="text-emerald-400">1883</span></p>
                <p><span className="text-gray-500">Username:</span> <span className="text-emerald-400">{credentialModal.username}</span></p>
                <p><span className="text-gray-500">Password:</span> <span className="text-emerald-400">{showPassword ? credentialModal.password : "••••••••"}</span></p>
                <p><span className="text-gray-500">Use Login Credentials:</span> <span className="text-emerald-400">Aktiviert</span></p>
              </div>

              {credentialModal.passwd_file_updated && (
                <p className="text-xs text-emerald-600 mt-3 flex items-center gap-1">
                  <CheckCircle className="w-3 h-3" /> Mosquitto passwd-Datei aktualisiert
                </p>
              )}
              {credentialModal.passwd_file_updated === false && (
                <p className="text-xs text-amber-600 mt-3 flex items-center gap-1">
                  <AlertTriangle className="w-3 h-3" /> MOSQUITTO_PASSWD_FILE nicht konfiguriert – bitte manuell aktualisieren
                </p>
              )}

              <div className="mt-5 flex justify-end">
                <Button onClick={() => setCredentialModal(null)} data-testid="close-credential-modal">Verstanden</Button>
              </div>
            </div>
          </div>
        )}

        {/* Setup Instructions */}
        <section className="bg-white rounded-xl border border-gray-200 overflow-hidden" data-testid="mqtt-setup-section">
          <button
            onClick={() => setShowSetup(!showSetup)}
            className="w-full flex items-center justify-between p-6 text-left hover:bg-gray-50 transition-colors"
          >
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-amber-100 flex items-center justify-center">
                <AlertTriangle className="w-5 h-5 text-amber-600" />
              </div>
              <div>
                <h2 className="font-semibold text-gray-900">Gateway Einrichtung</h2>
                <p className="text-xs text-gray-500">Anleitung: Was Sie am DSE-Gateway ändern müssen</p>
              </div>
            </div>
            {showSetup ? <ChevronDown className="w-5 h-5 text-gray-400" /> : <ChevronRight className="w-5 h-5 text-gray-400" />}
          </button>
          {showSetup && (
            <div className="px-6 pb-6 space-y-4 border-t border-gray-100 pt-4">
              <div className="bg-amber-50 rounded-lg p-4 text-sm text-amber-900 space-y-3">
                <p className="font-semibold">Eigener Mosquitto Broker auf eventenergie.app</p>
                <p>Jedes Gateway bekommt eigene Zugangsdaten. Generieren Sie diese oben im Bereich "Gateway-Zugangsdaten" und tragen Sie sie im DSE-Gateway ein.</p>
                <p>Die Mosquitto passwd-Datei wird automatisch aktualisiert, wenn <code className="bg-amber-100 px-1 rounded">MOSQUITTO_PASSWD_FILE</code> in der Backend .env gesetzt ist.</p>
              </div>

              <div className="space-y-3">
                <h3 className="font-semibold text-gray-900">Schritt 1: Broker hier konfigurieren</h3>
                <p className="text-sm text-gray-600">Tragen Sie die Broker-Zugangsdaten oben im Formular ein und klicken Sie "Speichern & Verbinden".</p>

                <h3 className="font-semibold text-gray-900 mt-4">Schritt 2: DSE-Gateway konfigurieren</h3>
                <p className="text-sm text-gray-600">Öffnen Sie die Gateway-Weboberfläche (z.B. http://192.168.1.100) und gehen Sie zum <strong>MQTT</strong>-Tab:</p>
                <div className="bg-gray-900 text-gray-100 rounded-lg p-4 text-sm font-mono space-y-1">
                  <p><span className="text-gray-500">Broker URL:</span> <span className="text-emerald-400">{config.broker_url || "[Ihre Broker-URL]"}</span></p>
                  <p><span className="text-gray-500">Port:</span> <span className="text-emerald-400">{config.broker_port || "[Port]"}</span></p>
                  <p><span className="text-gray-500">Connection Method:</span> <span className="text-emerald-400">Auto</span> (oder GSM/Ethernet)</p>
                  <p><span className="text-gray-500">Username:</span> <span className="text-emerald-400">{config.username || "[Benutzername]"}</span></p>
                  <p><span className="text-gray-500">Password:</span> <span className="text-emerald-400">[Ihr MQTT-Passwort]</span></p>
                  <p><span className="text-gray-500">Use Login Credentials:</span> <span className="text-emerald-400">Aktiviert</span></p>
                  <p><span className="text-gray-500">Use Secure MQTT:</span> <span className="text-emerald-400">{config.use_tls ? "Aktiviert" : "Deaktiviert"}</span></p>
                </div>

                <h3 className="font-semibold text-gray-900 mt-4">Schritt 3: Gateway-Zuordnung erstellen</h3>
                <p className="text-sm text-gray-600">
                  Sobald das Gateway Daten sendet, erscheinen diese in den "Roh-Nachrichten" unten.
                  Notieren Sie den Topic-Prefix und ordnen Sie ihn oben einem Generator zu.
                </p>

                <h3 className="font-semibold text-gray-900 mt-4">Schritt 4: WebNet (optional)</h3>
                <p className="text-sm text-gray-600">
                  Das Gateway kann <strong>gleichzeitig</strong> WebNet und MQTT nutzen. Sie können die WebNet-Verbindung zu dsewebnet.com beibehalten,
                  während die MQTT-Daten parallel an unser Portal gesendet werden.
                </p>
              </div>
            </div>
          )}
        </section>

        {/* Raw Messages (Debug) */}
        <section className="bg-white rounded-xl border border-gray-200 overflow-hidden" data-testid="mqtt-raw-section">
          <button
            onClick={() => { setShowRaw(!showRaw); if (!showRaw) loadRawMessages(); }}
            className="w-full flex items-center justify-between p-6 text-left hover:bg-gray-50 transition-colors"
          >
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-gray-100 flex items-center justify-center">
                <Terminal className="w-5 h-5 text-gray-600" />
              </div>
              <div>
                <h2 className="font-semibold text-gray-900">Roh-Nachrichten</h2>
                <p className="text-xs text-gray-500">Eingehende MQTT-Nachrichten (Debug)</p>
              </div>
            </div>
            {showRaw ? <ChevronDown className="w-5 h-5 text-gray-400" /> : <ChevronRight className="w-5 h-5 text-gray-400" />}
          </button>
          {showRaw && (
            <div className="px-6 pb-6 border-t border-gray-100 pt-4">
              <div className="flex gap-2 mb-3">
                <Button variant="outline" size="sm" onClick={loadRawMessages}>
                  <RefreshCw className="w-3 h-3 mr-1" /> Aktualisieren
                </Button>
                <Button variant="outline" size="sm" onClick={async () => { await api.delete("/mqtt/raw-messages"); setRawMessages([]); toast.success("Gelöscht"); }}>
                  <Trash2 className="w-3 h-3 mr-1" /> Leeren
                </Button>
              </div>
              {rawMessages.length === 0 ? (
                <p className="text-sm text-gray-500 italic">Keine Nachrichten vorhanden. Sobald das Gateway verbunden ist, erscheinen hier die empfangenen Daten.</p>
              ) : (
                <div className="space-y-1 max-h-96 overflow-y-auto">
                  {rawMessages.map(msg => (
                    <div key={msg.id} className="bg-gray-50 rounded p-2 text-xs font-mono border border-gray-100">
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-sky-600 font-semibold">{msg.topic}</span>
                        <span className="text-gray-400">{new Date(msg.timestamp).toLocaleString("de-DE")}</span>
                      </div>
                      <div className="text-gray-700 break-all flex items-start gap-1">
                        <span className="flex-1">{msg.payload.length > 300 ? msg.payload.substring(0, 300) + "..." : msg.payload}</span>
                        <button
                          onClick={() => { navigator.clipboard.writeText(msg.payload); toast.success("Kopiert"); }}
                          className="shrink-0 text-gray-400 hover:text-gray-600"
                        >
                          <Copy className="w-3 h-3" />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </section>
      </main>
    </div>
  );
}
