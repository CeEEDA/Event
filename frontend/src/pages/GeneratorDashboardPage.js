import { useState, useEffect, useCallback } from "react";
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
} from "lucide-react";

const statusConfig = {
  running: { label: "Läuft", color: "bg-emerald-500", textColor: "text-emerald-600" },
  standby: { label: "Standby", color: "bg-sky-500", textColor: "text-sky-600" },
  warning: { label: "Warnung", color: "bg-amber-500", textColor: "text-amber-600" },
  alarm: { label: "Alarm", color: "bg-red-500", textColor: "text-red-600" },
  offline: { label: "Offline", color: "bg-gray-400", textColor: "text-gray-500" },
};

function StatCard({ icon: Icon, label, value, color }) {
  return (
    <div className="bg-white border border-gray-200 rounded-lg p-4 flex items-center gap-3" data-testid={`stat-${label.toLowerCase()}`}>
      <div className={`w-10 h-10 rounded-lg ${color} flex items-center justify-center`}>
        <Icon className="w-5 h-5 text-white" />
      </div>
      <div>
        <p className="text-2xl font-bold text-gray-900 font-mono">{value}</p>
        <p className="text-xs text-gray-500 uppercase tracking-wider">{label}</p>
      </div>
    </div>
  );
}

function GeneratorCard({ generator, onClick }) {
  const status = statusConfig[generator.status] || statusConfig.offline;
  const t = generator.latest_telemetry;
  const lastSeen = generator.last_seen
    ? new Date(generator.last_seen).toLocaleString("de-DE", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" })
    : "–";

  return (
    <button
      onClick={onClick}
      className="bg-white border border-gray-200 rounded-lg p-5 text-left hover:border-fuchsia-400 hover:shadow-md transition-all group w-full"
      data-testid={`generator-card-${generator.serial_number}`}
    >
      <div className="flex items-start justify-between mb-3">
        <div className="flex-1 min-w-0">
          <h3 className="text-sm font-semibold text-gray-900 truncate">{generator.name}</h3>
          <p className="text-xs text-gray-400 font-mono">{generator.serial_number} · {generator.model}</p>
        </div>
        <div className="flex items-center gap-2 ml-2 flex-shrink-0">
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
            <div className="flex items-center gap-1 text-[10px] text-gray-400 mb-0.5">
              <Zap className="w-3 h-3" /> Leistung
            </div>
            <p className="text-xs font-mono text-gray-900 truncate">{t.power_kw ? `${Math.round(t.power_kw * 10) / 10} kW` : "–"}</p>
          </div>
          <div className="bg-gray-50 rounded px-2 py-1.5">
            <div className="flex items-center gap-1 text-[10px] text-gray-400 mb-0.5">
              <Gauge className="w-3 h-3" /> Last
            </div>
            <p className="text-xs font-mono text-gray-900 truncate">{t.load_percent ? `${Math.round(t.load_percent)}%` : "–"}</p>
          </div>
          <div className="bg-gray-50 rounded px-2 py-1.5">
            <div className="flex items-center gap-1 text-[10px] text-gray-400 mb-0.5">
              <Thermometer className="w-3 h-3" /> Temp
            </div>
            <p className="text-xs font-mono text-gray-900 truncate">{t.coolant_temp != null ? `${Math.round(t.coolant_temp * 10) / 10}°C` : "–"}</p>
          </div>
          <div className="bg-gray-50 rounded px-2 py-1.5">
            <div className="flex items-center gap-1 text-[10px] text-gray-400 mb-0.5">
              <Fuel className="w-3 h-3" /> Tank
            </div>
            <p className="text-xs font-mono text-gray-900 truncate">{t.fuel_level != null ? `${Math.round(t.fuel_level)}%` : "–"}</p>
          </div>
        </div>
      ) : (
        <div className="text-xs text-gray-400 mt-2">Keine Telemetrie-Daten</div>
      )}

      <div className="flex items-center justify-between mt-3 pt-3 border-t border-gray-100">
        <span className="text-[10px] text-gray-400 flex items-center gap-1">
          <Clock className="w-3 h-3" /> {lastSeen}
        </span>
        <ChevronRight className="w-4 h-4 text-gray-300 group-hover:text-fuchsia-600 transition-colors" />
      </div>
    </button>
  );
}

export default function GeneratorDashboardPage() {
  const { user, isAdmin } = useAuth();
  const navigate = useNavigate();
  const [generators, setGenerators] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");

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
    const interval = setInterval(fetchData, 30000);
    return () => clearInterval(interval);
  }, [fetchData]);

  const handleSimulate = async () => {
    try {
      const res = await api.post("/generators/simulate");
      toast.success(res.data.message);
      fetchData();
    } catch (err) {
      toast.error("Fehler bei Simulation");
    }
  };

  const filtered = generators.filter((g) => {
    const matchSearch =
      !search ||
      g.name.toLowerCase().includes(search.toLowerCase()) ||
      g.serial_number.toLowerCase().includes(search.toLowerCase()) ||
      (g.location_name || "").toLowerCase().includes(search.toLowerCase());
    const matchStatus = statusFilter === "all" || g.status === statusFilter;
    return matchSearch && matchStatus;
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
              <ArrowLeft className="w-4 h-4 mr-1" /> Hub
            </Button>
            <div className="h-5 w-px bg-gray-200" />
            <h1 className="text-base font-semibold text-gray-900 tracking-tight">Generator-Monitoring</h1>
          </div>
          <div className="flex items-center gap-3">
            <Button variant="ghost" size="sm" onClick={fetchData} className="text-gray-500 hover:text-fuchsia-600" data-testid="refresh-btn">
              <RefreshCw className="w-4 h-4" />
            </Button>
            {isAdmin && generators.length === 0 && (
              <Button size="sm" onClick={handleSimulate} className="bg-fuchsia-600 hover:bg-fuchsia-700 text-white" data-testid="simulate-btn">
                <Plus className="w-4 h-4 mr-1" /> Demo-Daten
              </Button>
            )}
            <Logo size="small" />
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 py-6">
        {/* Stats */}
        {stats && (
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-6" data-testid="stats-overview">
            <StatCard icon={Activity} label="Gesamt" value={stats.total} color="bg-fuchsia-600" />
            <StatCard icon={Power} label="Läuft" value={stats.running} color="bg-emerald-600" />
            <StatCard icon={Zap} label="Standby" value={stats.standby} color="bg-sky-600" />
            <StatCard icon={AlertTriangle} label="Warnung" value={stats.alarm} color="bg-amber-500" />
            <StatCard icon={WifiOff} label="Offline" value={stats.offline} color="bg-gray-400" />
          </div>
        )}

        {/* Filters */}
        <div className="flex flex-col sm:flex-row gap-3 mb-6">
          <div className="relative flex-1">
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
          <div className="flex gap-1">
            {["all", "running", "standby", "warning", "alarm", "offline"].map((s) => (
              <button
                key={s}
                onClick={() => setStatusFilter(s)}
                className={`px-3 py-2 rounded-lg text-xs font-medium transition-colors ${
                  statusFilter === s
                    ? "bg-fuchsia-600 text-white"
                    : "bg-white text-gray-500 hover:text-gray-700 border border-gray-200"
                }`}
                data-testid={`filter-${s}`}
              >
                {s === "all" ? "Alle" : (statusConfig[s]?.label || s)}
              </button>
            ))}
          </div>
        </div>

        {/* Generator Grid */}
        {filtered.length === 0 ? (
          <div className="text-center py-20">
            <Activity className="w-12 h-12 text-gray-300 mx-auto mb-4" />
            <p className="text-gray-500 mb-4">
              {generators.length === 0 ? "Keine Generatoren vorhanden" : "Keine Treffer für den Filter"}
            </p>
            {isAdmin && generators.length === 0 && (
              <Button size="sm" onClick={handleSimulate} className="bg-fuchsia-600 hover:bg-fuchsia-700 text-white" data-testid="simulate-empty-btn">
                <Plus className="w-4 h-4 mr-1" /> Demo-Daten generieren
              </Button>
            )}
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4" data-testid="generator-grid">
            {filtered.map((gen) => (
              <GeneratorCard
                key={gen.id}
                generator={gen}
                onClick={() => navigate(`/generators/${gen.id}`)}
              />
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
