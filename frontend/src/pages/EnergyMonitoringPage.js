import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
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
  ChevronRight,
  Search,
  Gauge,
  BarChart3,
  Clock,
  Plug,
  AlertCircle,
  MapPin,
} from "lucide-react";
import { Input } from "../components/ui/input";
import { MapContainer, TileLayer, Marker, Popup } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

function DeviceCard({ device, onClick }) {
  const d = device.latest_data;
  const isOnline = device.is_online;
  const lastSeen = d?.ts_utc
    ? new Date(d.ts_utc).toLocaleString("de-DE", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" })
    : null;

  return (
    <button
      onClick={onClick}
      className="bg-white border border-gray-200 rounded-lg p-5 text-left hover:border-fuchsia-400 hover:shadow-md transition-all group w-full"
      data-testid={`energy-device-card-${device.serial_number}`}
    >
      <div className="flex items-start justify-between mb-3">
        <div className="flex-1 min-w-0">
          <h3 className="text-sm font-semibold text-gray-900 truncate">
            {device.user_field || device.serial_number}
          </h3>
          <p className="text-xs text-gray-400 font-mono">{device.serial_number}</p>
        </div>
        <div className="flex items-center gap-1.5 ml-2 flex-shrink-0">
          <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-xs font-medium ${
            isOnline
              ? "bg-emerald-500 text-white"
              : "bg-gray-400 text-white"
          }`}>
            <span className={`w-1.5 h-1.5 rounded-full bg-white/70 ${isOnline ? "animate-pulse" : ""}`} />
            {isOnline ? "Online" : "Offline"}
          </span>
        </div>
      </div>

      <div className="flex items-center gap-1 text-xs text-gray-400 mb-3">
        <Plug className="w-3 h-3" />
        {device.meter_count || 0} Zähler
      </div>

      {d ? (
        <div className="grid grid-cols-3 gap-2 mt-2">
          <div className="bg-gray-50 rounded px-2 py-1.5">
            <div className="flex items-center gap-1 text-[10px] text-gray-400 mb-0.5">
              <Zap className="w-3 h-3" /> Leistung
            </div>
            <p className="text-xs font-mono text-gray-900 truncate">
              {d.P_sum_kW != null ? `${Math.round(d.P_sum_kW * 100) / 100} kW` : "–"}
            </p>
          </div>
          <div className="bg-gray-50 rounded px-2 py-1.5">
            <div className="flex items-center gap-1 text-[10px] text-gray-400 mb-0.5">
              <Gauge className="w-3 h-3" /> Spannung
            </div>
            <p className="text-xs font-mono text-gray-900 truncate">
              {d.U_L1 != null ? `${Math.round(d.U_L1)} V` : "–"}
            </p>
          </div>
          <div className="bg-gray-50 rounded px-2 py-1.5">
            <div className="flex items-center gap-1 text-[10px] text-gray-400 mb-0.5">
              <BarChart3 className="w-3 h-3" /> Energie
            </div>
            <p className="text-xs font-mono text-gray-900 truncate">
              {d.E_imp_kWh != null ? `${Math.round(d.E_imp_kWh * 10) / 10} kWh` : "–"}
            </p>
          </div>
        </div>
      ) : (
        <div className="text-xs text-gray-400 mt-2 flex items-center gap-1">
          <AlertCircle className="w-3 h-3" />
          Keine Daten vorhanden
        </div>
      )}

      <div className="flex items-center justify-between mt-3 pt-3 border-t border-gray-100">
        <span className="text-[10px] text-gray-400 flex items-center gap-1">
          <Clock className="w-3 h-3" />
          {lastSeen || "Keine Daten"}
        </span>
        <ChevronRight className="w-4 h-4 text-gray-300 group-hover:text-fuchsia-600 transition-colors" />
      </div>
    </button>
  );
}

export default function EnergyMonitoringPage() {
  const { isAdmin } = useAuth();
  const navigate = useNavigate();
  const [devices, setDevices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [locations, setLocations] = useState([]);

  // Fix Leaflet default marker icon
  const markerIcon = new L.Icon({
    iconUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
    iconRetinaUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
    shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
    iconSize: [25, 41],
    iconAnchor: [12, 41],
    popupAnchor: [1, -34],
  });

  const fetchData = useCallback(async () => {
    try {
      const [devRes, locRes] = await Promise.all([
        api.get("/energy-monitoring/devices"),
        api.get("/energy-monitoring/locations").catch(() => ({ data: [] })),
      ]);
      setDevices(devRes.data);
      setLocations(locRes.data);
    } catch (err) {
      if (err.response?.status === 403) {
        toast.error("Energy Monitoring nicht freigeschaltet");
        navigate("/hub");
        return;
      }
      toast.error("Fehler beim Laden der Messkoffer");
    } finally {
      setLoading(false);
    }
  }, [navigate]);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 30000);
    return () => clearInterval(interval);
  }, [fetchData]);

  const handleSeedDemo = async () => {
    try {
      const res = await api.post("/energy-monitoring/seed-demo");
      toast.success(res.data.message);
      fetchData();
    } catch (err) {
      toast.error("Fehler beim Erstellen der Demo-Daten");
    }
  };

  const filtered = devices.filter((d) => {
    // Only show devices that have data (= connected/configured)
    if (!d.latest_data) return false;
    if (!search) return true;
    const q = search.toLowerCase();
    return (
      d.serial_number?.toLowerCase().includes(q) ||
      d.user_field?.toLowerCase().includes(q) ||
      d.model?.toLowerCase().includes(q)
    );
  });

  const onlineCount = devices.filter(d => d.is_online).length;
  const totalPower = devices.reduce((sum, d) => sum + (d.latest_data?.P_sum_kW || 0), 0);

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col" data-testid="energy-monitoring-page">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 p-4">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => navigate("/hub")}
              className="text-gray-600 hover:text-fuchsia-600"
              data-testid="back-to-hub-btn"
            >
              <ArrowLeft className="w-4 h-4 mr-2" />
              Zurück
            </Button>
            <div className="h-6 w-px bg-gray-200" />
            <h1 className="text-lg font-semibold text-gray-900">Energy Monitoring</h1>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={fetchData}
              className="text-gray-600 hover:text-fuchsia-600"
              data-testid="refresh-btn"
            >
              <RefreshCw className="w-4 h-4" />
            </Button>
            <Logo size="small" />
          </div>
        </div>
      </header>

      <main className="flex-1 p-4 md:p-6">
        <div className="max-w-7xl mx-auto space-y-6">
          {/* Stats */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="bg-white border border-gray-200 rounded-lg p-4">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-fuchsia-100 flex items-center justify-center">
                  <Activity className="w-5 h-5 text-fuchsia-600" />
                </div>
                <div>
                  <p className="text-2xl font-bold text-gray-900">{devices.length}</p>
                  <p className="text-xs text-gray-500">Messkoffer</p>
                </div>
              </div>
            </div>
            <div className="bg-white border border-gray-200 rounded-lg p-4">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-emerald-100 flex items-center justify-center">
                  <Plug className="w-5 h-5 text-emerald-600" />
                </div>
                <div>
                  <p className="text-2xl font-bold text-gray-900">{onlineCount}</p>
                  <p className="text-xs text-gray-500">Online</p>
                </div>
              </div>
            </div>
            <div className="bg-white border border-gray-200 rounded-lg p-4">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-amber-100 flex items-center justify-center">
                  <Zap className="w-5 h-5 text-amber-600" />
                </div>
                <div>
                  <p className="text-2xl font-bold text-gray-900">{Math.round(totalPower * 100) / 100}</p>
                  <p className="text-xs text-gray-500">kW Gesamt</p>
                </div>
              </div>
            </div>
            <div className="bg-white border border-gray-200 rounded-lg p-4">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-blue-100 flex items-center justify-center">
                  <BarChart3 className="w-5 h-5 text-blue-600" />
                </div>
                <div>
                  <p className="text-2xl font-bold text-gray-900">
                    {Math.round(devices.reduce((s, d) => s + (d.latest_data?.E_imp_kWh || 0), 0) * 10) / 10}
                  </p>
                  <p className="text-xs text-gray-500">kWh Import</p>
                </div>
              </div>
            </div>
          </div>

          {/* Map */}
          {locations.length > 0 && (
            <div className="bg-white border border-gray-200 rounded-lg overflow-hidden" data-testid="energy-map">
              <div className="p-4 border-b border-gray-200 flex items-center gap-2">
                <MapPin className="w-4 h-4 text-fuchsia-600" />
                <h3 className="text-sm font-semibold text-gray-900">Standorte</h3>
              </div>
              <div style={{ height: "350px" }}>
                <MapContainer
                  center={[locations[0].gps_lat, locations[0].gps_lon]}
                  zoom={12}
                  style={{ height: "100%", width: "100%" }}
                  scrollWheelZoom={true}
                >
                  <TileLayer
                    attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
                    url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                  />
                  {locations.map((loc) => (
                    <Marker
                      key={loc.device_id}
                      position={[loc.gps_lat, loc.gps_lon]}
                      icon={markerIcon}
                    >
                      <Popup>
                        <div className="text-xs">
                          <p className="font-semibold text-sm mb-1">{loc.name}</p>
                          <p className="text-gray-500 font-mono">{loc.serial_number}</p>
                          {loc.P_sum_kW != null && (
                            <p className="mt-1">Leistung: <strong>{Math.round(loc.P_sum_kW * 100) / 100} kW</strong></p>
                          )}
                          {loc.gps_alt_m != null && (
                            <p>Höhe: {Math.round(loc.gps_alt_m)} m</p>
                          )}
                          <button
                            onClick={() => navigate(`/energy-monitoring/${loc.device_id}`)}
                            className="mt-2 text-fuchsia-600 hover:underline font-medium"
                          >
                            Details anzeigen
                          </button>
                        </div>
                      </Popup>
                    </Marker>
                  ))}
                </MapContainer>
              </div>
            </div>
          )}

          {/* Search + Actions */}
          <div className="flex flex-col sm:flex-row items-start sm:items-center gap-3">
            <div className="relative flex-1 max-w-xs">
              <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
              <Input
                placeholder="Messkoffer suchen..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pl-8 h-9 border-gray-300 text-sm"
                data-testid="energy-search-input"
              />
            </div>
          </div>

          {/* Device Grid */}
          {loading ? (
            <div className="text-center py-12 text-gray-400">Laden...</div>
          ) : filtered.length === 0 ? (
            <div className="text-center py-12">
              <Activity className="w-12 h-12 text-gray-300 mx-auto mb-3" />
              <p className="text-gray-500">
                {devices.length === 0
                  ? "Keine Messkoffer vorhanden. Erstellen Sie zuerst einen Messkoffer in der Geräteverwaltung."
                  : "Keine Ergebnisse für Ihre Suche."}
              </p>
            </div>
          ) : (
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {filtered.map((device) => (
                <DeviceCard
                  key={device.id}
                  device={device}
                  onClick={() => navigate(`/energy-monitoring/${device.id}`)}
                />
              ))}
            </div>
          )}
        </div>
      </main>

      <footer className="bg-white border-t border-gray-200 p-4 text-center text-sm text-gray-500">
        &copy; {new Date().getFullYear()} Eventenergie Deutschland GmbH & Co. KG
      </footer>
    </div>
  );
}
