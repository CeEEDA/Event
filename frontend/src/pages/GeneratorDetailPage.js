import { useState, useEffect, useCallback } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { Logo } from "../components/Logo";
import api from "../lib/api";
import { toast } from "sonner";
import { Button } from "../components/ui/button";
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
} from "lucide-react";
import {
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Area,
  AreaChart,
} from "recharts";

import { MapContainer, TileLayer, Marker } from "react-leaflet";
import L from "leaflet";

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

function MetricBox({ icon: Icon, label, value, unit, color = "text-gray-900" }) {
  return (
    <div className="bg-white border border-gray-200 rounded-lg p-4">
      <div className="flex items-center gap-1.5 text-xs text-gray-400 mb-2">
        <Icon className="w-3.5 h-3.5" />
        {label}
      </div>
      <p className={`text-xl font-bold font-mono ${color}`}>
        {value !== null && value !== undefined ? value : "–"}
        {unit && value !== null && <span className="text-xs text-gray-400 ml-1">{unit}</span>}
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

function TelemetryChart({ data, dataKeys, title, colors, unit }) {
  if (!data || data.length === 0) return null;

  const chartData = [...data].reverse().map((d) => ({
    ...d,
    time: new Date(d.timestamp).toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" }),
  }));

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-4">
      <h3 className="text-xs text-gray-400 uppercase tracking-wider mb-3 font-medium">{title}</h3>
      <ResponsiveContainer width="100%" height={180}>
        <AreaChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
          <XAxis dataKey="time" tick={{ fill: "#9CA3AF", fontSize: 10 }} interval="preserveStartEnd" />
          <YAxis tick={{ fill: "#9CA3AF", fontSize: 10 }} width={40} unit={unit} />
          <Tooltip
            contentStyle={{ background: "#fff", border: "1px solid #E5E7EB", borderRadius: "8px", fontSize: "12px" }}
            labelStyle={{ color: "#6B7280" }}
          />
          {dataKeys.map((key, i) => (
            <Area
              key={key}
              type="monotone"
              dataKey={key}
              stroke={colors[i]}
              fill={colors[i]}
              fillOpacity={0.1}
              strokeWidth={1.5}
              dot={false}
            />
          ))}
        </AreaChart>
      </ResponsiveContainer>
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

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 30000);
    return () => clearInterval(interval);
  }, [fetchData]);

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

  const sendCommand = async (command, label) => {
    setCmdLoading(command);
    try {
      await api.post(`/mqtt/control/${id}`, { command });
      toast.success(`${label} gesendet`);
      setTimeout(fetchData, 2000);
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Befehl konnte nicht gesendet werden");
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

        {/* Control Buttons - only for Admin + Mitarbeiter */}
        {canControl && (() => {
          const isRunning = generator.status === "running" || generator.latest_telemetry?.engine_running === true || (generator.latest_telemetry?.rpm || 0) > 0;
          const isAuto = generator.status === "online" || generator.status === "standby";
          return (
            <div className="flex items-center gap-5 bg-white border border-gray-200 rounded-lg px-5 py-4" data-testid="generator-controls">
              <span className="text-xs text-gray-400 font-medium mr-1">Steuerung</span>
              {/* Stop Button - DSE Style */}
              <button
                onClick={() => sendCommand("stop", "Generator stoppen")}
                disabled={cmdLoading !== null}
                className="group relative disabled:opacity-50 focus:outline-none"
                data-testid="cmd-stop-btn"
              >
                <div className={`w-14 h-14 rounded-full flex items-center justify-center transition-all duration-150
                  ${!isRunning
                    ? "bg-gradient-to-b from-red-400 via-red-600 to-red-800 shadow-[0_4px_12px_rgba(220,38,38,0.5),inset_0_2px_4px_rgba(255,255,255,0.3)]"
                    : "bg-gradient-to-b from-gray-200 via-gray-300 to-gray-400 shadow-[0_2px_6px_rgba(0,0,0,0.15),inset_0_2px_4px_rgba(255,255,255,0.4)] group-hover:from-red-300 group-hover:via-red-400 group-hover:to-red-600"
                  }
                  ring-[3px] ring-gray-300 ring-offset-1
                  active:shadow-[inset_0_3px_8px_rgba(0,0,0,0.3)]`}
                  style={{boxShadow: !isRunning ? '0 4px 14px rgba(220,38,38,0.45), inset 0 2px 4px rgba(255,255,255,0.25), 0 1px 2px rgba(0,0,0,0.2)' : '0 3px 8px rgba(0,0,0,0.15), inset 0 2px 4px rgba(255,255,255,0.35), 0 1px 2px rgba(0,0,0,0.1)'}}
                >
                  <span className={`text-xl font-bold ${!isRunning ? "text-white drop-shadow-md" : "text-gray-600 group-hover:text-white"}`}>O</span>
                </div>
                <span className="block text-[10px] text-gray-500 text-center mt-1.5 font-medium">{cmdLoading === "stop" ? "..." : "Stop"}</span>
              </button>
              {/* Auto Button - DSE Style */}
              <button
                onClick={() => sendCommand(isRunning ? "auto_off" : "auto_on", isRunning ? "Auto AUS" : "Auto EIN")}
                disabled={cmdLoading !== null}
                className="group relative disabled:opacity-50 focus:outline-none"
                data-testid="cmd-auto-btn"
              >
                <div className={`w-14 h-14 rounded-full flex items-center justify-center transition-all duration-150
                  ${isAuto
                    ? "bg-gradient-to-b from-teal-200 via-teal-300 to-teal-500 shadow-[0_4px_12px_rgba(20,184,166,0.4),inset_0_2px_4px_rgba(255,255,255,0.3)]"
                    : "bg-gradient-to-b from-gray-100 via-gray-200 to-gray-350 shadow-[0_2px_6px_rgba(0,0,0,0.12),inset_0_2px_4px_rgba(255,255,255,0.5)] group-hover:from-gray-200 group-hover:via-gray-300 group-hover:to-gray-400"
                  }
                  ring-[3px] ring-gray-300 ring-offset-1
                  active:shadow-[inset_0_3px_8px_rgba(0,0,0,0.3)]`}
                  style={{boxShadow: isAuto ? '0 4px 14px rgba(20,184,166,0.35), inset 0 2px 4px rgba(255,255,255,0.3), 0 1px 2px rgba(0,0,0,0.15)' : '0 3px 8px rgba(0,0,0,0.1), inset 0 2px 6px rgba(255,255,255,0.5), 0 1px 2px rgba(0,0,0,0.08)'}}
                >
                  <span className={`text-[10px] font-extrabold tracking-tight ${isAuto ? "text-teal-900" : "text-gray-500 group-hover:text-gray-700"}`}>AUTO</span>
                </div>
                <span className="block text-[10px] text-gray-500 text-center mt-1.5 font-medium">{cmdLoading === "auto_on" || cmdLoading === "auto_off" ? "..." : "Auto"}</span>
              </button>
              {/* Start Button - DSE Style */}
              <button
                onClick={() => sendCommand("start", "Generator starten")}
                disabled={cmdLoading !== null}
                className="group relative disabled:opacity-50 focus:outline-none"
                data-testid="cmd-start-btn"
              >
                <div className={`w-14 h-14 rounded-full flex items-center justify-center transition-all duration-150
                  ${isRunning
                    ? "bg-gradient-to-b from-emerald-300 via-emerald-500 to-emerald-700 shadow-[0_4px_12px_rgba(16,185,129,0.5),inset_0_2px_4px_rgba(255,255,255,0.3)]"
                    : "bg-gradient-to-b from-gray-200 via-gray-300 to-gray-400 shadow-[0_2px_6px_rgba(0,0,0,0.15),inset_0_2px_4px_rgba(255,255,255,0.4)] group-hover:from-emerald-300 group-hover:via-emerald-400 group-hover:to-emerald-600"
                  }
                  ring-[3px] ring-gray-300 ring-offset-1
                  active:shadow-[inset_0_3px_8px_rgba(0,0,0,0.3)]`}
                  style={{boxShadow: isRunning ? '0 4px 14px rgba(16,185,129,0.45), inset 0 2px 4px rgba(255,255,255,0.25), 0 1px 2px rgba(0,0,0,0.2)' : '0 3px 8px rgba(0,0,0,0.15), inset 0 2px 4px rgba(255,255,255,0.35), 0 1px 2px rgba(0,0,0,0.1)'}}
                >
                  <span className={`text-xl font-bold ${isRunning ? "text-white drop-shadow-md" : "text-gray-600 group-hover:text-white"}`}>I</span>
                </div>
                <span className="block text-[10px] text-gray-500 text-center mt-1.5 font-medium">{cmdLoading === "start" ? "..." : "Start"}</span>
              </button>
              {/* Generator Switch On/Off - DSE 5510 */}
              <div className="border-l border-gray-200 pl-5 flex items-center gap-4">
                <button
                  onClick={() => sendCommand("gen_switch_on", "Generator zuschalten")}
                  disabled={cmdLoading !== null}
                  className="group relative disabled:opacity-50 focus:outline-none"
                  data-testid="cmd-gen-on-btn"
                >
                  <div className="w-12 h-12 rounded-lg flex items-center justify-center transition-all duration-150
                    bg-gradient-to-b from-blue-100 via-blue-200 to-blue-300 shadow-[0_2px_6px_rgba(0,0,0,0.12),inset_0_2px_4px_rgba(255,255,255,0.5)]
                    group-hover:from-blue-200 group-hover:via-blue-300 group-hover:to-blue-500
                    ring-2 ring-gray-200 ring-offset-1 active:shadow-[inset_0_3px_8px_rgba(0,0,0,0.3)]">
                    <Zap className="w-5 h-5 text-blue-700 group-hover:text-white" />
                  </div>
                  <span className="block text-[10px] text-gray-500 text-center mt-1 font-medium">{cmdLoading === "gen_switch_on" ? "..." : "Gen EIN"}</span>
                </button>
                <button
                  onClick={() => sendCommand("gen_switch_off", "Generator abschalten")}
                  disabled={cmdLoading !== null}
                  className="group relative disabled:opacity-50 focus:outline-none"
                  data-testid="cmd-gen-off-btn"
                >
                  <div className="w-12 h-12 rounded-lg flex items-center justify-center transition-all duration-150
                    bg-gradient-to-b from-orange-100 via-orange-200 to-orange-300 shadow-[0_2px_6px_rgba(0,0,0,0.12),inset_0_2px_4px_rgba(255,255,255,0.5)]
                    group-hover:from-orange-200 group-hover:via-orange-300 group-hover:to-orange-500
                    ring-2 ring-gray-200 ring-offset-1 active:shadow-[inset_0_3px_8px_rgba(0,0,0,0.3)]">
                    <ZapOff className="w-5 h-5 text-orange-700 group-hover:text-white" />
                  </div>
                  <span className="block text-[10px] text-gray-500 text-center mt-1 font-medium">{cmdLoading === "gen_switch_off" ? "..." : "Gen AUS"}</span>
                </button>
              </div>
            </div>
          );
        })()}

        {/* Live Metrics */}
        {t ? (
          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3" data-testid="live-metrics">
            <MetricBox icon={Zap} label="Leistung" value={t.power_kw} unit="kW" color="text-fuchsia-600" />
            <MetricBox icon={Gauge} label="Last" value={t.load_percent} unit="%" color={t.load_percent > 85 ? "text-red-500" : "text-gray-900"} />
            <MetricBox icon={Activity} label="Frequenz" value={t.frequency} unit="Hz" />
            <MetricBox icon={Thermometer} label="Kühlmittel" value={t.coolant_temp} unit="°C" color={t.coolant_temp > 90 ? "text-amber-600" : "text-gray-900"} />
            <MetricBox icon={Fuel} label="Tankstand" value={t.fuel_level} unit="%" color={t.fuel_level < 25 ? "text-red-500" : "text-gray-900"} />
            <MetricBox icon={Battery} label="Batterie" value={t.battery_voltage} unit="V" />
          </div>
        ) : (
          <div className="bg-white border border-gray-200 rounded-lg p-8 text-center text-gray-400">
            Keine aktuellen Telemetrie-Daten verfügbar
          </div>
        )}

        {/* Electrical Details */}
        {t && (
          <div className="grid grid-cols-3 md:grid-cols-6 gap-3" data-testid="electrical-details">
            <MetricBox icon={Zap} label="U L1" value={t.voltage_l1} unit="V" />
            <MetricBox icon={Zap} label="U L2" value={t.voltage_l2} unit="V" />
            <MetricBox icon={Zap} label="U L3" value={t.voltage_l3} unit="V" />
            <MetricBox icon={Activity} label="I L1" value={t.current_l1} unit="A" />
            <MetricBox icon={Activity} label="I L2" value={t.current_l2} unit="A" />
            <MetricBox icon={Activity} label="I L3" value={t.current_l3} unit="A" />
          </div>
        )}

        {/* Engine Details */}
        {t && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3" data-testid="engine-details">
            <MetricBox icon={RotateCcw} label="Drehzahl" value={t.rpm} unit="U/min" />
            <MetricBox icon={Gauge} label="Öldruck" value={t.oil_pressure} unit="bar" />
            <MetricBox icon={Clock} label="Betriebsstunden" value={t.hours_run} unit="h" />
            <MetricBox icon={Activity} label="cos φ" value={t.power_factor} unit="" />
          </div>
        )}

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

        {/* Time Range Selector */}
        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-500">Zeitraum:</span>
          {[6, 12, 24, 48].map((h) => (
            <button
              key={h}
              onClick={() => setHours(h)}
              className={`px-3 py-1.5 rounded text-xs font-medium transition-colors ${
                hours === h ? "bg-fuchsia-600 text-white" : "bg-white text-gray-500 border border-gray-200 hover:text-gray-700"
              }`}
              data-testid={`hours-${h}`}
            >
              {h}h
            </button>
          ))}
        </div>

        {/* Charts */}
        {telemetry.length > 0 && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4" data-testid="telemetry-charts">
            <TelemetryChart data={telemetry} dataKeys={["power_kw"]} title="Leistung (kW)" colors={["#A855F7"]} unit=" kW" />
            <TelemetryChart data={telemetry} dataKeys={["load_percent"]} title="Auslastung (%)" colors={["#10B981"]} unit="%" />
            <TelemetryChart data={telemetry} dataKeys={["voltage_l1", "voltage_l2", "voltage_l3"]} title="Spannung (V)" colors={["#A855F7", "#D946EF", "#10B981"]} unit=" V" />
            <TelemetryChart data={telemetry} dataKeys={["coolant_temp"]} title="Kühlmitteltemperatur (°C)" colors={["#EF4444"]} unit="°C" />
            <TelemetryChart data={telemetry} dataKeys={["frequency"]} title="Frequenz (Hz)" colors={["#3B82F6"]} unit=" Hz" />
            <TelemetryChart data={telemetry} dataKeys={["fuel_level"]} title="Tankstand (%)" colors={["#8B5CF6"]} unit="%" />
          </div>
        )}

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
