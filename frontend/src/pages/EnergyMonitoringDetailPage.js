import { useState, useEffect, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { Logo } from "../components/Logo";
import api from "../lib/api";
import { toast } from "sonner";
import { Button } from "../components/ui/button";
import {
  ArrowLeft,
  Zap,
  Activity,
  RefreshCw,
  Gauge,
  BarChart3,
  Clock,
  Plug,
  Thermometer,
  TrendingUp,
} from "lucide-react";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../components/ui/select";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  AreaChart,
  Area,
} from "recharts";

function MetricCard({ icon: Icon, label, value, unit, color }) {
  return (
    <div className="bg-white border border-gray-200 rounded-lg p-4" data-testid={`metric-${label.toLowerCase().replace(/\s/g, '-')}`}>
      <div className="flex items-center gap-2 mb-2">
        <div className={`w-8 h-8 rounded-lg ${color} flex items-center justify-center`}>
          <Icon className="w-4 h-4 text-white" />
        </div>
        <span className="text-xs text-gray-500">{label}</span>
      </div>
      <p className="text-xl font-bold text-gray-900 font-mono">
        {value != null ? value : "–"}
        {value != null && unit && <span className="text-sm font-normal text-gray-400 ml-1">{unit}</span>}
      </p>
    </div>
  );
}

const TIME_RANGES = {
  "1h": { label: "1 Stunde", minutes: 60 },
  "6h": { label: "6 Stunden", minutes: 360 },
  "24h": { label: "24 Stunden", minutes: 1440 },
  "7d": { label: "7 Tage", minutes: 10080 },
};

export default function EnergyMonitoringDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [device, setDevice] = useState(null);
  const [telemetry, setTelemetry] = useState([]);
  const [meterData, setMeterData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [timeRange, setTimeRange] = useState("24h");
  const [selectedMeter, setSelectedMeter] = useState("all");

  const fetchDevice = useCallback(async () => {
    try {
      const res = await api.get(`/energy-monitoring/devices/${id}`);
      setDevice(res.data);
    } catch (err) {
      if (err.response?.status === 403) {
        toast.error("Kein Zugriff auf dieses Gerät");
        navigate("/energy-monitoring");
        return;
      }
      toast.error("Fehler beim Laden");
    }
  }, [id, navigate]);

  const fetchTelemetry = useCallback(async () => {
    try {
      const range = TIME_RANGES[timeRange];
      const from = new Date(Date.now() - range.minutes * 60 * 1000).toISOString();

      const params = { from_time: from, limit: 2000 };
      if (selectedMeter !== "all") {
        params.meter_id = selectedMeter;
      }

      const res = await api.get(`/energy-monitoring/devices/${id}/telemetry`, { params });
      setTelemetry(res.data);
    } catch (err) {
      console.error("Telemetry fetch error:", err);
    }
  }, [id, timeRange, selectedMeter]);

  const fetchLatest = useCallback(async () => {
    try {
      const res = await api.get(`/energy-monitoring/devices/${id}/telemetry/latest`);
      setMeterData(res.data);
    } catch (err) {
      console.error("Latest data fetch error:", err);
    }
  }, [id]);

  useEffect(() => {
    Promise.all([fetchDevice(), fetchTelemetry(), fetchLatest()]).finally(() => setLoading(false));
  }, [fetchDevice, fetchTelemetry, fetchLatest]);

  useEffect(() => {
    fetchTelemetry();
  }, [timeRange, selectedMeter, fetchTelemetry]);

  useEffect(() => {
    const interval = setInterval(() => {
      fetchTelemetry();
      fetchLatest();
    }, 30000);
    return () => clearInterval(interval);
  }, [fetchTelemetry, fetchLatest]);

  // Prepare chart data
  const chartData = telemetry.map((d) => ({
    time: new Date(d.ts_utc).toLocaleString("de-DE", {
      hour: "2-digit", minute: "2-digit",
      ...(TIME_RANGES[timeRange].minutes > 1440 ? { day: "2-digit", month: "2-digit" } : {})
    }),
    ts: new Date(d.ts_utc).getTime(),
    P_sum: d.P_sum_kW,
    P_L1: d.P_L1_kW,
    P_L2: d.P_L2_kW,
    P_L3: d.P_L3_kW,
    U_L1: d.U_L1,
    U_L2: d.U_L2,
    U_L3: d.U_L3,
    I_sum: d.I_sum,
    I_L1: d.I_L1,
    I_L2: d.I_L2,
    I_L3: d.I_L3,
    F_Hz: d.F_Hz,
    E_imp: d.E_imp_kWh,
    PF_L1: d.PF_L1,
    PF_L2: d.PF_L2,
    PF_L3: d.PF_L3,
  }));

  // Downsample for charts if too many points
  const downsample = (data, maxPoints = 300) => {
    if (data.length <= maxPoints) return data;
    const step = Math.ceil(data.length / maxPoints);
    return data.filter((_, i) => i % step === 0);
  };
  const displayData = downsample(chartData);

  // Latest values
  const latest = telemetry.length > 0 ? telemetry[telemetry.length - 1] : null;

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="animate-pulse text-fuchsia-600">Laden...</div>
      </div>
    );
  }

  if (!device) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <p className="text-gray-500">Gerät nicht gefunden</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col" data-testid="energy-detail-page">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 p-4">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => navigate("/energy-monitoring")}
              className="text-gray-600 hover:text-fuchsia-600"
              data-testid="back-to-list-btn"
            >
              <ArrowLeft className="w-4 h-4 mr-2" />
              Zurück
            </Button>
            <div className="h-6 w-px bg-gray-200" />
            <div>
              <h1 className="text-lg font-semibold text-gray-900">
                {device.user_field || device.serial_number}
              </h1>
              <p className="text-xs text-gray-400 font-mono">{device.serial_number}</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => { fetchTelemetry(); fetchLatest(); }}
              className="text-gray-600 hover:text-fuchsia-600"
              data-testid="refresh-detail-btn"
            >
              <RefreshCw className="w-4 h-4" />
            </Button>
            <Logo size="small" />
          </div>
        </div>
      </header>

      <main className="flex-1 p-4 md:p-6">
        <div className="max-w-7xl mx-auto space-y-6">
          {/* Current Values */}
          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
            <MetricCard icon={Zap} label="Leistung" value={latest ? Math.round(latest.P_sum_kW * 100) / 100 : null} unit="kW" color="bg-amber-500" />
            <MetricCard icon={Gauge} label="Spannung L1" value={latest ? Math.round(latest.U_L1 * 10) / 10 : null} unit="V" color="bg-blue-500" />
            <MetricCard icon={Activity} label="Strom" value={latest ? Math.round(latest.I_sum * 100) / 100 : null} unit="A" color="bg-fuchsia-500" />
            <MetricCard icon={Thermometer} label="Frequenz" value={latest ? Math.round(latest.F_Hz * 10) / 10 : null} unit="Hz" color="bg-emerald-500" />
            <MetricCard icon={BarChart3} label="Energie Import" value={latest ? Math.round(latest.E_imp_kWh * 10) / 10 : null} unit="kWh" color="bg-purple-500" />
            <MetricCard icon={TrendingUp} label="Cos Phi L1" value={latest ? Math.round(latest.PF_L1 * 100) / 100 : null} unit="" color="bg-teal-500" />
          </div>

          {/* Controls */}
          <div className="flex flex-wrap items-center gap-3">
            <Select value={timeRange} onValueChange={setTimeRange}>
              <SelectTrigger className="w-[150px] border-gray-300" data-testid="time-range-select">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {Object.entries(TIME_RANGES).map(([key, val]) => (
                  <SelectItem key={key} value={key}>{val.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>

            {device.meters?.length > 1 && (
              <Select value={selectedMeter} onValueChange={setSelectedMeter}>
                <SelectTrigger className="w-[200px] border-gray-300" data-testid="meter-select">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">Alle Zähler</SelectItem>
                  {device.meters.map((m) => (
                    <SelectItem key={m.id} value={m.id}>{m.meter_name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}

            <span className="text-xs text-gray-400 ml-auto flex items-center gap-1">
              <Clock className="w-3 h-3" />
              {telemetry.length} Datenpunkte
            </span>
          </div>

          {/* Power Chart */}
          <div className="bg-white border border-gray-200 rounded-lg p-4" data-testid="power-chart">
            <h3 className="text-sm font-semibold text-gray-900 mb-4 flex items-center gap-2">
              <Zap className="w-4 h-4 text-amber-500" />
              Leistung (kW)
            </h3>
            {displayData.length > 0 ? (
              <ResponsiveContainer width="100%" height={280}>
                <AreaChart data={displayData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                  <XAxis dataKey="time" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
                  <YAxis tick={{ fontSize: 10 }} />
                  <Tooltip contentStyle={{ fontSize: 12 }} />
                  <Legend wrapperStyle={{ fontSize: 11 }} />
                  <Area type="monotone" dataKey="P_L1" name="L1" stroke="#f59e0b" fill="#f59e0b" fillOpacity={0.15} strokeWidth={1.5} dot={false} />
                  <Area type="monotone" dataKey="P_L2" name="L2" stroke="#3b82f6" fill="#3b82f6" fillOpacity={0.15} strokeWidth={1.5} dot={false} />
                  <Area type="monotone" dataKey="P_L3" name="L3" stroke="#10b981" fill="#10b981" fillOpacity={0.15} strokeWidth={1.5} dot={false} />
                </AreaChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-64 flex items-center justify-center text-gray-400 text-sm">
                Keine Daten im gewählten Zeitraum
              </div>
            )}
          </div>

          {/* Voltage & Current Charts side by side */}
          <div className="grid md:grid-cols-2 gap-4">
            {/* Voltage */}
            <div className="bg-white border border-gray-200 rounded-lg p-4" data-testid="voltage-chart">
              <h3 className="text-sm font-semibold text-gray-900 mb-4 flex items-center gap-2">
                <Gauge className="w-4 h-4 text-blue-500" />
                Spannung (V)
              </h3>
              {displayData.length > 0 ? (
                <ResponsiveContainer width="100%" height={220}>
                  <LineChart data={displayData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                    <XAxis dataKey="time" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
                    <YAxis domain={["auto", "auto"]} tick={{ fontSize: 10 }} />
                    <Tooltip contentStyle={{ fontSize: 12 }} />
                    <Legend wrapperStyle={{ fontSize: 11 }} />
                    <Line type="monotone" dataKey="U_L1" name="L1" stroke="#f59e0b" strokeWidth={1.5} dot={false} />
                    <Line type="monotone" dataKey="U_L2" name="L2" stroke="#3b82f6" strokeWidth={1.5} dot={false} />
                    <Line type="monotone" dataKey="U_L3" name="L3" stroke="#10b981" strokeWidth={1.5} dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              ) : (
                <div className="h-52 flex items-center justify-center text-gray-400 text-sm">Keine Daten</div>
              )}
            </div>

            {/* Current */}
            <div className="bg-white border border-gray-200 rounded-lg p-4" data-testid="current-chart">
              <h3 className="text-sm font-semibold text-gray-900 mb-4 flex items-center gap-2">
                <Activity className="w-4 h-4 text-fuchsia-500" />
                Strom (A)
              </h3>
              {displayData.length > 0 ? (
                <ResponsiveContainer width="100%" height={220}>
                  <LineChart data={displayData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                    <XAxis dataKey="time" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
                    <YAxis tick={{ fontSize: 10 }} />
                    <Tooltip contentStyle={{ fontSize: 12 }} />
                    <Legend wrapperStyle={{ fontSize: 11 }} />
                    <Line type="monotone" dataKey="I_L1" name="L1" stroke="#f59e0b" strokeWidth={1.5} dot={false} />
                    <Line type="monotone" dataKey="I_L2" name="L2" stroke="#3b82f6" strokeWidth={1.5} dot={false} />
                    <Line type="monotone" dataKey="I_L3" name="L3" stroke="#10b981" strokeWidth={1.5} dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              ) : (
                <div className="h-52 flex items-center justify-center text-gray-400 text-sm">Keine Daten</div>
              )}
            </div>
          </div>

          {/* Energy & Frequency Charts */}
          <div className="grid md:grid-cols-2 gap-4">
            {/* Energy Import */}
            <div className="bg-white border border-gray-200 rounded-lg p-4" data-testid="energy-chart">
              <h3 className="text-sm font-semibold text-gray-900 mb-4 flex items-center gap-2">
                <BarChart3 className="w-4 h-4 text-purple-500" />
                Energie Import (kWh)
              </h3>
              {displayData.length > 0 ? (
                <ResponsiveContainer width="100%" height={220}>
                  <AreaChart data={displayData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                    <XAxis dataKey="time" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
                    <YAxis tick={{ fontSize: 10 }} />
                    <Tooltip contentStyle={{ fontSize: 12 }} />
                    <Area type="monotone" dataKey="E_imp" name="E Import" stroke="#8b5cf6" fill="#8b5cf6" fillOpacity={0.2} strokeWidth={1.5} dot={false} />
                  </AreaChart>
                </ResponsiveContainer>
              ) : (
                <div className="h-52 flex items-center justify-center text-gray-400 text-sm">Keine Daten</div>
              )}
            </div>

            {/* Frequency */}
            <div className="bg-white border border-gray-200 rounded-lg p-4" data-testid="frequency-chart">
              <h3 className="text-sm font-semibold text-gray-900 mb-4 flex items-center gap-2">
                <Thermometer className="w-4 h-4 text-emerald-500" />
                Frequenz (Hz)
              </h3>
              {displayData.length > 0 ? (
                <ResponsiveContainer width="100%" height={220}>
                  <LineChart data={displayData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                    <XAxis dataKey="time" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
                    <YAxis domain={["auto", "auto"]} tick={{ fontSize: 10 }} />
                    <Tooltip contentStyle={{ fontSize: 12 }} />
                    <Line type="monotone" dataKey="F_Hz" name="Frequenz" stroke="#10b981" strokeWidth={1.5} dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              ) : (
                <div className="h-52 flex items-center justify-center text-gray-400 text-sm">Keine Daten</div>
              )}
            </div>
          </div>

          {/* Meters Table */}
          {device.meters?.length > 0 && (
            <div className="bg-white border border-gray-200 rounded-lg overflow-hidden" data-testid="meters-table">
              <div className="p-4 border-b border-gray-200">
                <h3 className="text-sm font-semibold text-gray-900 flex items-center gap-2">
                  <Plug className="w-4 h-4 text-gray-500" />
                  Zähler
                </h3>
              </div>
              <table className="w-full text-sm">
                <thead className="bg-gray-50 text-xs text-gray-500 uppercase">
                  <tr>
                    <th className="px-4 py-2 text-left">Name</th>
                    <th className="px-4 py-2 text-left">IP</th>
                    <th className="px-4 py-2 text-left hidden sm:table-cell">Beschreibung</th>
                    <th className="px-4 py-2 text-right">Letzte Leistung</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {meterData.map((md) => (
                    <tr key={md.meter.id} className="hover:bg-gray-50">
                      <td className="px-4 py-2 font-medium text-gray-900">{md.meter.meter_name}</td>
                      <td className="px-4 py-2 text-gray-500 font-mono text-xs">{md.meter.meter_ip}</td>
                      <td className="px-4 py-2 text-gray-400 hidden sm:table-cell">{md.meter.description || "–"}</td>
                      <td className="px-4 py-2 text-right font-mono text-gray-900">
                        {md.latest?.P_sum_kW != null ? `${Math.round(md.latest.P_sum_kW * 100) / 100} kW` : "–"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
