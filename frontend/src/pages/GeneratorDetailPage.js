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

const statusConfig = {
  running: { label: "Läuft", bg: "bg-emerald-50", border: "border-emerald-200", text: "text-emerald-700", dot: "bg-emerald-500" },
  standby: { label: "Standby", bg: "bg-sky-50", border: "border-sky-200", text: "text-sky-700", dot: "bg-sky-500" },
  warning: { label: "Warnung", bg: "bg-amber-50", border: "border-amber-200", text: "text-amber-700", dot: "bg-amber-500" },
  alarm: { label: "Alarm", bg: "bg-red-50", border: "border-red-200", text: "text-red-700", dot: "bg-red-500" },
  offline: { label: "Offline", bg: "bg-gray-50", border: "border-gray-200", text: "text-gray-500", dot: "bg-gray-400" },
};

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
  const { isAdmin } = useAuth();
  const [generator, setGenerator] = useState(null);
  const [telemetry, setTelemetry] = useState([]);
  const [alarms, setAlarms] = useState([]);
  const [loading, setLoading] = useState(true);
  const [hours, setHours] = useState(24);

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
              <h1 className="text-sm font-semibold text-gray-900 tracking-tight">{generator.name}</h1>
              <p className="text-xs text-gray-400 font-mono">{generator.serial_number}</p>
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
                <span className="font-mono text-gray-600">{new Date(generator.created_at).toLocaleString("de-DE")}</span>
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
      </main>
    </div>
  );
}
