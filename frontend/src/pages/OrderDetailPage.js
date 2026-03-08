import { useState, useEffect, useCallback } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Logo } from "../components/Logo";
import api from "../lib/api";
import { toast } from "sonner";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import {
  ArrowLeft,
  ClipboardList,
  MapPin,
  Loader2,
  RefreshCw,
  AlertTriangle,
  CheckCircle,
  XCircle,
  Archive,
  Zap,
  Settings2,
  Save,
  Circle,
} from "lucide-react";
import { MapContainer, TileLayer, Marker, Popup, useMap } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

const formatDate = (d) => {
  if (!d || d === "0000-00-00") return "—";
  const parts = d.split("-");
  if (parts.length !== 3) return d;
  return `${parts[2]}.${parts[1]}.${parts[0]}`;
};

const formatDateRange = (start, end) => {
  const s = formatDate(start);
  const e = formatDate(end);
  if (s === "—" && e === "—") return "—";
  if (s === e) return s;
  return `${s} – ${e}`;
};

const StatusBadge = ({ order }) => {
  if (!order) return null;
  if (order.is_canceled)
    return (
      <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded text-xs font-medium bg-red-100 text-red-700">
        <XCircle className="w-3.5 h-3.5" /> Storniert
      </span>
    );
  if (order.is_confirmed)
    return (
      <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded text-xs font-medium bg-emerald-100 text-emerald-700">
        <CheckCircle className="w-3.5 h-3.5" /> Bestätigt
      </span>
    );
  if (order.is_archived)
    return (
      <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded text-xs font-medium bg-gray-100 text-gray-600">
        <Archive className="w-3.5 h-3.5" /> Archiviert
      </span>
    );
  return (
    <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded text-xs font-medium bg-sky-100 text-sky-700">
      Offen
    </span>
  );
};

// Leaflet icon for generators
const genIcon = L.divIcon({
  className: "",
  html: `<div style="width:28px;height:28px;border-radius:50%;background:#d946ef;border:3px solid #fff;box-shadow:0 2px 6px rgba(0,0,0,.3);display:flex;align-items:center;justify-content:center"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10"></polygon></svg></div>`,
  iconSize: [28, 28],
  iconAnchor: [14, 14],
});

const centerIcon = L.divIcon({
  className: "",
  html: `<div style="width:18px;height:18px;border-radius:50%;background:#f97316;border:3px solid #fff;box-shadow:0 2px 6px rgba(0,0,0,.35)"></div>`,
  iconSize: [18, 18],
  iconAnchor: [9, 9],
});

function RadiusCircle({ center, radiusKm }) {
  const map = useMap();
  useEffect(() => {
    if (!center || !center[0]) return;
    const circle = L.circle(center, { radius: radiusKm * 1000, color: "#f97316", fillColor: "#f97316", fillOpacity: 0.08, weight: 2, dashArray: "6 4" });
    circle.addTo(map);
    return () => map.removeLayer(circle);
  }, [map, center, radiusKm]);
  return null;
}

function FitBounds({ center, generators, radiusKm }) {
  const map = useMap();
  useEffect(() => {
    if (!center || !center[0]) return;
    const points = [[center[0], center[1]]];
    generators.forEach((g) => points.push([g.latitude, g.longitude]));
    // Also include radius boundary
    const latOffset = radiusKm / 111;
    points.push([center[0] + latOffset, center[1]]);
    points.push([center[0] - latOffset, center[1]]);
    if (points.length > 0) {
      map.fitBounds(points, { padding: [30, 30], maxZoom: 14 });
    }
  }, [map, center, generators, radiusKm]);
  return null;
}

const statusColors = {
  running: "#10B981",
  standby: "#0EA5E9",
  online: "#14B8A6",
  warning: "#F59E0B",
  alarm: "#EF4444",
  offline: "#9CA3AF",
};

export default function OrderDetailPage() {
  const { pk } = useParams();
  const navigate = useNavigate();
  const [order, setOrder] = useState(null);
  const [generators, setGenerators] = useState([]);
  const [loading, setLoading] = useState(true);
  const [genLoading, setGenLoading] = useState(false);
  const [error, setError] = useState(null);
  const [radiusInput, setRadiusInput] = useState("5");
  const [savingRadius, setSavingRadius] = useState(false);

  const fetchOrder = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const { data } = await api.get(`/orders/epirent/${pk}`);
      setOrder(data);
      setRadiusInput(String(data.radius_km || 5));
    } catch (err) {
      setError(err.response?.data?.detail || "Fehler beim Laden");
    } finally {
      setLoading(false);
    }
  }, [pk]);

  const fetchGenerators = useCallback(async () => {
    setGenLoading(true);
    try {
      const { data } = await api.get(`/orders/epirent/${pk}/generators`);
      setGenerators(data.generators || []);
    } catch {
      // silent
    } finally {
      setGenLoading(false);
    }
  }, [pk]);

  useEffect(() => {
    fetchOrder();
  }, [fetchOrder]);

  useEffect(() => {
    if (order?.center_lat) fetchGenerators();
  }, [order?.center_lat, order?.radius_km, fetchGenerators]);

  const saveRadius = async () => {
    const km = parseFloat(radiusInput);
    if (isNaN(km) || km <= 0) return;
    setSavingRadius(true);
    try {
      await api.put(`/orders/epirent/${pk}/settings`, { radius_km: km });
      toast.success("Radius gespeichert");
      await fetchOrder();
    } catch {
      toast.error("Fehler beim Speichern");
    } finally {
      setSavingRadius(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-fuchsia-500" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gray-50 flex flex-col items-center justify-center gap-4">
        <AlertTriangle className="w-12 h-12 text-red-400" />
        <p className="text-gray-700">{error}</p>
        <Button variant="outline" onClick={() => navigate("/orders")}>Zurück</Button>
      </div>
    );
  }

  const center = order?.center_lat && order?.center_lng ? [order.center_lat, order.center_lng] : null;

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col" data-testid="order-detail-page">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 p-4">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => navigate("/orders")}
              className="text-gray-600 hover:text-fuchsia-600"
              data-testid="back-to-orders-btn"
            >
              <ArrowLeft className="w-4 h-4 mr-2" /> Aufträge
            </Button>
            <div className="h-6 w-px bg-gray-200" />
            <div>
              <h1 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
                <ClipboardList className="w-5 h-5 text-fuchsia-600" />
                {order?.order_no}
              </h1>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <StatusBadge order={order} />
            <Button variant="outline" size="sm" onClick={fetchOrder} data-testid="refresh-detail-btn">
              <RefreshCw className="w-4 h-4 mr-1" /> Aktualisieren
            </Button>
            <Logo size="small" />
          </div>
        </div>
      </header>

      <main className="flex-1 p-4 md:p-6">
        <div className="max-w-7xl mx-auto space-y-6">
          {/* Order Info Cards */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="bg-white rounded-lg border border-gray-200 p-4" data-testid="order-info-event">
              <p className="text-xs text-gray-500 mb-1">Event / Projekt</p>
              <p className="font-semibold text-gray-900 text-base">{order?.event || "—"}</p>
              <p className="text-sm text-gray-500 mt-1">
                {formatDateRange(order?.event_start || order?.dispo_start, order?.event_end || order?.dispo_end)}
              </p>
            </div>
            <div className="bg-white rounded-lg border border-gray-200 p-4" data-testid="order-info-customer">
              <p className="text-xs text-gray-500 mb-1">Kunde</p>
              <p className="font-semibold text-gray-900">{order?.contact_name || "—"}</p>
              <p className="text-sm text-gray-500 mt-1">Kd.-Nr. {order?.customer_no || "—"}</p>
            </div>
            <div className="bg-white rounded-lg border border-gray-200 p-4" data-testid="order-info-address">
              <p className="text-xs text-gray-500 mb-1">Lieferanschrift</p>
              <p className="font-semibold text-gray-900 flex items-center gap-1">
                {order?.address ? (
                  <>
                    <MapPin className="w-4 h-4 text-fuchsia-500 flex-shrink-0" />
                    {order.address}
                  </>
                ) : "—"}
              </p>
              {center && (
                <p className="text-xs text-gray-400 mt-1">
                  {center[0].toFixed(4)}, {center[1].toFixed(4)}
                </p>
              )}
            </div>
          </div>

          {/* Map + Generators */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Map */}
            <div className="lg:col-span-2 bg-white rounded-lg border border-gray-200 overflow-hidden" data-testid="order-map-container">
              <div className="p-3 border-b border-gray-100 flex items-center justify-between">
                <h2 className="text-sm font-semibold text-gray-700 flex items-center gap-2">
                  <MapPin className="w-4 h-4 text-fuchsia-500" />
                  Standort & Generatoren
                </h2>
                <div className="flex items-center gap-2">
                  <Settings2 className="w-4 h-4 text-gray-400" />
                  <span className="text-xs text-gray-500">Radius:</span>
                  <Input
                    type="number"
                    value={radiusInput}
                    onChange={(e) => setRadiusInput(e.target.value)}
                    className="w-20 h-7 text-xs text-center"
                    min="0.5"
                    step="0.5"
                    data-testid="radius-input"
                  />
                  <span className="text-xs text-gray-500">km</span>
                  <Button
                    size="sm"
                    variant="outline"
                    className="h-7 text-xs"
                    onClick={saveRadius}
                    disabled={savingRadius}
                    data-testid="save-radius-btn"
                  >
                    {savingRadius ? <Loader2 className="w-3 h-3 animate-spin" /> : <Save className="w-3 h-3" />}
                  </Button>
                </div>
              </div>
              {center ? (
                <div style={{ height: 420 }}>
                  <MapContainer
                    center={center}
                    zoom={12}
                    style={{ height: "100%", width: "100%" }}
                    scrollWheelZoom={true}
                  >
                    <TileLayer
                      url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                      attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a>'
                    />
                    <RadiusCircle center={center} radiusKm={order?.radius_km || 5} />
                    <FitBounds center={center} generators={generators} radiusKm={order?.radius_km || 5} />
                    <Marker position={center} icon={centerIcon}>
                      <Popup>
                        <strong>Lieferanschrift</strong><br />
                        {order?.address || "Auftrag"}
                      </Popup>
                    </Marker>
                    {generators.map((g) => (
                      <Marker key={g.id} position={[g.latitude, g.longitude]} icon={genIcon}>
                        <Popup>
                          <strong>{g.name}</strong><br />
                          {g.model} | {g.status}<br />
                          <span className="text-xs">{g.distance_km} km entfernt</span>
                        </Popup>
                      </Marker>
                    ))}
                  </MapContainer>
                </div>
              ) : (
                <div className="flex items-center justify-center h-64 text-gray-400">
                  <div className="text-center">
                    <MapPin className="w-10 h-10 mx-auto mb-2 opacity-30" />
                    <p className="text-sm">Keine Koordinaten verfügbar</p>
                    <p className="text-xs">Die Lieferanschrift konnte nicht geocodiert werden</p>
                  </div>
                </div>
              )}
            </div>

            {/* Generator List */}
            <div className="bg-white rounded-lg border border-gray-200" data-testid="generators-panel">
              <div className="p-3 border-b border-gray-100">
                <h2 className="text-sm font-semibold text-gray-700 flex items-center gap-2">
                  <Zap className="w-4 h-4 text-fuchsia-500" />
                  Generatoren im Radius
                  {genLoading && <Loader2 className="w-3 h-3 animate-spin text-gray-400" />}
                </h2>
              </div>
              <div className="divide-y divide-gray-100 max-h-[380px] overflow-y-auto">
                {generators.length === 0 && !genLoading && (
                  <div className="p-6 text-center text-gray-400">
                    <Zap className="w-8 h-8 mx-auto mb-2 opacity-30" />
                    <p className="text-sm">Keine Generatoren im Radius</p>
                  </div>
                )}
                {generators.map((g) => (
                  <div
                    key={g.id}
                    className="p-3 hover:bg-gray-50 cursor-pointer transition-colors"
                    onClick={() => navigate(`/generators/${g.id}`)}
                    data-testid={`gen-item-${g.id}`}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <div
                          className="w-2.5 h-2.5 rounded-full flex-shrink-0"
                          style={{ backgroundColor: statusColors[g.status] || "#9CA3AF" }}
                        />
                        <div>
                          <p className="text-sm font-medium text-gray-900">{g.name}</p>
                          <p className="text-xs text-gray-500">{g.model} · {g.serial_number}</p>
                        </div>
                      </div>
                      <span className="text-xs text-gray-400 whitespace-nowrap">{g.distance_km} km</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
