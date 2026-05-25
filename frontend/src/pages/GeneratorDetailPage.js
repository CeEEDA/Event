import { useState, useEffect, useCallback } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { Logo } from "../components/Logo";
import api from "../lib/api";
import { toast } from "sonner";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import {
  ArrowLeft,
  RefreshCw,
  Zap,
  Gauge,
  Thermometer,
  Fuel,
  Clock,
  MapPin,
  Activity,
  AlertTriangle,
  CheckCircle,
  Battery,
  RotateCcw,
  Play,
  Square,
  ToggleLeft,
  ToggleRight,
  ClipboardList,
  ZapOff,
  FileText,
  Download,
  BarChart3,
  Stethoscope,
  ChevronDown,
  ChevronRight,
  Copy,
} from "lucide-react";
import {
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  Area,
  AreaChart,
  Line,
  LineChart,
} from "recharts";

import { MapContainer, Marker } from "react-leaflet";
import MapTileLayer from "../components/MapTileLayer";
import L from "leaflet";
import EventLog from "../components/EventLog";

const statusConfig = {
  running: { label: "Läuft", bg: "bg-emerald-50", border: "border-emerald-200", text: "text-emerald-700", dot: "bg-emerald-500" },
  standby: { label: "Standby", bg: "bg-sky-50", border: "border-sky-200", text: "text-sky-700", dot: "bg-sky-500" },
  online: { label: "Online", bg: "bg-teal-50", border: "border-teal-200", text: "text-teal-700", dot: "bg-teal-500" },
  verbunden: { label: "Verbunden", bg: "bg-amber-50", border: "border-amber-200", text: "text-amber-600", dot: "bg-amber-400" },
  warning: { label: "Warnung", bg: "bg-amber-50", border: "border-amber-200", text: "text-amber-700", dot: "bg-amber-500" },
  alarm: { label: "Alarm", bg: "bg-red-50", border: "border-red-200", text: "text-red-700", dot: "bg-red-500" },
  offline: { label: "Offline", bg: "bg-gray-50", border: "border-gray-200", text: "text-gray-500", dot: "bg-gray-400" },
};

function DeploymentHistory({ generatorId }) {
  const [deployments, setDeployments] = useState([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    const fetch = async () => {
      try {
        const { data } = await api.get(`/orders/deployments/by-generator/${generatorId}`);
        setDeployments(data.deployments || []);
      } catch {
        // silent
      } finally {
        setLoading(false);
      }
    };
    fetch();
  }, [generatorId]);

  const fmtDate = (d) => {
    if (!d) return "—";
    try {
      return new Date(d).toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" });
    } catch {
      return d;
    }
  };

  return (
    <div className="bg-white rounded-lg border border-gray-200" data-testid="deployment-history">
      <div className="p-4 border-b border-gray-100 flex items-center gap-2">
        <ClipboardList className="w-4 h-4 text-fuchsia-500" />
        <h3 className="text-sm font-semibold text-gray-700">Einsatzhistorie</h3>
      </div>
      {loading ? (
        <div className="p-6 text-center text-gray-400 text-sm">Laden...</div>
      ) : deployments.length === 0 ? (
        <div className="p-6 text-center text-gray-400 text-sm">Keine Einsätze erfasst</div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50 border-b border-gray-200">
                <th className="text-left px-4 py-2 font-medium text-gray-600">Auftrag</th>
                <th className="text-left px-4 py-2 font-medium text-gray-600">Eingeschaltet</th>
                <th className="text-left px-4 py-2 font-medium text-gray-600">Ausgeschaltet</th>
                <th className="text-right px-4 py-2 font-medium text-gray-600">Betriebsstd.</th>
                <th className="text-right px-4 py-2 font-medium text-gray-600">kWh Start</th>
                <th className="text-right px-4 py-2 font-medium text-gray-600">kWh Ende</th>
                <th className="text-left px-4 py-2 font-medium text-gray-600">Störungen</th>
              </tr>
            </thead>
            <tbody>
              {deployments.map((d) => {
                const orderPkNum = d.order_pk != null ? parseInt(d.order_pk, 10) : NaN;
                const hasValidOrderPk = Number.isFinite(orderPkNum) && orderPkNum > 0;
                return (
                <tr
                  key={d.id}
                  className={`border-b border-gray-100 hover:bg-fuchsia-50/50 ${hasValidOrderPk ? "cursor-pointer" : ""}`}
                  onClick={() => hasValidOrderPk && navigate(`/orders/${orderPkNum}`)}
                  data-testid={`deployment-${d.id}`}
                >
                  <td className="px-4 py-2.5 font-medium text-fuchsia-700">
                    <div className="flex items-center gap-1.5">
                      <span>{d.order_label || d.generator_name || `Auftrag #${d.order_pk}`}</span>
                      {d.auto_assigned && (
                        <span className="text-[9px] px-1.5 py-0.5 bg-fuchsia-100 text-fuchsia-700 rounded uppercase tracking-wide font-medium">
                          Auto
                        </span>
                      )}
                    </div>
                  </td>
                  <td className="px-4 py-2.5 text-gray-600">{fmtDate(d.started_at)}</td>
                  <td className="px-4 py-2.5 text-gray-600">{fmtDate(d.stopped_at)}</td>
                  <td className="px-4 py-2.5 text-right font-mono text-gray-700">{d.operating_hours || "—"}</td>
                  <td className="px-4 py-2.5 text-right font-mono text-gray-700">{d.kwh_start ?? "—"}</td>
                  <td className="px-4 py-2.5 text-right font-mono text-gray-700">{d.kwh_end ?? "—"}</td>
                  <td className="px-4 py-2.5 text-gray-500">
                    {d.faults ? (
                      <span className="text-red-600 flex items-center gap-1">
                        <AlertTriangle className="w-3 h-3" /> {d.faults}
                      </span>
                    ) : (
                      <span className="text-emerald-600 flex items-center gap-1">
                        <CheckCircle className="w-3 h-3" /> Keine
                      </span>
                    )}
                  </td>
                </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// Sanitize telemetry values: catch any remaining DSE sentinel garbage on the frontend
const METRIC_MAX = {
  voltage_l1: 2000, voltage_l2: 2000, voltage_l3: 2000,
  voltage_l1_l2: 2000, voltage_l2_l3: 2000, voltage_l3_l1: 2000,
  current_l1: 50000, current_l2: 50000, current_l3: 50000,
  frequency: 200, power_kw: 100000, power_kva: 100000,
  oil_pressure: 5000, coolant_temp: 500, fuel_level: 200,
  battery_voltage: 100, rpm: 50000, load_percent: 200,
  power_factor: 10, hours_run: 1000000,
};

function sanitizeValue(val, fieldHint) {
  if (val === null || val === undefined) return null;
  if (typeof val !== "number" || isNaN(val)) return null;
  // Generic large-number catch (DSE sentinel ~2.1 billion / 10 = ~214 million)
  if (Math.abs(val) > 10_000_000) return null;
  // Field-specific threshold
  if (fieldHint && METRIC_MAX[fieldHint] && Math.abs(val) > METRIC_MAX[fieldHint]) return null;
  return val;
}

function MetricBox({ icon: Icon, label, value, unit, color = "text-gray-900", field }) {
  const safeVal = sanitizeValue(value, field);
  const displayVal = safeVal !== null ? (typeof safeVal === "number" ? Math.round(safeVal * 100) / 100 : safeVal) : null;
  return (
    <div className="bg-white border border-gray-200 rounded-lg p-4">
      <div className="flex items-center gap-1.5 text-xs text-gray-400 mb-2">
        <Icon className="w-3.5 h-3.5" />
        {label}
      </div>
      <p className={`text-xl font-bold font-mono ${color}`}>
        {displayVal !== null ? displayVal : "–"}
        {unit && displayVal !== null && <span className="text-xs text-gray-400 ml-1">{unit}</span>}
      </p>
    </div>
  );
}

function AlarmRow({ alarm, onAcknowledge, onResolve }) {
  const isSevere = alarm.severity === "alarm";
  return (
    <div className={`flex items-center justify-between py-2.5 px-3 rounded-lg mb-1.5 ${isSevere ? "bg-red-50 border border-red-200" : "bg-amber-50 border border-amber-200"}`} data-testid={`alarm-${alarm.id}`}>
      <div className="flex items-center gap-2 flex-1 min-w-0">
        <AlertTriangle className={`w-4 h-4 flex-shrink-0 ${isSevere ? "text-red-500" : "text-amber-500"}`} />
        <div className="min-w-0">
          <p className="text-sm text-gray-900 truncate">{alarm.alarm_text}</p>
          <p className="text-[10px] text-gray-400 font-mono">
            {new Date(alarm.timestamp).toLocaleString("de-DE")}
          </p>
        </div>
      </div>
      <div className="flex gap-1.5 ml-2 flex-shrink-0">
        {!alarm.acknowledged && (
          <Button size="sm" variant="ghost" onClick={() => onAcknowledge(alarm.id)} className="text-amber-600 hover:text-amber-700 h-7 px-2 text-xs" data-testid={`ack-alarm-${alarm.id}`}>
            <CheckCircle className="w-3.5 h-3.5 mr-1" /> Quittieren
          </Button>
        )}
        <Button size="sm" variant="ghost" onClick={() => onResolve(alarm.id)} className="text-emerald-600 hover:text-emerald-700 h-7 px-2 text-xs" data-testid={`resolve-alarm-${alarm.id}`}>
          <RotateCcw className="w-3.5 h-3.5 mr-1" /> Behoben
        </Button>
      </div>
    </div>
  );
}

export default function GeneratorDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { isAdmin, user } = useAuth();
  const canControl = user?.role === "admin" || user?.role === "mitarbeiter";
  const [generator, setGenerator] = useState(null);
  const [telemetry, setTelemetry] = useState([]);
  const [alarms, setAlarms] = useState([]);
  const [loading, setLoading] = useState(true);
  const [hours, setHours] = useState(24);
  const [cmdLoading, setCmdLoading] = useState(null);

  // Diagnose-Panel: lazy geladen erst beim Aufklappen, sonst wuerden raw
  // MQTT-Logs jede Sekunde gezogen werden.
  const [diagOpen, setDiagOpen] = useState(false);
  const [diagData, setDiagData] = useState(null);
  const [diagLoading, setDiagLoading] = useState(false);
  const [diagExpanded, setDiagExpanded] = useState(() => new Set()); // expanded raw-message ids

  // Analyse-Bereich
  const today = new Date().toISOString().split("T")[0];
  const weekAgo = new Date(Date.now() - 7 * 86400000).toISOString().split("T")[0];
  const [analyseDateFrom, setAnalyseDateFrom] = useState(weekAgo);
  const [analyseDateTo, setAnalyseDateTo] = useState(today);
  const [analyseData, setAnalyseData] = useState([]);
  const [analyseLoading, setAnalyseLoading] = useState(false);
  const [exporting, setExporting] = useState(false);

  const fetchData = useCallback(async () => {
    // Wichtig: Generator-Doc ist die kritische Anforderung – wenn DAS klappt,
    // soll die Seite rendern. Telemetry/Alarms duerfen im Hintergrund nachladen,
    // sonst bleibt "Laden..." bei langsamen Telemetry-Queries oder einzelnen
    // 403/500-Fehlern haengen (frueher: Promise.all → ein Fehler killt alle drei).
    try {
      const genRes = await api.get(`/generators/${id}`);
      setGenerator(genRes.data);
    } catch (err) {
      if (err.response?.status === 403) {
        toast.error("Kein Zugriff auf diesen Generator");
      } else if (err.response?.status === 404) {
        toast.error("Generator nicht gefunden");
      } else {
        toast.error("Fehler beim Laden");
      }
      navigate("/generators");
      return;
    } finally {
      setLoading(false);
    }
    // Telemetry + Alarms unabhaengig nachladen – Fehler nur loggen, Page bleibt nutzbar
    try {
      const telRes = await api.get(`/generators/${id}/telemetry?hours=${hours}&limit=200`);
      setTelemetry(telRes.data);
    } catch (e) { console.error("Telemetry load failed:", e); }
    try {
      const alarmRes = await api.get(`/generators/${id}/alarms?active_only=true`);
      setAlarms(alarmRes.data);
    } catch (e) { console.error("Alarm load failed:", e); }
  }, [id, hours, navigate]);

  // Diagnose laden - Admin-only Endpoint, deshalb tolerant gegen 403/404
  // damit ein Mitarbeiter den Toggle einfach nicht sieht ohne Crash.
  const loadDiagnostics = useCallback(async () => {
    if (!isAdmin) return;
    setDiagLoading(true);
    try {
      const r = await api.get(`/generators/${id}/diagnostics?limit=50`);
      setDiagData(r.data);
    } catch (e) {
      console.error("Diagnostics load failed:", e);
      toast.error("Diagnose-Daten konnten nicht geladen werden");
    } finally {
      setDiagLoading(false);
    }
  }, [id, isAdmin]);

  const toggleDiag = () => {
    setDiagOpen((prev) => {
      const next = !prev;
      if (next && !diagData && !diagLoading) loadDiagnostics();
      return next;
    });
  };

  const toggleDiagRow = (mid) => {
    setDiagExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(mid)) next.delete(mid); else next.add(mid);
      return next;
    });
  };

  const copyDiagDump = () => {
    if (!diagData) return;
    try {
      navigator.clipboard.writeText(JSON.stringify(diagData, null, 2));
      toast.success("Diagnose-Dump in Zwischenablage kopiert");
    } catch {
      toast.error("Kopieren fehlgeschlagen");
    }
  };

  const fetchAnalyse = useCallback(async () => {
    if (!analyseDateFrom || !analyseDateTo) return;
    setAnalyseLoading(true);
    try {
      const from = new Date(analyseDateFrom).toISOString();
      const to = new Date(analyseDateTo + "T23:59:59").toISOString();
      const res = await api.get(`/generators/${id}/telemetry?from_time=${from}&to_time=${to}&limit=50000`);
      setAnalyseData(res.data);
    } catch {
      toast.error("Fehler beim Laden der Analysedaten");
    } finally {
      setAnalyseLoading(false);
    }
  }, [id, analyseDateFrom, analyseDateTo]);

  const handleExportCSV = async () => {
    if (analyseData.length === 0) return;
    setExporting(true);
    try {
      // CSV: ungekuerzt holen (raw=true umgeht 5-Min-Bucketing)
      const from = new Date(analyseDateFrom).toISOString();
      const to = new Date(analyseDateTo + "T23:59:59").toISOString();
      const rawRes = await api.get(
        `/generators/${id}/telemetry?from_time=${from}&to_time=${to}&limit=50000&raw=true`
      );
      const rawData = rawRes.data || [];
      const fields = ["timestamp", "voltage_l1", "voltage_l2", "voltage_l3", "current_l1", "current_l2", "current_l3",
        "power_total_w", "power_kw", "energy_kwh", "frequency", "battery_voltage", "coolant_temp", "oil_pressure",
        "fuel_level", "hours_run", "rpm", "dse_mode"];
      const header = fields.join(";");
      // Zahlen mit Komma als Dezimaltrenner ausgeben (DE-Format), sonst
      // interpretiert Excel z.B. "1.4" als Datum "1. April".
      const formatCell = (v) => {
        if (v == null) return "";
        if (typeof v === "number") return String(v).replace(".", ",");
        const s = String(v);
        if (/^-?\d+\.\d+$/.test(s)) return s.replace(".", ",");
        return s;
      };
      const rows = rawData.map(d => fields.map(f => formatCell(d[f])).join(";"));
      const csv = "\uFEFF" + [header, ...rows].join("\n");
      const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      const name = (generator?.serial_number || generator?.device_code || id).replace(/[^A-Za-z0-9._-]/g, "_");
      a.download = `${name}_${analyseDateFrom}_${analyseDateTo}.csv`;
      a.click();
      URL.revokeObjectURL(url);
      toast.success(`${rawData.length} Datenpunkte exportiert`);
    } catch {
      toast.error("CSV-Export fehlgeschlagen");
    } finally {
      setExporting(false);
    }
  };

  // Refresh: Bei Alarm alle 30s, normal alle 2 Min
  const [refreshMs, setRefreshMs] = useState(120000);

  useEffect(() => {
    if (generator?.status === "alarm" || alarms.length > 0) {
      setRefreshMs(30000);
    }
  }, [generator?.status, alarms.length]);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, refreshMs);
    return () => clearInterval(interval);
  }, [fetchData, refreshMs]);

  const handleAcknowledge = async (alarmId) => {
    try {
      await api.post(`/generators/${id}/alarms/${alarmId}/acknowledge`);
      toast.success("Alarm quittiert");
      fetchData();
    } catch (err) {
      toast.error("Fehler");
    }
  };

  const handleResolve = async (alarmId) => {
    try {
      await api.post(`/generators/${id}/alarms/${alarmId}/resolve`);
      toast.success("Alarm als behoben markiert");
      fetchData();
    } catch (err) {
      toast.error("Fehler");
    }
  };

  // Track pending command for button blink animation
  const [pendingCmd, setPendingCmd] = useState(null);

  // Auto-clear pendingCmd wenn erwarteter dse_mode in Telemetrie angekommen ist
  useEffect(() => {
    if (!pendingCmd) return;
    const t = generator?.latest_telemetry;
    const mode = t?.dse_mode || generator?.last_dse_mode;
    const running = t?.engine_running === true || (t?.rpm || 0) > 100;
    const cmdMatchMap = {
      stop: () => mode === "stop" || mode === "off" || (!running && mode !== "auto" && mode !== "manual"),
      auto_on: () => mode === "auto" || mode === "auto_manual_restore",
      manual: () => mode === "manual",
      start: () => running,
      test_on_load: () => mode === "test_on_load" || running,
      auto_manual_restore: () => mode === "auto_manual_restore" || mode === "auto",
    };
    const matcher = cmdMatchMap[pendingCmd];
    if (matcher && matcher()) {
      setPendingCmd(null);
      return;
    }
    // Commands ohne Mode-Wechsel: kurzer Timer (Quittung nach 3s)
    const noModeChangeCommands = ["reset", "reset_mains", "mute", "gen_switch_on", "gen_switch_off"];
    if (noModeChangeCommands.includes(pendingCmd)) {
      const timer = setTimeout(() => setPendingCmd(null), 3000);
      return () => clearTimeout(timer);
    }
  }, [generator, pendingCmd]);

  const sendCommand = async (command, label) => {
    setCmdLoading(command);
    try {
      // Pi-connected devices use pi-command endpoint, MQTT devices use mqtt/control
      const isPiDevice = generator?.is_pi_device || generator?.device_key_hash || generator?.connection_type === "pi_usb" || generator?.connection_type === "pi_rs232";
      const deviceId = generator?.device_id || (id.startsWith("dev-") ? id.slice(4) : id);
      
      if (isPiDevice) {
        await api.post(`/generators/pi-command/${deviceId}`, { command });
      } else {
        await api.post(`/mqtt/control/${id}`, { command });
      }
      toast.success(`${label} gesendet`);
      setPendingCmd(command);
      // Dichte Refreshes direkt nach Command, damit neuer dse_mode schnell sichtbar wird
      setTimeout(fetchData, 2000);
      setTimeout(fetchData, 4000);
      setTimeout(fetchData, 7000);
      setTimeout(fetchData, 12000);
      setTimeout(fetchData, 20000);
      setRefreshMs(10000);
      setTimeout(() => {
        setRefreshMs(1200000);
        setPendingCmd(null);
        fetchData();
      }, 120000);
    } catch (err) {
      const detail = err?.response?.data?.detail || "";
      if (detail.includes("MQTT client nicht verbunden")) {
        toast.error("MQTT-Broker nicht verbunden. Bitte Verbindung pruefen.");
      } else if (detail.includes("Kein MQTT-Gateway")) {
        toast.error("Kein Gateway konfiguriert. Bitte Geraeteverwaltung pruefen.");
      } else {
        toast.error(detail || "Befehl konnte nicht gesendet werden");
      }
    } finally {
      setCmdLoading(null);
    }
  };

  if (loading) {
    return (
      <div className="h-screen w-full flex items-center justify-center bg-white">
        <div className="animate-pulse text-fuchsia-600">Lade Generator...</div>
      </div>
    );
  }

  if (!generator) return null;

  const s = statusConfig[generator.status] || statusConfig.offline;
  const t = generator.latest_telemetry;

  return (
    <div className="min-h-screen bg-gray-50" data-testid="generator-detail">
      {/* Header */}
      <header className="sticky top-0 z-10 bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Button variant="ghost" size="sm" onClick={() => navigate("/generators")} className="text-gray-600 hover:text-fuchsia-600" data-testid="back-to-generators-btn">
              <ArrowLeft className="w-4 h-4 mr-1" /> Zurück
            </Button>
            <div className="h-5 w-px bg-gray-200" />
            <div>
              <h1 className="text-sm font-bold text-gray-900 tracking-tight">{generator.serial_number || generator.name}</h1>
              <p className="text-xs text-gray-400">{generator.model}</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${s.bg} ${s.border} border ${s.text}`}>
              <span className={`w-2 h-2 rounded-full ${s.dot} animate-pulse`} />
              {s.label}
            </span>
            <Button variant="ghost" size="sm" onClick={fetchData} className="text-gray-500 hover:text-fuchsia-600" data-testid="refresh-detail-btn">
              <RefreshCw className="w-4 h-4" />
            </Button>
            <Logo size="small" />
          </div>
        </div>
      </header>

      {/* Alarm-Banner wenn Störung aktiv */}
      {(generator.status === "alarm" || alarms.length > 0 || generator.latest_snapshot?.fault_text) && (
        <div className="bg-red-600 text-white px-4 py-3" data-testid="alarm-banner">
          <div className="max-w-7xl mx-auto flex items-center gap-3">
            <AlertTriangle className="w-5 h-5 flex-shrink-0 animate-pulse" />
            <div className="flex-1">
              <p className="text-sm font-bold">
                {alarms.length > 0
                  ? alarms.map(a => a.alarm_text).join(", ")
                  : generator.latest_snapshot?.fault_text || "Alarm aktiv"}
              </p>
              {alarms.length > 0 && alarms[0].timestamp && (
                <p className="text-xs text-red-200">seit {new Date(alarms[0].timestamp).toLocaleString("de-DE")}</p>
              )}
            </div>
            {isAdmin && (
              <button
                onClick={toggleDiag}
                className="flex items-center gap-1.5 text-xs bg-white/15 hover:bg-white/25 px-3 py-1.5 rounded-md font-medium transition-colors"
                data-testid="diag-toggle-banner"
                title="Roh-Daten ansehen damit der Trigger des Alarms gefunden werden kann"
              >
                <Stethoscope className="w-3.5 h-3.5" />
                {diagOpen ? "Diagnose ausblenden" : "Diagnose oeffnen"}
              </button>
            )}
          </div>
        </div>
      )}

      {/* Diagnose-Panel: zeigt offene Alarme, decoded status-bits und letzte
          MQTT-Roh-Messages fuer dieses Geraet - hilft false-positive Alarme
          (Portal zeigt Alarm, vor Ort alles okay) zu debuggen. */}
      {isAdmin && diagOpen && (
        <div className="bg-slate-900 text-slate-100 border-t border-slate-700" data-testid="diag-panel">
          <div className="max-w-7xl mx-auto px-4 py-4 space-y-4">
            <div className="flex items-center justify-between flex-wrap gap-2">
              <div className="flex items-center gap-2">
                <Stethoscope className="w-4 h-4 text-emerald-400" />
                <h3 className="text-sm font-semibold">Diagnose &middot; Roh-Daten</h3>
                {diagLoading && <RefreshCw className="w-3 h-3 animate-spin text-slate-400" />}
              </div>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={loadDiagnostics}
                  disabled={diagLoading}
                  className="text-xs px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 disabled:opacity-50"
                  data-testid="diag-refresh"
                >
                  <RefreshCw className="w-3 h-3 inline mr-1" /> Aktualisieren
                </button>
                <button
                  type="button"
                  onClick={copyDiagDump}
                  disabled={!diagData}
                  className="text-xs px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 disabled:opacity-30 inline-flex items-center gap-1"
                  data-testid="diag-copy-dump"
                >
                  <Copy className="w-3 h-3" /> JSON kopieren
                </button>
              </div>
            </div>

            {!diagData && !diagLoading && (
              <p className="text-xs text-slate-400">Klicke auf &bdquo;Aktualisieren&ldquo; um die Daten zu laden.</p>
            )}

            {diagData && (
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                {/* Linke Spalte: Open Alarms + Status-Bits */}
                <div className="space-y-4">
                  <section data-testid="diag-open-alarms">
                    <h4 className="text-[11px] uppercase tracking-wide text-slate-400 mb-1.5">
                      Offene Alarme ({(diagData.open_alarms || []).length})
                    </h4>
                    {(diagData.open_alarms || []).length === 0 ? (
                      <p className="text-xs text-slate-500 italic">Keine offenen Alarme in der DB</p>
                    ) : (
                      <ul className="space-y-1">
                        {diagData.open_alarms.map((a) => (
                          <li key={a.id} className="flex items-start gap-2 text-xs bg-slate-800/60 rounded px-2 py-1.5">
                            <span className={`shrink-0 mt-0.5 font-mono px-1.5 py-0.5 rounded text-[10px] ${a.severity === "shutdown" ? "bg-red-500/30 text-red-200" : "bg-amber-500/30 text-amber-200"}`}>
                              {a.alarm_code}
                            </span>
                            <div className="min-w-0 flex-1">
                              <p className="text-slate-100">{a.alarm_text}</p>
                              <p className="text-[10px] text-slate-400">
                                {new Date(a.timestamp).toLocaleString("de-DE")} &middot; {a.severity}
                                {a.acknowledged && " &middot; ack"}
                              </p>
                            </div>
                          </li>
                        ))}
                      </ul>
                    )}
                  </section>

                  <section data-testid="diag-alarm-conditions">
                    <h4 className="text-[11px] uppercase tracking-wide text-slate-400 mb-1.5">
                      Alarm-Ursachen (Page 8 Named Conditions)
                      {Array.isArray(diagData.alarm_conditions_active) && (
                        <span className="ml-1 text-slate-300 font-mono">
                          ({diagData.alarm_conditions_active.length})
                        </span>
                      )}
                    </h4>
                    {(!diagData.alarm_conditions_active || diagData.alarm_conditions_active.length === 0) ? (
                      diagData.alarm_conditions_raw == null ? (
                        <p className="text-xs text-slate-500 italic">
                          Keine Page-8-Daten in Telemetrie. Pi muss aktualisiert werden (siehe Refresh-PI-URL).
                        </p>
                      ) : (
                        <p className="text-xs text-emerald-400/80 italic">Keine aktiven Alarm-Ursachen — sauber.</p>
                      )
                    ) : (
                      <ul className="space-y-1 text-xs">
                        {diagData.alarm_conditions_active.map((c) => {
                          const sevCls = c.severity === "shutdown" ? "bg-red-600/20 text-red-300 border-red-600/40"
                                       : c.severity === "electrical_trip" ? "bg-orange-600/20 text-orange-300 border-orange-600/40"
                                       : c.severity === "warning" ? "bg-amber-600/20 text-amber-300 border-amber-600/40"
                                       : "bg-slate-600/20 text-slate-300 border-slate-600/40";
                          return (
                            <li key={c.modbus_addr} className={`flex items-start gap-2 px-2 py-1.5 rounded border ${sevCls}`}>
                              <span className="text-[10px] font-mono font-bold uppercase shrink-0 mt-0.5">{c.severity_label}</span>
                              <span className="flex-1">{c.label}</span>
                              <span className="text-[10px] font-mono text-slate-400 shrink-0">P8R{c.page8_reg}</span>
                            </li>
                          );
                        })}
                      </ul>
                    )}
                  </section>

                  <section data-testid="diag-status-bits">
                    <h4 className="text-[11px] uppercase tracking-wide text-slate-400 mb-1.5">
                      DSE Status-Bits {diagData.status_bits_raw != null && (
                        <span className="font-mono text-slate-300 ml-1">
                          (0x{Number(diagData.status_bits_raw).toString(16).toUpperCase().padStart(4, "0")} = {diagData.status_bits_raw})
                        </span>
                      )}
                    </h4>
                    {(diagData.status_bits_decoded || []).length === 0 ? (
                      <p className="text-xs text-slate-500 italic">Keine status_bits in Telemetrie (Page-3 Reg-6 noch nicht empfangen)</p>
                    ) : (
                      <ul className="space-y-0.5 text-xs font-mono">
                        {diagData.status_bits_decoded.map((b) => (
                          <li key={b.mask_hex} className={`flex items-center gap-2 ${b.set ? "text-amber-300" : "text-slate-500"}`}>
                            <span className="w-4">{b.set ? "●" : "○"}</span>
                            <span className="w-16">{b.mask_hex}</span>
                            <span className="flex-1 truncate">{b.label}</span>
                          </li>
                        ))}
                      </ul>
                    )}
                  </section>
                </div>

                {/* Rechte Spalte: Roh-MQTT-Messages */}
                <section data-testid="diag-raw-messages">
                  <h4 className="text-[11px] uppercase tracking-wide text-slate-400 mb-1.5">
                    Letzte MQTT-Roh-Messages ({diagData.raw_messages_count || 0})
                  </h4>
                  {(diagData.raw_messages || []).length === 0 ? (
                    <p className="text-xs text-slate-500 italic">
                      Keine Roh-Messages gefunden. {!diagData.filter_used && "Geraet hat keine konfigurierte module_uid / topic_prefix - kann nicht filtern."}
                    </p>
                  ) : (
                    <ul className="space-y-1 max-h-96 overflow-y-auto pr-1">
                      {diagData.raw_messages.map((m, idx) => {
                        const mid = `${m.timestamp}-${idx}`;
                        const isExp = diagExpanded.has(mid);
                        const payloadStr = typeof m.payload === "string" ? m.payload : JSON.stringify(m.payload);
                        return (
                          <li key={mid} className="bg-slate-800/60 rounded text-xs">
                            <button
                              type="button"
                              onClick={() => toggleDiagRow(mid)}
                              className="w-full flex items-start gap-1.5 px-2 py-1.5 text-left hover:bg-slate-800"
                              data-testid={`diag-raw-row-${idx}`}
                            >
                              {isExp ? <ChevronDown className="w-3 h-3 mt-0.5 shrink-0 text-slate-400" /> : <ChevronRight className="w-3 h-3 mt-0.5 shrink-0 text-slate-400" />}
                              <div className="min-w-0 flex-1">
                                <p className="font-mono text-emerald-300 truncate">{m.topic}</p>
                                <p className="text-[10px] text-slate-400">{new Date(m.timestamp).toLocaleString("de-DE")}</p>
                                {!isExp && (
                                  <p className="font-mono text-slate-300 truncate">{payloadStr}</p>
                                )}
                              </div>
                            </button>
                            {isExp && (
                              <pre className="px-2 pb-2 text-[11px] font-mono text-slate-200 whitespace-pre-wrap break-all">{payloadStr}</pre>
                            )}
                          </li>
                        );
                      })}
                    </ul>
                  )}
                  {diagData.meta && (
                    <div className="mt-3 text-[10px] text-slate-500 leading-snug" data-testid="diag-meta">
                      <p>Topic-Prefix: <span className="font-mono text-slate-400">{diagData.meta.dse_mqtt_topic_prefix || "(nicht gesetzt)"}</span></p>
                      <p>Module-UID: <span className="font-mono text-slate-400">{diagData.meta.dse_module_uid || "(nicht gesetzt)"}</span></p>
                      <p>Letzter Kontakt: <span className="text-slate-400">{diagData.meta.last_seen ? new Date(diagData.meta.last_seen).toLocaleString("de-DE") : "—"}</span></p>
                    </div>
                  )}
                </section>
              </div>
            )}
          </div>
        </div>
      )}

      <main className="max-w-7xl mx-auto px-4 py-6 space-y-6">
        {/* Info Bar */}
        <div className="flex flex-wrap gap-4 text-xs text-gray-400">
          {generator.location_name && (
            <span className="flex items-center gap-1"><MapPin className="w-3.5 h-3.5" /> {generator.location_name}</span>
          )}
          <span className="flex items-center gap-1"><Activity className="w-3.5 h-3.5" /> {generator.model}</span>
          <span className="flex items-center gap-1"><Clock className="w-3.5 h-3.5" /> Letzter Kontakt: {generator.last_seen ? new Date(generator.last_seen).toLocaleString("de-DE") : "–"}</span>
        </div>

        {/* DSE Control Panel */}
        {canControl && (() => {
          const isRunning = generator.status === "running" || generator.latest_telemetry?.engine_running === true || (generator.latest_telemetry?.rpm || 0) > 0;
          const dseMode = t?.dse_mode || generator?.last_dse_mode || null;
          const isAuto = dseMode === "auto" || dseMode === "auto_manual_restore";
          const isManual = dseMode === "manual";
          // Stop leuchtet nur wenn Motor AUS UND nicht im Auto/Manual Modus
          const isStop = !isRunning && (dseMode === "stop" || dseMode === "off" || (!isAuto && !isManual));
          const hasPower = sanitizeValue(t?.power_total_w || t?.power_kw, "power_kw") > 0;
          const genReady = t?.generator_available === true || (hasPower || isRunning);
          const switchClosed = t?.breaker_closed === true || (hasPower && isRunning);
          const model = (generator.model || "").toUpperCase();
          const is5510 = model.includes("5510");
          const isL401 = model.includes("L401");
          const is4520 = model.includes("4520");
          const isFullControl = !isL401 && !is4520; // L401 (Lichtmast) + 4520 MKII = nur Start/Auto/Stop
          const canWrite = true; // FC16 @4104 funktioniert (DSE antwortet mit FC03 Read-Back)

          const DseImgBtn = ({ cmd, label, imgSrc, size = 64, disabled = false, active = false, glowColor = null }) => {
            const isPending = pendingCmd === cmd;
            const showActive = active || isPending;
            const effectiveGlow = isPending ? "rgba(34,197,94,0.6)" : glowColor;
            return (
            <button
              onClick={() => !disabled && sendCommand(cmd, label)}
              disabled={disabled || cmdLoading !== null}
              className={`group focus:outline-none flex flex-col items-center ${disabled ? "opacity-30 cursor-not-allowed" : "disabled:opacity-40"}`}
              data-testid={`cmd-${cmd}-btn`}
              title={disabled ? "Fernsteuerung nur mit DSE 890" : label}
            >
              <div
                className={`relative rounded-full transition-all duration-200 ${isPending ? "animate-pulse" : ""}`}
                style={{
                  width: size, height: size,
                  filter: showActive && effectiveGlow ? `drop-shadow(0 0 10px ${effectiveGlow})` : disabled ? 'grayscale(80%)' : 'none',
                  transform: cmdLoading === cmd ? 'scale(0.92)' : 'scale(1)',
                }}
              >
                <img
                  src={imgSrc}
                  alt={label}
                  className={`w-full h-full object-contain rounded-full transition-all duration-150 ${disabled ? '' : 'group-hover:brightness-110 group-active:brightness-90'}`}
                  draggable={false}
                  style={{ opacity: showActive ? 1 : disabled ? 0.5 : 0.85 }}
                />
                {showActive && effectiveGlow && (
                  <div
                    className={`absolute inset-0 rounded-full pointer-events-none ${isPending ? "animate-pulse" : ""}`}
                    style={{ boxShadow: `0 0 16px 4px ${effectiveGlow}` }}
                  />
                )}
              </div>
              <span className="block text-[10px] text-gray-500 text-center mt-1.5 font-medium tracking-wide">
                {cmdLoading === cmd ? "..." : isPending ? "Warte..." : label}
              </span>
            </button>
            );
          };

          const StatusIndicator = ({ on, label, imgSrc }) => (
            <div className="flex items-center gap-2.5">
              <div className="relative" style={{ width: 40, height: 40 }}>
                <img
                  src={imgSrc}
                  alt={label}
                  className="w-full h-full object-contain rounded-full"
                  style={{
                    opacity: on ? 1 : 0.3,
                    filter: on ? 'drop-shadow(0 0 6px rgba(74,222,128,0.6))' : 'grayscale(100%) brightness(1.2)',
                    transition: 'all 0.3s ease',
                  }}
                />
              </div>
              <div className="flex flex-col">
                <span className="text-xs font-medium text-gray-700">{label}</span>
                <div className="flex items-center gap-1.5 mt-0.5">
                  <div className={`w-8 h-3 rounded-sm border transition-colors duration-300 ${on ? "bg-emerald-400 border-emerald-500" : "bg-gray-200 border-gray-300"}`}
                    style={on ? { boxShadow: '0 0 6px rgba(52,211,153,0.5)' } : {}} />
                  <span className={`text-[10px] font-medium ${on ? "text-emerald-600" : "text-gray-400"}`}>
                    {on ? "EIN" : "AUS"}
                  </span>
                </div>
              </div>
            </div>
          );

          return (
            <div className="bg-white border border-gray-200 rounded-xl overflow-hidden shadow-sm" data-testid="generator-controls">
              {/* Header */}
              <div className="px-5 pt-4 pb-2 flex items-center justify-between">
                <span className="text-xs font-bold text-gray-500 uppercase tracking-widest">DSE Steuerung</span>
                {(
                  <div className="flex items-center gap-2">
                    <div className={`w-2 h-2 rounded-full ${isRunning ? "bg-emerald-500 animate-pulse" : "bg-gray-300"}`} />
                    <span className={`text-[10px] font-medium ${isRunning ? "text-emerald-600" : "text-gray-400"}`}>
                      {isRunning ? "Motor laeuft" : "Motor aus"}
                    </span>
                  </div>
                )}
              </div>

              {/* Status LEDs Row */}
              {(
                <div className="px-5 py-2.5 flex flex-wrap items-center gap-4 border-t border-gray-100">
                  <div className="flex items-center gap-1.5">
                    <div className={`w-8 h-3.5 rounded-sm border transition-colors duration-300 ${isRunning ? "bg-emerald-400 border-emerald-500" : "bg-gray-200 border-gray-300"}`}
                      style={isRunning ? { boxShadow: '0 0 6px rgba(52,211,153,0.5)' } : {}} />
                    <span className="text-[10px] text-gray-500 font-medium">Motor laeuft</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <div className={`w-8 h-3.5 rounded-sm border transition-colors duration-300 ${isAuto ? "bg-emerald-400 border-emerald-500" : "bg-gray-200 border-gray-300"}`}
                      style={isAuto ? { boxShadow: '0 0 6px rgba(52,211,153,0.5)' } : {}} />
                    <span className="text-[10px] text-gray-500 font-medium">Auto-Modus</span>
                  </div>
                </div>
              )}

              {/* Status Indicators: Generator bereit + Hauptschalter geschlossen */}
              {isFullControl && (
                <div className="px-5 py-4 flex flex-wrap items-center justify-center gap-8 border-t border-gray-100">
                  <StatusIndicator on={genReady} label="Generator bereit" imgSrc="/dse-buttons/geno.png" />
                  <StatusIndicator on={switchClosed} label="Hauptschalter geschlossen" imgSrc="/dse-buttons/netz.png" />
                </div>
              )}

              {/* Main Control Buttons */}
              <div className="px-5 py-5 flex flex-col items-center gap-3 border-t border-gray-100">
                <div className="flex items-end justify-center gap-4 sm:gap-6 flex-wrap">
                <DseImgBtn cmd="stop" label="Stop" imgSrc="/dse-buttons/stop.png"
                  disabled={!canWrite} size={68}
                  active={isStop} glowColor="rgba(239,68,68,0.5)" />

                {isFullControl && (
                  <DseImgBtn cmd="manual" label="Manuell" imgSrc="/dse-buttons/hand.png"
                    disabled={!canWrite} size={68}
                    active={isManual} glowColor="rgba(251,191,36,0.5)" />
                )}

                <DseImgBtn cmd="auto_on" label="Auto" imgSrc="/dse-buttons/auto.png"
                  disabled={!canWrite} size={68}
                  active={isAuto} glowColor="rgba(52,211,153,0.5)" />

                {isFullControl && (
                  <DseImgBtn cmd="mute" label="Hupe Aus" imgSrc="/dse-buttons/hupe-aus.png"
                    disabled={!canWrite} size={68} />
                )}

                <DseImgBtn cmd="start" label="Start" imgSrc="/dse-buttons/start.png"
                  disabled={!canWrite} size={68}
                  active={isRunning} glowColor="rgba(34,197,94,0.5)" />
                </div>
              </div>

              {/* Transfer Switches - Stromerzeuger */}
              {isFullControl && (
                <div className="px-5 py-4 flex items-end justify-center gap-5 border-t border-gray-100">
                  <DseImgBtn cmd="gen_switch_on" label="Hauptschalter EIN" imgSrc="/dse-buttons/geno.png"
                    disabled={!canWrite} size={52} />
                  <DseImgBtn cmd="gen_switch_off" label="Hauptschalter AUS" imgSrc="/dse-buttons/netz.png"
                    disabled={!canWrite} size={52} />
                </div>
              )}
            </div>
          );
        })()}

        {/* Live Metrics */}
        {t ? (
          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3" data-testid="live-metrics">
            <MetricBox icon={Zap} label="Leistung" value={t.power_kw} unit="kW" color="text-fuchsia-600" field="power_kw" />
            <MetricBox icon={Activity} label="Frequenz" value={t.frequency} unit="Hz" field="frequency" />
            <MetricBox icon={Thermometer} label="Kühlmittel" value={t.coolant_temp} unit="°C" color={sanitizeValue(t.coolant_temp, "coolant_temp") > 90 ? "text-amber-600" : "text-gray-900"} field="coolant_temp" />
            <MetricBox icon={Fuel} label="Tankstand" value={t.fuel_level} unit="%" color={sanitizeValue(t.fuel_level, "fuel_level") < 25 ? "text-red-500" : "text-gray-900"} field="fuel_level" />
            <MetricBox icon={Battery} label="Batterie" value={t.battery_voltage} unit="V" field="battery_voltage" />
          </div>
        ) : (
          <div className="bg-white border border-gray-200 rounded-lg p-8 text-center text-gray-400">
            Keine aktuellen Telemetrie-Daten verfügbar
          </div>
        )}

        {/* Electrical Details - DSE L401 = 1-phasig (Lichtmasten) */}
        {t && (() => {
          const model = (generator.model || generator.controller || "").toLowerCase();
          const isSinglePhase = model.includes("l401");
          return isSinglePhase ? (
            <div className="grid grid-cols-2 md:grid-cols-2 gap-3" data-testid="electrical-details">
              <MetricBox icon={Zap} label="Spannung" value={t.voltage_l1} unit="V" field="voltage_l1" />
              <MetricBox icon={Activity} label="Strom" value={t.current_l1} unit="A" field="current_l1" />
            </div>
          ) : (
            <div className="grid grid-cols-3 md:grid-cols-6 gap-3" data-testid="electrical-details">
              <MetricBox icon={Zap} label="U L1" value={t.voltage_l1} unit="V" field="voltage_l1" />
              <MetricBox icon={Zap} label="U L2" value={t.voltage_l2} unit="V" field="voltage_l2" />
              <MetricBox icon={Zap} label="U L3" value={t.voltage_l3} unit="V" field="voltage_l3" />
              <MetricBox icon={Activity} label="I L1" value={t.current_l1} unit="A" field="current_l1" />
              <MetricBox icon={Activity} label="I L2" value={t.current_l2} unit="A" field="current_l2" />
              <MetricBox icon={Activity} label="I L3" value={t.current_l3} unit="A" field="current_l3" />
            </div>
          );
        })()}

        {/* Engine Details – L401: kein Öldruck, kein cos φ, kein Strom */}
        {t && (() => {
          const model = (generator.model || generator.controller || "").toLowerCase();
          const isL401 = model.includes("l401");
          return isL401 ? (
            <div className="grid grid-cols-2 md:grid-cols-3 gap-3" data-testid="engine-details">
              <MetricBox icon={RotateCcw} label="Drehzahl" value={t.rpm} unit="U/min" field="rpm" />
              <MetricBox icon={Clock} label="Betriebsstunden" value={t.hours_run} unit="h" field="hours_run" />
              <MetricBox icon={Fuel} label="Tankstand" value={t.fuel_level} unit="%" color={sanitizeValue(t.fuel_level, "fuel_level") < 25 ? "text-red-500" : "text-gray-900"} field="fuel_level" />
            </div>
          ) : (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3" data-testid="engine-details">
              <MetricBox icon={RotateCcw} label="Drehzahl" value={t.rpm} unit="U/min" field="rpm" />
              <MetricBox icon={Gauge} label="Öldruck" value={t.oil_pressure} unit="bar" field="oil_pressure" />
              <MetricBox icon={Clock} label="Betriebsstunden" value={t.hours_run} unit="h" field="hours_run" />
              <MetricBox icon={Activity} label="cos φ" value={t.power_factor} unit="" field="power_factor" />
            </div>
          );
        })()}

        {/* Active Alarms */}
        {alarms.length > 0 && (
          <div data-testid="active-alarms">
            <h2 className="text-sm font-semibold text-gray-900 mb-3 flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-amber-500" /> Aktive Alarme ({alarms.length})
            </h2>
            {alarms.map((a) => (
              <AlarmRow key={a.id} alarm={a} onAcknowledge={handleAcknowledge} onResolve={handleResolve} />
            ))}
          </div>
        )}

        {/* Event Log */}
        <EventLog generatorId={id} />

        {/* GPS Location */}
        {generator.latitude && generator.longitude && (
          <div className="bg-white border border-gray-200 rounded-lg overflow-hidden" data-testid="generator-map">
            <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100">
              <h2 className="text-sm font-semibold text-gray-900 flex items-center gap-2">
                <MapPin className="w-4 h-4 text-fuchsia-500" /> Standort
              </h2>
              <span className="text-xs text-gray-400">
                {Number(generator.latitude).toFixed(5)}, {Number(generator.longitude).toFixed(5)}
                {generator.last_gps_update && <span className="ml-2">({new Date(generator.last_gps_update).toLocaleString("de-DE")})</span>}
              </span>
            </div>
            <div style={{ height: 260 }}>
              <MapContainer
                center={[generator.latitude, generator.longitude]}
                zoom={14}
                style={{ height: "100%", width: "100%" }}
                scrollWheelZoom={false}
              >
                <MapTileLayer />
                <Marker
                  position={[generator.latitude, generator.longitude]}
                  icon={L.divIcon({
                    className: "custom-marker",
                    html: '<div style="width:16px;height:16px;background:#A855F7;border-radius:50%;border:3px solid white;box-shadow:0 2px 6px rgba(0,0,0,0.3)"></div>',
                    iconSize: [16, 16],
                    iconAnchor: [8, 8],
                  })}
                />
              </MapContainer>
            </div>
          </div>
        )}

        {/* ============ Analyse-Bereich ============ */}
        <div className="bg-white border border-gray-200 rounded-lg overflow-hidden" data-testid="analyse-section">
          <div className="px-5 py-4 border-b border-gray-100">
            <h2 className="text-sm font-semibold text-gray-900 flex items-center gap-2">
              <BarChart3 className="w-4 h-4 text-fuchsia-500" /> Analyse
            </h2>
          </div>

          {/* Zeitraum + Export */}
          <div className="px-5 py-4 flex flex-wrap items-end gap-4">
            <div className="space-y-1">
              <Label className="text-gray-500 text-xs">Von</Label>
              <Input
                type="date"
                value={analyseDateFrom}
                onChange={(e) => setAnalyseDateFrom(e.target.value)}
                className="border-gray-300 text-sm w-[150px]"
                data-testid="analyse-date-from"
              />
            </div>
            <div className="space-y-1">
              <Label className="text-gray-500 text-xs">Bis</Label>
              <Input
                type="date"
                value={analyseDateTo}
                onChange={(e) => setAnalyseDateTo(e.target.value)}
                className="border-gray-300 text-sm w-[150px]"
                data-testid="analyse-date-to"
              />
            </div>

            <Button
              variant="outline"
              size="sm"
              onClick={fetchAnalyse}
              disabled={analyseLoading}
              className="text-gray-600 hover:text-fuchsia-600"
              data-testid="analyse-load-btn"
            >
              <RefreshCw className={`w-4 h-4 mr-1.5 ${analyseLoading ? "animate-spin" : ""}`} />
              {analyseLoading ? "Laden..." : "Laden"}
            </Button>

            <Button
              variant="outline"
              size="sm"
              onClick={handleExportCSV}
              disabled={exporting || analyseData.length === 0}
              className="text-gray-600 hover:text-fuchsia-600"
              data-testid="analyse-export-btn"
            >
              <Download className="w-4 h-4 mr-1.5" />
              {exporting ? "Exportiert..." : "CSV Export"}
            </Button>

            <span className="text-xs text-gray-400 flex items-center gap-1 ml-auto">
              <Clock className="w-3 h-3" />
              {analyseData.length} Datenpunkte
            </span>
          </div>

          {/* Analyse-Charts */}
          {analyseData.length > 0 && (() => {
            // WICHTIG: null != 0. Wenn ein Wert nicht vorhanden ist, soll er
            // im Chart eine Lücke erzeugen (Recharts ignoriert null), NICHT
            // als 0 angezeigt werden. Sonst wirkt's als wäre der Motor aus.
            const _val = (raw, field) => {
              const v = sanitizeValue(raw, field);
              return (v === null || v === undefined || Number.isNaN(v)) ? null : v;
            };
            const chartData = analyseData.map(r => ({
              time: new Date(r.timestamp).toLocaleString("de-DE", { day:"2-digit", month:"2-digit", hour:"2-digit", minute:"2-digit" }),
              P_kW: _val(r.power_kw, "power_kw") ?? (r.power_total_w ? Math.round(sanitizeValue(r.power_total_w) / 100) / 10 : null),
              kWh: r.energy_kwh ?? null,
              U_L1: _val(r.voltage_l1, "voltage_l1"),
              U_L2: _val(r.voltage_l2, "voltage_l2"),
              U_L3: _val(r.voltage_l3, "voltage_l3"),
              I_L1: _val(r.current_l1, "current_l1"),
              I_L2: _val(r.current_l2, "current_l2"),
              I_L3: _val(r.current_l3, "current_l3"),
              Freq: _val(r.frequency, "frequency"),
              Batt: _val(r.battery_voltage, "battery_voltage"),
              Fuel: _val(r.fuel_level, "fuel_level") ?? _val(r.fuel_level_pct, "fuel_level"),
              Cool: _val(r.coolant_temp, "coolant_temp") ?? _val(r.coolant_temp_c, "coolant_temp"),
            }));
            return (
              <div className="px-5 pb-5 space-y-4">
                {/* Leistung */}
                <div className="border border-gray-100 rounded-lg p-4" data-testid="analyse-power-chart">
                  <h3 className="text-xs font-semibold text-gray-700 mb-3 flex items-center gap-1.5">
                    <Zap className="w-3.5 h-3.5 text-amber-500" /> Leistung (kW)
                  </h3>
                  <ResponsiveContainer width="100%" height={220}>
                    <AreaChart data={chartData}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                      <XAxis dataKey="time" tick={{ fontSize: 9 }} interval="preserveStartEnd" />
                      <YAxis tick={{ fontSize: 10 }} />
                      <Tooltip contentStyle={{ fontSize: 12 }} />
                      <Area type="monotone" dataKey="P_kW" name="kW" stroke="#A855F7" fill="#A855F7" fillOpacity={0.15} strokeWidth={1.5} dot={false} />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>

                {/* kWh Zaehlerstand */}
                {(() => {
                  const first = analyseData.find(r => r.energy_kwh && r.energy_kwh > 0);
                  const last = [...analyseData].reverse().find(r => r.energy_kwh && r.energy_kwh > 0);
                  const startKwh = first?.energy_kwh || 0;
                  const endKwh = last?.energy_kwh || 0;
                  const diff = Math.round((endKwh - startKwh) * 10) / 10;
                  const startTs = first ? new Date(first.timestamp).toLocaleString("de-DE", { day:"2-digit", month:"2-digit", year:"numeric", hour:"2-digit", minute:"2-digit" }) : "–";
                  const endTs = last ? new Date(last.timestamp).toLocaleString("de-DE", { day:"2-digit", month:"2-digit", year:"numeric", hour:"2-digit", minute:"2-digit" }) : "–";
                  return (
                    <div className="border border-gray-100 rounded-lg p-4" data-testid="analyse-kwh-meter">
                      <h3 className="text-xs font-semibold text-gray-700 mb-4 flex items-center gap-1.5">
                        <Gauge className="w-3.5 h-3.5 text-amber-500" /> Energiezaehler (kWh)
                      </h3>
                      <div className="grid grid-cols-3 gap-6">
                        <div className="text-center">
                          <span className="block text-[10px] text-gray-400 uppercase tracking-wider mb-1">Start</span>
                          <span className="block text-2xl font-bold text-gray-800" data-testid="kwh-start">{startKwh.toLocaleString("de-DE", { minimumFractionDigits: 1 })}</span>
                          <span className="block text-[10px] text-gray-400 mt-0.5">kWh</span>
                          <span className="block text-[10px] text-gray-300 mt-1">{startTs}</span>
                        </div>
                        <div className="text-center">
                          <span className="block text-[10px] text-gray-400 uppercase tracking-wider mb-1">Ende</span>
                          <span className="block text-2xl font-bold text-gray-800" data-testid="kwh-end">{endKwh.toLocaleString("de-DE", { minimumFractionDigits: 1 })}</span>
                          <span className="block text-[10px] text-gray-400 mt-0.5">kWh</span>
                          <span className="block text-[10px] text-gray-300 mt-1">{endTs}</span>
                        </div>
                        <div className="text-center">
                          <span className="block text-[10px] text-gray-400 uppercase tracking-wider mb-1">Verbrauch</span>
                          <span className={`block text-2xl font-bold ${diff > 0 ? "text-fuchsia-600" : "text-gray-400"}`} data-testid="kwh-diff">{diff.toLocaleString("de-DE", { minimumFractionDigits: 1 })}</span>
                          <span className="block text-[10px] text-gray-400 mt-0.5">kWh</span>
                        </div>
                      </div>
                    </div>
                  );
                })()}

                {/* Spannung + Strom */}
                <div className="grid md:grid-cols-2 gap-4">
                  <div className="border border-gray-100 rounded-lg p-4" data-testid="analyse-voltage-chart">
                    <h3 className="text-xs font-semibold text-gray-700 mb-3 flex items-center gap-1.5">
                      <Gauge className="w-3.5 h-3.5 text-blue-500" /> Spannung (V)
                    </h3>
                    <ResponsiveContainer width="100%" height={200}>
                      <LineChart data={chartData}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                        <XAxis dataKey="time" tick={{ fontSize: 9 }} interval="preserveStartEnd" />
                        <YAxis domain={["auto", "auto"]} tick={{ fontSize: 10 }} />
                        <Tooltip contentStyle={{ fontSize: 12 }} />
                        <Legend wrapperStyle={{ fontSize: 10 }} />
                        <Line type="monotone" dataKey="U_L1" name="L1" stroke="#f59e0b" strokeWidth={1.5} dot={false} />
                        <Line type="monotone" dataKey="U_L2" name="L2" stroke="#3b82f6" strokeWidth={1.5} dot={false} />
                        <Line type="monotone" dataKey="U_L3" name="L3" stroke="#10b981" strokeWidth={1.5} dot={false} />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                  <div className="border border-gray-100 rounded-lg p-4" data-testid="analyse-current-chart">
                    <h3 className="text-xs font-semibold text-gray-700 mb-3 flex items-center gap-1.5">
                      <Activity className="w-3.5 h-3.5 text-green-500" /> Strom (A)
                    </h3>
                    <ResponsiveContainer width="100%" height={200}>
                      <LineChart data={chartData}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                        <XAxis dataKey="time" tick={{ fontSize: 9 }} interval="preserveStartEnd" />
                        <YAxis tick={{ fontSize: 10 }} />
                        <Tooltip contentStyle={{ fontSize: 12 }} />
                        <Legend wrapperStyle={{ fontSize: 10 }} />
                        <Line type="monotone" dataKey="I_L1" name="L1" stroke="#f59e0b" strokeWidth={1.5} dot={false} />
                        <Line type="monotone" dataKey="I_L2" name="L2" stroke="#3b82f6" strokeWidth={1.5} dot={false} />
                        <Line type="monotone" dataKey="I_L3" name="L3" stroke="#10b981" strokeWidth={1.5} dot={false} />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                </div>

                {/* Frequenz, Batterie, Tank, Temperatur */}
                <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-4">
                  <div className="border border-gray-100 rounded-lg p-4" data-testid="analyse-freq-chart">
                    <h3 className="text-xs font-semibold text-gray-700 mb-3">Frequenz (Hz)</h3>
                    <ResponsiveContainer width="100%" height={150}>
                      <LineChart data={chartData}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                        <XAxis dataKey="time" tick={{ fontSize: 8 }} interval="preserveStartEnd" />
                        <YAxis domain={["auto","auto"]} tick={{ fontSize: 9 }} />
                        <Tooltip contentStyle={{ fontSize: 11 }} />
                        <Line type="monotone" dataKey="Freq" name="Hz" stroke="#3B82F6" strokeWidth={1.5} dot={false} />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                  <div className="border border-gray-100 rounded-lg p-4" data-testid="analyse-batt-chart">
                    <h3 className="text-xs font-semibold text-gray-700 mb-3">Batterie (V)</h3>
                    <ResponsiveContainer width="100%" height={150}>
                      <LineChart data={chartData}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                        <XAxis dataKey="time" tick={{ fontSize: 8 }} interval="preserveStartEnd" />
                        <YAxis domain={["auto","auto"]} tick={{ fontSize: 9 }} />
                        <Tooltip contentStyle={{ fontSize: 11 }} />
                        <Line type="monotone" dataKey="Batt" name="V" stroke="#EAB308" strokeWidth={1.5} dot={false} />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                  <div className="border border-gray-100 rounded-lg p-4" data-testid="analyse-fuel-chart">
                    <h3 className="text-xs font-semibold text-gray-700 mb-3">Tankstand (%)</h3>
                    <ResponsiveContainer width="100%" height={150}>
                      <LineChart data={chartData}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                        <XAxis dataKey="time" tick={{ fontSize: 8 }} interval="preserveStartEnd" />
                        <YAxis domain={[0,100]} tick={{ fontSize: 9 }} />
                        <Tooltip contentStyle={{ fontSize: 11 }} />
                        <Line type="monotone" dataKey="Fuel" name="%" stroke="#8B5CF6" strokeWidth={1.5} dot={false} />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                  <div className="border border-gray-100 rounded-lg p-4" data-testid="analyse-cool-chart">
                    <h3 className="text-xs font-semibold text-gray-700 mb-3">Temperatur (C)</h3>
                    <ResponsiveContainer width="100%" height={150}>
                      <LineChart data={chartData}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                        <XAxis dataKey="time" tick={{ fontSize: 8 }} interval="preserveStartEnd" />
                        <YAxis tick={{ fontSize: 9 }} />
                        <Tooltip contentStyle={{ fontSize: 11 }} />
                        <Line type="monotone" dataKey="Cool" name="C" stroke="#EF4444" strokeWidth={1.5} dot={false} />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              </div>
            );
          })()}
        </div>

        {/* Generator Info (Admin) */}
        {isAdmin && (
          <div className="bg-white border border-gray-200 rounded-lg p-4" data-testid="admin-info">
            <h3 className="text-xs text-gray-400 uppercase tracking-wider mb-3">Admin-Info</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-xs">
              <div className="flex justify-between py-1.5 border-b border-gray-100">
                <span className="text-gray-400">Generator-ID</span>
                <span className="font-mono text-gray-600">{generator.id}</span>
              </div>
              <div className="flex justify-between py-1.5 border-b border-gray-100">
                <span className="text-gray-400">API-Key</span>
                <span className="font-mono text-gray-600 truncate ml-4">{generator.api_key}</span>
              </div>
              <div className="flex justify-between py-1.5 border-b border-gray-100">
                <span className="text-gray-400">DSE-Modul</span>
                <span className="font-mono text-gray-600">{generator.dse_module_type}</span>
              </div>
              <div className="flex justify-between py-1.5 border-b border-gray-100">
                <span className="text-gray-400">Erstellt</span>
                <span className="font-mono text-gray-600">{generator.created_at ? new Date(generator.created_at).toLocaleString("de-DE") : "–"}</span>
              </div>
              {generator.notes && (
                <div className="flex justify-between py-1.5 col-span-2">
                  <span className="text-gray-400">Notizen</span>
                  <span className="text-gray-600">{generator.notes}</span>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Einsatzhistorie */}
        <DeploymentHistory generatorId={id} />
      </main>
    </div>
  );
}
