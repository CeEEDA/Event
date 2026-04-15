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

import { MapContainer, TileLayer, Marker } from "react-leaflet";
import L from "leaflet";
import EventLog from "../components/EventLog";

const statusConfig = {
  running: { label: "Läuft", bg: "bg-emerald-50", border: "border-emerald-200", text: "text-emerald-700", dot: "bg-emerald-500" },
  standby: { label: "Standby", bg: "bg-sky-50", border: "border-sky-200", text: "text-sky-700", dot: "bg-sky-500" },
  online: { label: "Online", bg: "bg-teal-50", border: "border-teal-200", text: "text-teal-700", dot: "bg-teal-500" },
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
              {deployments.map((d) => (
                <tr
                  key={d.id}
                  className="border-b border-gray-100 hover:bg-fuchsia-50/50 cursor-pointer"
                  onClick={() => d.order_pk && navigate(`/orders/${d.order_pk}`)}
                  data-testid={`deployment-${d.id}`}
                >
                  <td className="px-4 py-2.5 font-medium text-fuchsia-700">
                    {d.generator_name || `Auftrag #${d.order_pk}`}
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
              ))}
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

  // Analyse-Bereich
  const today = new Date().toISOString().split("T")[0];
  const weekAgo = new Date(Date.now() - 7 * 86400000).toISOString().split("T")[0];
  const [analyseDateFrom, setAnalyseDateFrom] = useState(weekAgo);
  const [analyseDateTo, setAnalyseDateTo] = useState(today);
  const [analyseData, setAnalyseData] = useState([]);
  const [analyseLoading, setAnalyseLoading] = useState(false);
  const [exporting, setExporting] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      const [genRes, telRes, alarmRes] = await Promise.all([
        api.get(`/generators/${id}`),
        api.get(`/generators/${id}/telemetry?hours=${hours}&limit=200`),
        api.get(`/generators/${id}/alarms?active_only=true`),
      ]);
      setGenerator(genRes.data);
      setTelemetry(telRes.data);
      setAlarms(alarmRes.data);
    } catch (err) {
      toast.error("Fehler beim Laden");
      navigate("/generators");
    } finally {
      setLoading(false);
    }
  }, [id, hours, navigate]);

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

  const handleExportCSV = () => {
    if (analyseData.length === 0) return;
    setExporting(true);
    try {
      const fields = ["timestamp", "voltage_l1", "voltage_l2", "voltage_l3", "current_l1", "current_l2", "current_l3",
        "power_total_w", "power_kw", "energy_kwh", "frequency", "battery_voltage", "coolant_temp", "oil_pressure",
        "fuel_level", "hours_run", "rpm", "dse_mode"];
      const header = fields.join(";");
      const rows = analyseData.map(r => fields.map(f => {
        const v = r[f];
        return v !== null && v !== undefined ? String(v) : "";
      }).join(";"));
      const csv = "\uFEFF" + [header, ...rows].join("\n");
      const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      const name = generator?.name || "generator";
      a.href = url;
      a.download = `${name}_${analyseDateFrom}_${analyseDateTo}.csv`;
      a.click();
      URL.revokeObjectURL(url);
      toast.success(`${analyseData.length} Datenpunkte exportiert`);
    } catch {
      toast.error("Export fehlgeschlagen");
    } finally {
      setExporting(false);
    }
  };

  // Normal: 20 Min Refresh. Nach Tastendruck: 2 Min einmalig, dann zurueck auf 20 Min.
  const [refreshMs, setRefreshMs] = useState(1200000);

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

  const sendCommand = async (command, label) => {
    setCmdLoading(command);
    try {
      await api.post(`/mqtt/control/${id}`, { command });
      toast.success(`${label} gesendet`);
      setPendingCmd(command); // Start blinking
      // DSE 5510 Pi: Command ausfuehren + Readback dauert ~5-7s
      // Schnelles Polling: 5s, 10s, 20s nach Befehl
      setTimeout(fetchData, 5000);
      setTimeout(fetchData, 10000);
      setTimeout(fetchData, 20000);
      // 2 Min schneller Refresh, dann zurueck auf 20 Min
      setRefreshMs(30000);
      setTimeout(() => {
        setRefreshMs(1200000);
        setPendingCmd(null); // Stop blinking after 2 min
        fetchData();
      }, 120000);
    } catch (err) {
      const detail = err?.response?.data?.detail || "";
      if (detail.includes("MQTT client nicht verbunden")) {
        toast.error("MQTT-Broker nicht verbunden. Bitte Verbindung pruefen.");
      } else if (detail.includes("Kein MQTT-Gateway")) {
        toast.error("Bitte zuerst die DSE-Modul USB ID im Geraet hinterlegen.");
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
          const isFullControl = !isL401; // Stromerzeuger (8610, 5510 etc.) = alle Buttons
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
            <MetricBox icon={Gauge} label="Last" value={t.load_percent} unit="%" color={sanitizeValue(t.load_percent, "load_percent") > 85 ? "text-red-500" : "text-gray-900"} field="load_percent" />
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
                <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" attribution='&copy; OSM' />
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
            const chartData = analyseData.map(r => ({
              time: new Date(r.timestamp).toLocaleString("de-DE", { day:"2-digit", month:"2-digit", hour:"2-digit", minute:"2-digit" }),
              P_kW: sanitizeValue(r.power_kw, "power_kw") || (r.power_total_w ? Math.round(sanitizeValue(r.power_total_w) / 100) / 10 : 0) || 0,
              kWh: r.energy_kwh || 0,
              U_L1: sanitizeValue(r.voltage_l1, "voltage_l1") || 0,
              U_L2: sanitizeValue(r.voltage_l2, "voltage_l2") || 0,
              U_L3: sanitizeValue(r.voltage_l3, "voltage_l3") || 0,
              I_L1: sanitizeValue(r.current_l1, "current_l1") || 0,
              I_L2: sanitizeValue(r.current_l2, "current_l2") || 0,
              I_L3: sanitizeValue(r.current_l3, "current_l3") || 0,
              Freq: sanitizeValue(r.frequency, "frequency") || 0,
              Batt: sanitizeValue(r.battery_voltage, "battery_voltage") || 0,
              Fuel: sanitizeValue(r.fuel_level, "fuel_level") || sanitizeValue(r.fuel_level_pct, "fuel_level") || 0,
              Cool: sanitizeValue(r.coolant_temp, "coolant_temp") || sanitizeValue(r.coolant_temp_c, "coolant_temp") || 0,
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
