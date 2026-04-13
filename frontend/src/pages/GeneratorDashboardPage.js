import { useState, useEffect, useCallback, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { Logo } from "../components/Logo";
import api from "../lib/api";
import { toast } from "sonner";
import { Button } from "../components/ui/button";
import {
  ArrowLeft,
  Activity,
  Zap,
  AlertTriangle,
  WifiOff,
  Power,
  RefreshCw,
  Plus,
  MapPin,
  Gauge,
  Thermometer,
  Fuel,
  Clock,
  ChevronRight,
  Search,
  Map,
  LayoutGrid,
  Wrench,
  Play,
  Square,
  ToggleLeft,
} from "lucide-react";
import { MapContainer, TileLayer, Marker, Popup, useMap } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

const statusConfig = {
  running: { label: "Läuft", color: "bg-emerald-500", textColor: "text-emerald-600", filterKey: "running" },
  standby: { label: "Standby", color: "bg-sky-500", textColor: "text-sky-600", filterKey: "standby" },
  online: { label: "Online", color: "bg-teal-500", textColor: "text-teal-600", filterKey: "online" },
  warning: { label: "Warnung", color: "bg-amber-500", textColor: "text-amber-600", filterKey: "warning" },
  alarm: { label: "Alarm", color: "bg-red-500", textColor: "text-red-600", filterKey: "alarm" },
  offline: { label: "Offline", color: "bg-gray-400", textColor: "text-gray-500", filterKey: "offline" },
};

// Leaflet marker icons by status
const markerIcons = {};
function getMarkerIcon(status) {
  if (markerIcons[status]) return markerIcons[status];
  const colors = {
    running: "#10B981",
    standby: "#0EA5E9",
    online: "#14B8A6",
    warning: "#F59E0B",
    alarm: "#EF4444",
    offline: "#9CA3AF",
  };
  const color = colors[status] || colors.offline;
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="28" height="36" viewBox="0 0 28 36">
    <path d="M14 0C6.3 0 0 6.3 0 14c0 10.5 14 22 14 22s14-11.5 14-22C28 6.3 21.7 0 14 0z" fill="${color}"/>
    <circle cx="14" cy="14" r="6" fill="white"/>
  </svg>`;
  markerIcons[status] = L.divIcon({
    html: svg,
    iconSize: [28, 36],
    iconAnchor: [14, 36],
    popupAnchor: [0, -36],
    className: "",
  });
  return markerIcons[status];
}

function StatCard({ icon: Icon, label, value, color, active, onClick }) {
  return (
    <button
      onClick={onClick}
      className={`bg-white border rounded-lg p-4 flex items-center gap-3 transition-all text-left w-full ${
        active ? "border-fuchsia-500 ring-2 ring-fuchsia-200" : "border-gray-200 hover:border-fuchsia-300"
      }`}
      data-testid={`stat-${label.toLowerCase()}`}
    >
      <div className={`w-10 h-10 rounded-lg ${color} flex items-center justify-center`}>
        <Icon className="w-5 h-5 text-white" />
      </div>
      <div>
        <p className="text-2xl font-bold text-gray-900 font-mono">{value}</p>
        <p className="text-xs text-gray-500 uppercase tracking-wider">{label}</p>
      </div>
    </button>
  );
}

function GeneratorCard({ generator, onClick, canControl }) {
  const status = statusConfig[generator.status] || statusConfig.offline;
  const t = generator.latest_telemetry;
  const lastSeen = generator.last_seen
    ? new Date(generator.last_seen).toLocaleString("de-DE", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" })
    : "–";
  const hasMaintWarning = generator.maintenance_warning;
  const [cmdLoading, setCmdLoading] = useState(null);

  const sendCmd = async (e, command, label) => {
    e.stopPropagation();
    setCmdLoading(command);
    try {
      await api.post(`/mqtt/control/${generator.id}`, { command });
      toast.success(`${label} gesendet`);
    } catch {
      toast.error("Befehl fehlgeschlagen");
    } finally {
      setCmdLoading(null);
    }
  };

  return (
    <div
      onClick={onClick}
      className="bg-white border border-gray-200 rounded-lg p-5 text-left hover:border-fuchsia-400 hover:shadow-md transition-all group w-full cursor-pointer"
      data-testid={`generator-card-${generator.serial_number}`}
    >
      <div className="flex items-start justify-between mb-3">
        <div className="flex-1 min-w-0">
          <h3 className="text-sm font-bold text-gray-900 truncate">{generator.serial_number || generator.name}</h3>
          <p className="text-xs text-gray-400">{generator.model}</p>
        </div>
        <div className="flex items-center gap-1.5 ml-2 flex-shrink-0">
          {hasMaintWarning && (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-amber-100 text-amber-700" title={generator.maintenance_warning_reason || "Wartung fällig"} data-testid={`maint-warning-${generator.serial_number}`}>
              <Wrench className="w-3 h-3" />
              {generator.maintenance_warning_reason || "Wartung"}
            </span>
          )}
          <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-xs font-medium ${status.color} text-white`}>
            <span className="w-1.5 h-1.5 rounded-full bg-white/70 animate-pulse" />
            {status.label}
          </span>
        </div>
      </div>

      {generator.location_name && (
        <div className="flex items-center gap-1 text-xs text-gray-400 mb-3">
          <MapPin className="w-3 h-3" />
          {generator.location_name}
        </div>
      )}

      {t && generator.status !== "offline" ? (
        <div className="grid grid-cols-4 gap-2 mt-2">
          <div className="bg-gray-50 rounded px-2 py-1.5">
            <div className="flex items-center gap-1 text-[10px] text-gray-400 mb-0.5"><Zap className="w-3 h-3" /> Leistung</div>
            <p className="text-xs font-mono text-gray-900 truncate">{t.power_kw ? `${Math.round(t.power_kw * 10) / 10} kW` : "–"}</p>
          </div>
          <div className="bg-gray-50 rounded px-2 py-1.5">
            <div className="flex items-center gap-1 text-[10px] text-gray-400 mb-0.5"><Gauge className="w-3 h-3" /> Last</div>
            <p className="text-xs font-mono text-gray-900 truncate">{t.load_percent ? `${Math.round(t.load_percent)}%` : "–"}</p>
          </div>
          <div className="bg-gray-50 rounded px-2 py-1.5">
            <div className="flex items-center gap-1 text-[10px] text-gray-400 mb-0.5"><Thermometer className="w-3 h-3" /> Temp</div>
            <p className="text-xs font-mono text-gray-900 truncate">{t.coolant_temp != null ? `${Math.round(t.coolant_temp * 10) / 10}°C` : "–"}</p>
          </div>
          <div className="bg-gray-50 rounded px-2 py-1.5">
            <div className="flex items-center gap-1 text-[10px] text-gray-400 mb-0.5"><Fuel className="w-3 h-3" /> Tank</div>
            <p className="text-xs font-mono text-gray-900 truncate">{t.fuel_level != null ? `${Math.round(t.fuel_level)}%` : "–"}</p>
          </div>
        </div>
      ) : (
        <div className="text-xs text-gray-400 mt-2">Keine Telemetrie-Daten</div>
      )}

      {canControl && (
        <div className="flex items-center gap-3 mt-3 pt-3 border-t border-gray-100 justify-center" onClick={e => e.stopPropagation()}>
          {(() => {
            const isRunning = generator.status === "running" || generator.latest_telemetry?.engine_running === true || (generator.latest_telemetry?.rpm || 0) > 0;
            const isAuto = generator.status === "online" || generator.status === "standby";
            return (
              <>
                {/* Stop */}
                <button onClick={e => sendCmd(e, "stop", "Generator stoppen")} disabled={cmdLoading !== null}
                  className="group disabled:opacity-50 focus:outline-none"
                  data-testid={`cmd-stop-${generator.serial_number}`}>
                  <div className={`w-9 h-9 rounded-full flex items-center justify-center transition-all duration-150
                    ${!isRunning
                      ? "bg-gradient-to-b from-red-400 via-red-600 to-red-800"
                      : "bg-gradient-to-b from-gray-200 via-gray-300 to-gray-400 group-hover:from-red-300 group-hover:via-red-400 group-hover:to-red-600"
                    } ring-2 ring-gray-300 ring-offset-1`}
                    style={{boxShadow: !isRunning ? '0 3px 10px rgba(220,38,38,0.4), inset 0 1px 3px rgba(255,255,255,0.25)' : '0 2px 6px rgba(0,0,0,0.12), inset 0 1px 3px rgba(255,255,255,0.4)'}}>
                    <span className={`text-sm font-bold ${!isRunning ? "text-white" : "text-gray-600 group-hover:text-white"}`}>O</span>
                  </div>
                  <span className="block text-[8px] text-gray-400 text-center mt-1 font-medium">{cmdLoading === "stop" ? "..." : "Stop"}</span>
                </button>
                {/* Auto */}
                <button onClick={e => sendCmd(e, "auto_on", "Auto EIN")} disabled={cmdLoading !== null}
                  className="group disabled:opacity-50 focus:outline-none"
                  data-testid={`cmd-auto-${generator.serial_number}`}>
                  <div className={`w-9 h-9 rounded-full flex items-center justify-center transition-all duration-150
                    ${isAuto
                      ? "bg-gradient-to-b from-teal-200 via-teal-300 to-teal-500"
                      : "bg-gradient-to-b from-gray-100 via-gray-200 to-gray-350 group-hover:from-gray-200 group-hover:via-gray-300 group-hover:to-gray-400"
                    } ring-2 ring-gray-300 ring-offset-1`}
                    style={{boxShadow: isAuto ? '0 3px 10px rgba(20,184,166,0.35), inset 0 1px 3px rgba(255,255,255,0.3)' : '0 2px 6px rgba(0,0,0,0.08), inset 0 1px 4px rgba(255,255,255,0.5)'}}>
                    <span className={`text-[7px] font-extrabold ${isAuto ? "text-teal-900" : "text-gray-500 group-hover:text-gray-700"}`}>AUTO</span>
                  </div>
                  <span className="block text-[8px] text-gray-400 text-center mt-1 font-medium">{cmdLoading === "auto_on" ? "..." : "Auto"}</span>
                </button>
                {/* Start */}
                <button onClick={e => sendCmd(e, "start", "Generator starten")} disabled={cmdLoading !== null}
                  className="group disabled:opacity-50 focus:outline-none"
                  data-testid={`cmd-start-${generator.serial_number}`}>
                  <div className={`w-9 h-9 rounded-full flex items-center justify-center transition-all duration-150
                    ${isRunning
                      ? "bg-gradient-to-b from-emerald-300 via-emerald-500 to-emerald-700"
                      : "bg-gradient-to-b from-gray-200 via-gray-300 to-gray-400 group-hover:from-emerald-300 group-hover:via-emerald-400 group-hover:to-emerald-600"
                    } ring-2 ring-gray-300 ring-offset-1`}
                    style={{boxShadow: isRunning ? '0 3px 10px rgba(16,185,129,0.4), inset 0 1px 3px rgba(255,255,255,0.25)' : '0 2px 6px rgba(0,0,0,0.12), inset 0 1px 3px rgba(255,255,255,0.4)'}}>
                    <span className={`text-sm font-bold ${isRunning ? "text-white" : "text-gray-600 group-hover:text-white"}`}>I</span>
                  </div>
                  <span className="block text-[8px] text-gray-400 text-center mt-1 font-medium">{cmdLoading === "start" ? "..." : "Start"}</span>
                </button>
              </>
            );
          })()}
        </div>
      )}

      <div className="flex items-center justify-between mt-3 pt-3 border-t border-gray-100">
        <span className="text-[10px] text-gray-400 flex items-center gap-1"><Clock className="w-3 h-3" /> {lastSeen}</span>
        <ChevronRight className="w-4 h-4 text-gray-300 group-hover:text-fuchsia-600 transition-colors" />
      </div>
    </div>
  );
}

function FitBounds({ generators }) {
  const map = useMap();
  useEffect(() => {
    const pts = generators.filter(g => g.latitude && g.longitude).map(g => [g.latitude, g.longitude]);
    if (pts.length > 0) {
      map.fitBounds(pts, { padding: [40, 40], maxZoom: 13 });
    }
  }, [generators, map]);
  return null;
}

export default function GeneratorDashboardPage() {
  const { user, isAdmin } = useAuth();
  const navigate = useNavigate();
  const [generators, setGenerators] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [viewMode, setViewMode] = useState("grid"); // "grid" or "map"

  const fetchData = useCallback(async () => {
    try {
      const [genRes, statsRes] = await Promise.all([
        api.get("/generators"),
        api.get("/generators/stats/overview"),
      ]);
      setGenerators(genRes.data);
      setStats(statsRes.data);
    } catch (err) {
      toast.error("Fehler beim Laden der Generatoren");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 1200000); // 20 Min
    return () => clearInterval(interval);
  }, [fetchData]);

  const handleStatClick = (filterValue) => {
    setStatusFilter(prev => prev === filterValue ? "all" : filterValue);
  };

  const filtered = generators.filter((g) => {
    const matchSearch =
      !search ||
      (g.name || "").toLowerCase().includes(search.toLowerCase()) ||
      (g.serial_number || "").toLowerCase().includes(search.toLowerCase()) ||
      (g.location_name || "").toLowerCase().includes(search.toLowerCase());
    const matchStatus = statusFilter === "all" || g.status === statusFilter || (statusFilter === "standby" && g.status === "online");
    return matchSearch && matchStatus;
  });

  // Sort: Alarm/Warning first, then running/online/standby, then offline
  const statusPriority = { alarm: 0, warning: 1, running: 2, online: 3, standby: 4, offline: 5 };
  const sorted = [...filtered].sort((a, b) => {
    const pa = statusPriority[a.status] ?? 9;
    const pb = statusPriority[b.status] ?? 9;
    return pa - pb;
  });

  if (loading) {
    return (
      <div className="h-screen w-full flex items-center justify-center bg-white">
        <div className="animate-pulse text-fuchsia-600">Lade Generatoren...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50" data-testid="generator-dashboard">
      {/* Header */}
      <header className="sticky top-0 z-10 bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Button variant="ghost" size="sm" onClick={() => navigate("/hub")} className="text-gray-600 hover:text-fuchsia-600" data-testid="back-to-hub-btn">
              <ArrowLeft className="w-4 h-4 mr-1" /> Zurück
            </Button>
            <div className="h-5 w-px bg-gray-200" />
            <h1 className="text-base font-semibold text-gray-900 tracking-tight">Monitoring</h1>
          </div>
          <div className="flex items-center gap-2">
            {/* View Toggle */}
            <div className="flex bg-gray-100 rounded-lg p-0.5">
              <button
                onClick={() => setViewMode("grid")}
                className={`p-1.5 rounded-md transition-colors ${viewMode === "grid" ? "bg-white shadow text-fuchsia-600" : "text-gray-400 hover:text-gray-600"}`}
                data-testid="view-grid-btn"
              >
                <LayoutGrid className="w-4 h-4" />
              </button>
              <button
                onClick={() => setViewMode("map")}
                className={`p-1.5 rounded-md transition-colors ${viewMode === "map" ? "bg-white shadow text-fuchsia-600" : "text-gray-400 hover:text-gray-600"}`}
                data-testid="view-map-btn"
              >
                <Map className="w-4 h-4" />
              </button>
            </div>
            <Button variant="ghost" size="sm" onClick={fetchData} className="text-gray-500 hover:text-fuchsia-600" data-testid="refresh-btn">
              <RefreshCw className="w-4 h-4" />
            </Button>
            <Logo size="small" />
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 py-6">
        {/* Stats - clickable as filters */}
        {stats && (
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-6" data-testid="stats-overview">
            <StatCard icon={Activity} label="Gesamt" value={stats.total} color="bg-fuchsia-600" active={statusFilter === "all"} onClick={() => handleStatClick("all")} />
            <StatCard icon={Power} label="Läuft" value={stats.running} color="bg-emerald-600" active={statusFilter === "running"} onClick={() => handleStatClick("running")} />
            <StatCard icon={Zap} label="Online" value={(stats.standby || 0) + (stats.online || 0)} color="bg-teal-600" active={statusFilter === "standby"} onClick={() => handleStatClick("standby")} />
            <StatCard icon={AlertTriangle} label="Warnung" value={stats.alarm} color="bg-amber-500" active={statusFilter === "warning"} onClick={() => handleStatClick("warning")} />
            <StatCard icon={WifiOff} label="Offline" value={stats.offline} color="bg-gray-400" active={statusFilter === "offline"} onClick={() => handleStatClick("offline")} />
          </div>
        )}

        {/* Search */}
        <div className="mb-6">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <input
              type="text"
              placeholder="Suche nach Name, Seriennummer, Standort..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pl-10 pr-4 py-2 bg-white border border-gray-200 rounded-lg text-sm text-gray-900 placeholder-gray-400 focus:outline-none focus:border-fuchsia-500 transition-colors"
              data-testid="generator-search-input"
            />
          </div>
        </div>

        {/* Map View */}
        {viewMode === "map" && (
          <div className="bg-white border border-gray-200 rounded-lg overflow-hidden mb-6" style={{ height: "500px" }} data-testid="generator-map">
            <MapContainer
              center={[50.1109, 8.6821]}
              zoom={10}
              style={{ height: "100%", width: "100%" }}
              scrollWheelZoom={true}
            >
              <TileLayer
                attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
                url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
              />
              <FitBounds generators={filtered} />
              {filtered.filter(g => g.latitude && g.longitude).map((gen) => {
                const s = statusConfig[gen.status] || statusConfig.offline;
                const t = gen.latest_telemetry;
                return (
                  <Marker
                    key={gen.id}
                    position={[gen.latitude, gen.longitude]}
                    icon={getMarkerIcon(gen.status)}
                    eventHandlers={{ click: () => navigate(`/generators/${gen.id}`) }}
                  >
                    <Popup>
                      <div className="min-w-[180px]">
                        <p className="font-semibold text-sm">{gen.serial_number || gen.name}</p>
                        <p className="text-xs text-gray-500">{gen.model}</p>
                        <p className="text-xs mt-1">
                          <span className={`inline-block w-2 h-2 rounded-full ${s.color} mr-1`}></span>
                          {s.label}
                        </p>
                        {t && (
                          <div className="text-xs mt-1 text-gray-600">
                            {t.power_kw ? `${Math.round(t.power_kw)} kW` : ""}{t.power_kw && t.fuel_level ? " · " : ""}{t.fuel_level ? `Tank ${Math.round(t.fuel_level)}%` : ""}
                          </div>
                        )}
                        {gen.location_name && <p className="text-xs text-gray-400 mt-1">{gen.location_name}</p>}
                      </div>
                    </Popup>
                  </Marker>
                );
              })}
            </MapContainer>
          </div>
        )}

        {/* List View */}
        {viewMode === "grid" && (
          <>
            {sorted.length === 0 ? (
              <div className="text-center py-20">
                <Activity className="w-12 h-12 text-gray-300 mx-auto mb-4" />
                <p className="text-gray-500 mb-4">
                  {generators.length === 0 ? "Keine Generatoren vorhanden" : "Keine Treffer für den Filter"}
                </p>
              </div>
            ) : (
              <div className="bg-white border border-gray-200 rounded-lg overflow-hidden" data-testid="generator-list">
                {sorted.map((gen, idx) => {
                  const s = statusConfig[gen.status] || statusConfig.offline;
                  const t = gen.latest_telemetry;
                  const lastSeen = gen.last_seen ? new Date(gen.last_seen).toLocaleString("de-DE", { day:"2-digit", month:"2-digit", hour:"2-digit", minute:"2-digit" }) : "–";
                  return (
                    <div
                      key={gen.id}
                      onClick={() => navigate(`/generators/${gen.id}`)}
                      className={`flex items-center gap-4 px-4 py-3 cursor-pointer hover:bg-gray-50 transition-colors ${idx > 0 ? "border-t border-gray-100" : ""} ${gen.status === "alarm" || gen.status === "warning" ? "bg-red-50/50" : ""}`}
                      data-testid={`generator-row-${gen.serial_number || gen.id}`}
                    >
                      {/* Status Dot */}
                      <div className={`w-3 h-3 rounded-full flex-shrink-0 ${s.color}`} title={s.label} />

                      {/* Name + Model */}
                      <div className="min-w-0 flex-1">
                        <p className="text-sm font-semibold text-gray-900 truncate">{gen.serial_number || gen.name}</p>
                        <p className="text-xs text-gray-400 truncate">{gen.model || gen.location_name || "–"}</p>
                      </div>

                      {/* Telemetry Values */}
                      <div className="hidden md:flex items-center gap-6 text-xs font-mono text-gray-600 flex-shrink-0">
                        {t?.power_kw != null && (
                          <span className="text-fuchsia-600 font-semibold">{Math.round(t.power_kw * 10) / 10} kW</span>
                        )}
                        {t?.voltage_l1 != null && (
                          <span>{Math.round(t.voltage_l1 * 10) / 10} V</span>
                        )}
                        {t?.frequency != null && (
                          <span>{Math.round(t.frequency * 10) / 10} Hz</span>
                        )}
                        {t?.fuel_level != null && (
                          <span className={t.fuel_level < 25 ? "text-red-500" : ""}>{Math.round(t.fuel_level)}% Tank</span>
                        )}
                      </div>

                      {/* Status + Time */}
                      <div className="flex flex-col items-end flex-shrink-0 gap-0.5">
                        <span className={`text-[10px] font-medium ${s.textColor}`}>{s.label}</span>
                        <span className="text-[10px] text-gray-400">{lastSeen}</span>
                      </div>

                      {/* GPS Pin */}
                      {gen.latitude && gen.longitude ? (
                        <a
                          href={`https://www.google.com/maps?q=${gen.latitude},${gen.longitude}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          onClick={(e) => e.stopPropagation()}
                          className="p-1.5 rounded-lg hover:bg-blue-50 text-blue-500 hover:text-blue-700 transition-colors flex-shrink-0"
                          title="Standort anzeigen"
                          data-testid={`gps-pin-${gen.serial_number || gen.id}`}
                        >
                          <MapPin className="w-4 h-4" />
                        </a>
                      ) : (
                        <div className="w-7 flex-shrink-0" />
                      )}

                      <ChevronRight className="w-4 h-4 text-gray-300 flex-shrink-0" />
                    </div>
                  );
                })}
              </div>
            )}
          </>
        )}
      </main>
    </div>
  );
}
