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

        {/* Passwd-Datei Diagnose */}
        <PasswdFileDiagnostics />

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


function PasswdFileDiagnostics() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get("/mqtt/passwd-file-status");
      setData(res.data);
    } catch (err) {
      toast.error(getErrorMsg(err, "Status konnte nicht geladen werden"));
    }
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  const [restarting, setRestarting] = useState(false);

  const handleSync = async () => {
    setSyncing(true);
    try {
      const res = await api.post("/mqtt/passwd-file/sync");
      if (res.data?.ok) {
        toast.success("Passwd-Datei synchronisiert");
      } else {
        toast.error("Sync fehlgeschlagen - prüfe Backend-Log");
      }
      await load();
    } catch (err) {
      toast.error(getErrorMsg(err, "Sync fehlgeschlagen"));
    }
    setSyncing(false);
  };

  const handleRestart = async () => {
    if (!window.confirm("Mosquitto-Broker neu starten? Alle Gateways verbinden sich danach kurz neu.")) return;
    setRestarting(true);
    try {
      const res = await api.post("/mqtt/broker/restart");
      if (res.data?.ok) {
        toast.success("Mosquitto neu gestartet – Gateways verbinden sich jetzt neu");
      } else {
        toast.error("Neustart teilweise fehlgeschlagen – prüfe Backend-Log");
      }
    } catch (err) {
      toast.error(getErrorMsg(err, "Broker-Neustart fehlgeschlagen"));
    }
    setRestarting(false);
  };

  if (loading || !data) return null;

  const missing = data.missing_in_file || [];
  const hasProblem = !data.file_exists || missing.length > 0;

  return (
    <section className="bg-white rounded-xl border border-gray-200 overflow-hidden" data-testid="mqtt-passwd-diagnostics">
      <div className={`px-6 py-4 border-b ${hasProblem ? "bg-amber-50/50 border-amber-200" : "bg-emerald-50/50 border-emerald-200"}`}>
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div className="flex items-center gap-3">
            <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${hasProblem ? "bg-amber-100" : "bg-emerald-100"}`}>
              {hasProblem ? <AlertTriangle className="w-5 h-5 text-amber-600" /> : <CheckCircle className="w-5 h-5 text-emerald-600" />}
            </div>
            <div>
              <h2 className="text-base font-semibold text-gray-900">Mosquitto Passwd-Datei</h2>
              <p className="text-xs text-gray-500">
                {data.file_entries.length} Einträge in Datei · {data.db_users.length} Einträge in DB
                {missing.length > 0 && <span className="text-amber-700 font-semibold"> · {missing.length} fehlen!</span>}
              </p>
            </div>
          </div>
          <div className="flex gap-2 flex-wrap">
            <Button size="sm" variant="outline" onClick={load} data-testid="passwd-refresh-btn">
              <RefreshCw className="w-3.5 h-3.5 mr-1" /> Status neu laden
            </Button>
            <Button size="sm" onClick={handleSync} disabled={syncing} className="bg-fuchsia-600 hover:bg-fuchsia-700 text-white" data-testid="passwd-sync-btn">
              {syncing ? "Sync..." : "Datei neu schreiben"}
            </Button>
            <Button size="sm" onClick={handleRestart} disabled={restarting} variant="outline" className="border-orange-300 text-orange-700 hover:bg-orange-50" data-testid="broker-restart-btn">
              {restarting ? "Neustart..." : "Broker neu starten"}
            </Button>
          </div>
        </div>
      </div>

      <div className="px-6 py-4 space-y-3 text-sm">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div>
            <p className="text-[10px] font-semibold text-gray-500 uppercase tracking-wide mb-1">Konfigurierter Pfad</p>
            <code className="text-xs bg-gray-100 px-2 py-1 rounded block break-all">{data.mosquitto_passwd_file}</code>
            <p className="text-[10px] text-gray-400 mt-1">
              Datei existiert: {data.file_exists ? <span className="text-emerald-600 font-medium">Ja</span> : <span className="text-red-600 font-medium">Nein</span>}
              {data.file_last_modified && <span> · zuletzt: {new Date(data.file_last_modified).toLocaleString("de-DE")}</span>}
            </p>
          </div>
          <div>
            <p className="text-[10px] font-semibold text-gray-500 uppercase tracking-wide mb-1">System</p>
            <p className="text-xs text-gray-700">Platform: {data.platform}</p>
            <p className="text-xs text-gray-700">Mosquitto Exe: <code className="text-[10px] bg-gray-100 px-1 rounded">{data.mosquitto_exe}</code></p>
          </div>
        </div>

        {missing.length > 0 && (
          <div className="bg-amber-50 border border-amber-200 rounded-lg p-3" data-testid="passwd-missing-list">
            <p className="text-xs font-semibold text-amber-800 mb-2">
              Diese Credentials sind in der Datenbank, fehlen aber in der Passwd-Datei:
            </p>
            <div className="flex flex-wrap gap-1.5">
              {missing.map(u => (
                <code key={u} className="text-[11px] bg-white border border-amber-300 text-amber-800 px-2 py-0.5 rounded">{u}</code>
              ))}
            </div>
            <p className="text-[10px] text-amber-700 mt-2">
              → Klicke "Datei neu schreiben", damit die fehlenden Einträge übertragen werden.
            </p>
          </div>
        )}

        {data.file_only && data.file_only.length > 0 && (
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
            <p className="text-xs font-semibold text-blue-800 mb-2">
              Nur in Datei vorhanden (nicht in DB — evtl. manuell hinzugefügt):
            </p>
            <div className="flex flex-wrap gap-1.5">
              {data.file_only.map(u => (
                <code key={u} className="text-[11px] bg-white border border-blue-300 text-blue-800 px-2 py-0.5 rounded">{u}</code>
              ))}
            </div>
            <p className="text-[10px] text-blue-700 mt-2">Diese Einträge bleiben erhalten (werden nicht gelöscht).</p>
          </div>
        )}
      </div>
    </section>
  );
}
