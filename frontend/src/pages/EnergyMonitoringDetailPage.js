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
  MapPin,
  Download,
} from "lucide-react";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../components/ui/select";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { MapContainer, Marker, Popup } from "react-leaflet";
import MapTileLayer from "../components/MapTileLayer";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
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

function toLocalDateStr(date) {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

export default function EnergyMonitoringDetailPage() {
  const { id } = useParams();
  const { user } = useAuth();
  const navigate = useNavigate();
  const [device, setDevice] = useState(null);
  const [telemetry, setTelemetry] = useState([]);
  const [telemetryTotal, setTelemetryTotal] = useState(0);
  const [telemetryDownsampled, setTelemetryDownsampled] = useState(false);
  const [meterData, setMeterData] = useState([]);
  const [location, setLocation] = useState(null);
  const [loading, setLoading] = useState(true);
  const [selectedMeter, setSelectedMeter] = useState("all");
  const [exporting, setExporting] = useState(false);

  // Date range: default = last 24 hours
  const now = new Date();
  const yesterday = new Date(now.getTime() - 24 * 60 * 60 * 1000);
  const [dateFrom, setDateFrom] = useState(toLocalDateStr(yesterday));
  const [dateTo, setDateTo] = useState(toLocalDateStr(now));

  const markerIcon = new L.Icon({
    iconUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
    iconRetinaUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
    shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
    iconSize: [25, 41],
    iconAnchor: [12, 41],
    popupAnchor: [1, -34],
  });

  const fetchDevice = useCallback(async () => {
    try {
      const res = await api.get(`/energy-monitoring/devices/${id}`);
      setDevice(res.data);
      return true;
    } catch (err) {
      if (err.response?.status === 403) {
        toast.error("Kein Zugriff auf dieses Gerät");
        navigate("/energy-monitoring");
        return false;
      }
      if (err.response?.status === 404) {
        toast.error("Gerät nicht gefunden");
        return false;
      }
      toast.error("Fehler beim Laden des Geräts");
      return false;
    }
  }, [id, navigate]);

  const fetchTelemetry = useCallback(async () => {
    try {
      const params = { limit: 5000 };
      if (dateFrom) {
        params.from_time = new Date(dateFrom).toISOString();
      }
      if (dateTo) {
        params.to_time = new Date(dateTo + "T23:59:59").toISOString();
      }
      if (selectedMeter !== "all") {
        params.meter_id = selectedMeter;
      }

      const res = await api.get(`/energy-monitoring/devices/${id}/telemetry`, { params });
      // Backend liefert {items, total, downsampled}. Aelterer Aufrufer-Code
      // bekam ein Array - hier robust beides unterstuetzen.
      const payload = res.data;
      if (Array.isArray(payload)) {
        setTelemetry(payload);
        setTelemetryTotal(payload.length);
        setTelemetryDownsampled(false);
      } else {
        setTelemetry(payload.items || []);
        setTelemetryTotal(payload.total || (payload.items || []).length);
        setTelemetryDownsampled(!!payload.downsampled);
      }
    } catch (err) {
      console.error("Telemetry fetch error:", err);
    }
  }, [id, dateFrom, dateTo, selectedMeter]);

  const fetchLatest = useCallback(async () => {
    try {
      const [latestRes, locRes] = await Promise.all([
        api.get(`/energy-monitoring/devices/${id}/telemetry/latest`),
        api.get(`/energy-monitoring/devices/${id}/location`).catch(() => ({ data: {} })),
      ]);
      setMeterData(latestRes.data);
      if (locRes.data?.gps_lat) setLocation(locRes.data);
    } catch (err) {
      console.error("Latest data fetch error:", err);
    }
  }, [id]);

  useEffect(() => {
    // Wichtig: setLoading(false) sobald das Geraet geladen ist – telemetry/latest
    // duerfen im Hintergrund nachladen. Sonst bleibt "Laden..." bei langsamen
    // Telemetry-Requests (oder Backend-Hangern) ewig stehen, obwohl die
    // Geraetedaten schon da sind. (Reproduziert bei Mitarbeitern mit
    // eingeschraenktem Geraete-Zugriff.)
    let cancelled = false;
    const safetyTimer = setTimeout(() => {
      if (!cancelled) setLoading(false);
    }, 15000); // 15s Safety-Net falls fetchDevice haengt
    fetchDevice().finally(() => {
      if (!cancelled) setLoading(false);
      clearTimeout(safetyTimer);
    });
    fetchTelemetry();
    fetchLatest();
    return () => { cancelled = true; clearTimeout(safetyTimer); };
  }, [fetchDevice, fetchTelemetry, fetchLatest]);

  useEffect(() => {
    fetchTelemetry();
  }, [dateFrom, dateTo, selectedMeter, fetchTelemetry]);

  useEffect(() => {
    const interval = setInterval(() => {
      fetchTelemetry();
      fetchLatest();
    }, 30000);
    return () => clearInterval(interval);
  }, [fetchTelemetry, fetchLatest]);

  // CSV Export
  const handleExportCSV = async () => {
    setExporting(true);
    try {
      const params = { limit: 999999, raw: true };
      if (dateFrom) params.from_time = new Date(dateFrom).toISOString();
      if (dateTo) params.to_time = new Date(dateTo + "T23:59:59").toISOString();
      if (selectedMeter !== "all") params.meter_id = selectedMeter;

      const res = await api.get(`/energy-monitoring/devices/${id}/telemetry`, { params });
      const payload = res.data;
      const data = Array.isArray(payload) ? payload : (payload.items || []);

      if (data.length === 0) {
        toast.error("Keine Daten zum Exportieren");
        return;
      }

      // CSV Header
      const cols = [
        "ts_utc", "meter_ts",
        "I_L1", "I_L2", "I_L3", "I_sum",
        "U_L1", "U_L2", "U_L3",
        "F_Hz",
        "P_sum_kW", "P_L1_kW", "P_L2_kW", "P_L3_kW",
        "Q_sum", "Q_L1", "Q_L2", "Q_L3",
        "PF_L1", "PF_L2", "PF_L3",
        "E_imp_kWh", "E_exp_kWh",
        "gps_lat", "gps_lon", "gps_alt_m",
        "http_ok", "error",
      ];

      let csv = cols.join(";") + "\n";
      for (const row of data) {
        csv += cols.map(c => row[c] ?? "").join(";") + "\n";
      }

      const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `${device?.serial_number || "export"}_${dateFrom}_${dateTo}.csv`;
      link.click();
      URL.revokeObjectURL(url);
      toast.success(`${data.length} Datensätze exportiert`);
    } catch (err) {
      toast.error("Export fehlgeschlagen");
    } finally {
      setExporting(false);
    }
  };

  // Chart data
  const isMultiDay = dateFrom !== dateTo;
  const chartData = telemetry.map((d) => ({
    time: new Date(d.ts_utc).toLocaleString("de-DE", {
      hour: "2-digit", minute: "2-digit",
      ...(isMultiDay ? { day: "2-digit", month: "2-digit" } : {})
    }),
    ts: new Date(d.ts_utc).getTime(),
    P_sum: d.P_sum_kW, P_L1: d.P_L1_kW, P_L2: d.P_L2_kW, P_L3: d.P_L3_kW,
    U_L1: d.U_L1, U_L2: d.U_L2, U_L3: d.U_L3,
    I_sum: d.I_sum, I_L1: d.I_L1, I_L2: d.I_L2, I_L3: d.I_L3,
    F_Hz: d.F_Hz, E_imp: d.E_imp_kWh,
    PF_L1: d.PF_L1, PF_L2: d.PF_L2, PF_L3: d.PF_L3,
  }));

  const downsample = (data, maxPoints = 300) => {
    if (data.length <= maxPoints) return data;
    const step = Math.ceil(data.length / maxPoints);
    return data.filter((_, i) => i % step === 0);
  };
  const displayData = downsample(chartData);
  const latest = telemetry.length > 0 ? telemetry[telemetry.length - 1] : null;

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center" data-testid="detail-loading">
        <div className="animate-pulse text-fuchsia-600">Geräte­daten werden geladen…</div>
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
            <Button variant="ghost" size="sm" onClick={() => navigate("/energy-monitoring")} className="text-gray-600 hover:text-fuchsia-600" data-testid="back-to-list-btn">
              <ArrowLeft className="w-4 h-4 mr-2" />Zurück
            </Button>
            <div className="h-6 w-px bg-gray-200" />
            <div>
              <h1 className="text-lg font-semibold text-gray-900">{device.user_field || device.serial_number}</h1>
              <p className="text-xs text-gray-400 font-mono">{device.serial_number}</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={() => { fetchTelemetry(); fetchLatest(); }} className="text-gray-600 hover:text-fuchsia-600" data-testid="refresh-detail-btn">
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

          {/* Location Map */}
          {location && Number.isFinite(location.gps_lat) && Number.isFinite(location.gps_lon) && (
            <div className="bg-white border border-gray-200 rounded-lg overflow-hidden" data-testid="detail-map">
              <div className="p-3 border-b border-gray-200 flex items-center gap-2">
                <MapPin className="w-4 h-4 text-fuchsia-600" />
                <span className="text-sm font-semibold text-gray-900">Standort</span>
                <span className="text-xs text-gray-400 ml-auto">
                  {location.gps_lat?.toFixed(6)}, {location.gps_lon?.toFixed(6)}
                  {location.gps_alt_m != null && ` | ${Math.round(location.gps_alt_m)} m`}
                </span>
              </div>
              <div style={{ height: "250px" }}>
                <MapContainer center={[location.gps_lat, location.gps_lon]} zoom={15} style={{ height: "100%", width: "100%" }} scrollWheelZoom={true}>
                  <MapTileLayer />
                  <Marker position={[location.gps_lat, location.gps_lon]} icon={markerIcon}>
                    <Popup>
                      <div className="text-xs">
                        <p className="font-semibold">{device.user_field || device.serial_number}</p>
                        <p>Lat: {location.gps_lat?.toFixed(6)}</p>
                        <p>Lon: {location.gps_lon?.toFixed(6)}</p>
                        {location.gps_alt_m != null && <p>Höhe: {Math.round(location.gps_alt_m)} m</p>}
                      </div>
                    </Popup>
                  </Marker>
                </MapContainer>
              </div>
            </div>
          )}

          {/* Time Range + Export Controls */}
          <div className="bg-white border border-gray-200 rounded-lg p-4" data-testid="time-controls">
            <div className="flex flex-wrap items-end gap-4">
              <div className="space-y-1">
                <Label className="text-gray-500 text-xs">Von</Label>
                <Input
                  type="date"
                  value={dateFrom}
                  onChange={(e) => setDateFrom(e.target.value)}
                  className="border-gray-300 text-sm w-[150px]"
                  data-testid="date-from-input"
                />
              </div>
              <div className="space-y-1">
                <Label className="text-gray-500 text-xs">Bis</Label>
                <Input
                  type="date"
                  value={dateTo}
                  onChange={(e) => setDateTo(e.target.value)}
                  className="border-gray-300 text-sm w-[150px]"
                  data-testid="date-to-input"
                />
              </div>

              {device.meters?.length > 1 && (
                <div className="space-y-1">
                  <Label className="text-gray-500 text-xs">Zähler</Label>
                  <Select value={selectedMeter} onValueChange={setSelectedMeter}>
                    <SelectTrigger className="w-[180px] border-gray-300" data-testid="meter-select">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">Alle Zähler</SelectItem>
                      {device.meters.map((m) => (
                        <SelectItem key={m.id} value={m.id}>{m.meter_name}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              )}

              <Button
                variant="outline"
                size="sm"
                onClick={handleExportCSV}
                disabled={exporting || telemetry.length === 0}
                className="text-gray-600 hover:text-fuchsia-600 ml-auto"
                data-testid="export-csv-btn"
              >
                <Download className="w-4 h-4 mr-1.5" />
                {exporting ? "Exportiert..." : "CSV Export"}
              </Button>

              <span className="text-xs text-gray-400 flex items-center gap-1" data-testid="datapoints-count">
                <Clock className="w-3 h-3" />
                {telemetryDownsampled
                  ? `${telemetry.length.toLocaleString("de-DE")} von ${telemetryTotal.toLocaleString("de-DE")} Datenpunkten (gleichmäßig verteilt)`
                  : `${telemetry.length.toLocaleString("de-DE")} Datenpunkte`}
              </span>
            </div>
          </div>

          {/* Power Chart */}
          <div className="bg-white border border-gray-200 rounded-lg p-4" data-testid="power-chart">
            <h3 className="text-sm font-semibold text-gray-900 mb-4 flex items-center gap-2">
              <Zap className="w-4 h-4 text-amber-500" />Leistung (kW)
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
              <div className="h-64 flex items-center justify-center text-gray-400 text-sm">Keine Daten im gewählten Zeitraum</div>
            )}
          </div>

          {/* Voltage & Current Charts */}
          <div className="grid md:grid-cols-2 gap-4">
            <div className="bg-white border border-gray-200 rounded-lg p-4" data-testid="voltage-chart">
              <h3 className="text-sm font-semibold text-gray-900 mb-4 flex items-center gap-2">
                <Gauge className="w-4 h-4 text-blue-500" />Spannung (V)
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
            <div className="bg-white border border-gray-200 rounded-lg p-4" data-testid="current-chart">
              <h3 className="text-sm font-semibold text-gray-900 mb-4 flex items-center gap-2">
                <Activity className="w-4 h-4 text-fuchsia-500" />Strom (A)
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
            <div className="bg-white border border-gray-200 rounded-lg p-4" data-testid="energy-chart">
              <h3 className="text-sm font-semibold text-gray-900 mb-4 flex items-center gap-2">
                <BarChart3 className="w-4 h-4 text-purple-500" />Energie Import (kWh)
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
            <div className="bg-white border border-gray-200 rounded-lg p-4" data-testid="frequency-chart">
              <h3 className="text-sm font-semibold text-gray-900 mb-4 flex items-center gap-2">
                <Thermometer className="w-4 h-4 text-emerald-500" />Frequenz (Hz)
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
                  <Plug className="w-4 h-4 text-gray-500" />Zähler
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
