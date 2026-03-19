import { useState, useEffect, useCallback } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Logo } from "../components/Logo";
import api from "../lib/api";
import { toast } from "sonner";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
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
  Plus,
  Crosshair,
  Trash2,
  Lightbulb,
  Box,
  GitFork,
  Fuel,
  Check,
  X,
  Pencil,
  Download,
  Droplets,
} from "lucide-react";
import { MapContainer, TileLayer, Marker, Popup, useMap } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { OpenLocationCode } from "open-location-code";

const olcInstance = new OpenLocationCode();

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

const ASSET_TYPES = [
  { value: "Lichtmast", icon: Lightbulb, color: "#f97316" },
  { value: "Stromerzeuger", icon: Zap, color: "#f97316" },
  { value: "Verteiler", icon: GitFork, color: "#f97316" },
  { value: "Sonstiges", icon: Box, color: "#f97316" },
];

const assetTypeIcon = (type) => {
  const cfg = ASSET_TYPES.find((t) => t.value === type) || ASSET_TYPES[3];
  return cfg;
};

const makeAssetIcon = (type) => {
  const icons = {
    Lichtmast: `<circle cx="12" cy="5" r="3" fill="#fff" stroke="#fff" stroke-width="1.5"/><line x1="12" y1="8" x2="12" y2="20" stroke="#fff" stroke-width="2.5" stroke-linecap="round"/>`,
    Stromerzeuger: `<polygon points="13 2 3 14 12 14 11 22 21 10 12 10" fill="none" stroke="#fff" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>`,
    Verteiler: `<line x1="12" y1="3" x2="12" y2="15" stroke="#fff" stroke-width="2.5" stroke-linecap="round"/><line x1="6" y1="9" x2="12" y2="15" stroke="#fff" stroke-width="2" stroke-linecap="round"/><line x1="18" y1="9" x2="12" y2="15" stroke="#fff" stroke-width="2" stroke-linecap="round"/><circle cx="12" cy="18" r="2.5" fill="#fff"/>`,
    Sonstiges: `<rect x="4" y="4" width="16" height="16" rx="3" fill="none" stroke="#fff" stroke-width="2"/><line x1="12" y1="8" x2="12" y2="16" stroke="#fff" stroke-width="2" stroke-linecap="round"/><line x1="8" y1="12" x2="16" y2="12" stroke="#fff" stroke-width="2" stroke-linecap="round"/>`,
  };
  const svg = icons[type] || icons.Sonstiges;
  return L.divIcon({
    className: "",
    html: `<div style="width:32px;height:32px;border-radius:50%;background:#f97316;border:3px solid #fff;box-shadow:0 2px 8px rgba(249,115,22,.5);display:flex;align-items:center;justify-content:center"><svg width="16" height="16" viewBox="0 0 24 24">${svg}</svg></div>`,
    iconSize: [32, 32],
    iconAnchor: [16, 16],
  });
};

// Generator icon (fuchsia)
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

function FitBounds({ center, generators, assets, radiusKm }) {
  const map = useMap();
  useEffect(() => {
    if (!center || !center[0]) return;
    const points = [[center[0], center[1]]];
    generators.forEach((g) => points.push([g.latitude, g.longitude]));
    assets.forEach((a) => points.push([a.latitude, a.longitude]));
    const latOffset = radiusKm / 111;
    points.push([center[0] + latOffset, center[1]]);
    points.push([center[0] - latOffset, center[1]]);
    if (points.length > 0) {
      map.fitBounds(points, { padding: [30, 30], maxZoom: 14 });
    }
  }, [map, center, generators, assets, radiusKm]);
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

function encodePlusCode(lat, lng) {
  try {
    return olcInstance.encode(lat, lng, 10);
  } catch {
    return "";
  }
}

export default function OrderDetailPage() {
  const { pk } = useParams();
  const navigate = useNavigate();
  const [order, setOrder] = useState(null);
  const [generators, setGenerators] = useState([]);
  const [assets, setAssets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [genLoading, setGenLoading] = useState(false);
  const [error, setError] = useState(null);
  const [radiusInput, setRadiusInput] = useState("5");
  const [savingRadius, setSavingRadius] = useState(false);

  // Asset form
  const [assetType, setAssetType] = useState("Lichtmast");
  const [assetLabel, setAssetLabel] = useState("");
  const [assetLat, setAssetLat] = useState("");
  const [assetLng, setAssetLng] = useState("");
  const [locating, setLocating] = useState(false);
  const [addingAsset, setAddingAsset] = useState(false);

  // Tankbelege
  const [fuelReceipts, setFuelReceipts] = useState([]);
  const [fuelLoading, setFuelLoading] = useState(false);
  const [showFuelModal, setShowFuelModal] = useState(false);
  const [editFuelReceipt, setEditFuelReceipt] = useState(null);
  const user = JSON.parse(localStorage.getItem("user") || "{}");
  const isAdmin = user.role === "admin";

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

  const fetchAssets = useCallback(async () => {
    try {
      const { data } = await api.get(`/orders/epirent/${pk}/assets`);
      setAssets(data.assets || []);
    } catch {
      // silent
    }
  }, [pk]);

  const fetchFuelReceipts = useCallback(async () => {
    setFuelLoading(true);
    try {
      const { data } = await api.get(`/fuel-receipts/by-order/${pk}`);
      setFuelReceipts(data || []);
    } catch {
      // silent
    } finally {
      setFuelLoading(false);
    }
  }, [pk]);

  useEffect(() => {
    fetchOrder();
    fetchAssets();
    fetchFuelReceipts();
  }, [fetchOrder, fetchAssets, fetchFuelReceipts]);

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

  const getMyPosition = () => {
    if (!navigator.geolocation) {
      toast.error("Geolocation nicht verfügbar");
      return;
    }
    setLocating(true);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setAssetLat(pos.coords.latitude.toFixed(6));
        setAssetLng(pos.coords.longitude.toFixed(6));
        setLocating(false);
        toast.success("Position ermittelt");
      },
      (err) => {
        setLocating(false);
        toast.error("Position konnte nicht ermittelt werden: " + err.message);
      },
      { enableHighAccuracy: true, timeout: 15000 }
    );
  };

  const addAsset = async () => {
    const lat = parseFloat(assetLat);
    const lng = parseFloat(assetLng);
    if (isNaN(lat) || isNaN(lng)) {
      toast.error("Bitte Position ermitteln");
      return;
    }
    setAddingAsset(true);
    try {
      const plusCode = encodePlusCode(lat, lng);
      await api.post(`/orders/epirent/${pk}/assets`, {
        asset_type: assetType,
        latitude: lat,
        longitude: lng,
        label: assetLabel || assetType,
        plus_code: plusCode,
      });
      toast.success("Artikel hinzugefügt");
      setAssetLabel("");
      setAssetLat("");
      setAssetLng("");
      fetchAssets();
    } catch {
      toast.error("Fehler beim Hinzufügen");
    } finally {
      setAddingAsset(false);
    }
  };

  const deleteAsset = async (assetId) => {
    try {
      await api.delete(`/orders/epirent/${pk}/assets/${assetId}`);
      toast.success("Artikel entfernt");
      fetchAssets();
    } catch {
      toast.error("Fehler beim Löschen");
    }
  };

  const confirmFuelReceipt = async (id) => {
    try {
      await api.post(`/fuel-receipts/${id}/confirm`);
      toast.success("Beleg bestätigt");
      fetchFuelReceipts();
    } catch { toast.error("Fehler"); }
  };

  const rejectFuelReceipt = async (id) => {
    try {
      await api.post(`/fuel-receipts/${id}/reject`);
      toast.success("Beleg abgelehnt");
      fetchFuelReceipts();
    } catch { toast.error("Fehler"); }
  };

  const deleteFuelReceipt = async (id) => {
    if (!window.confirm("Tankbeleg wirklich löschen?")) return;
    try {
      await api.delete(`/fuel-receipts/${id}`);
      toast.success("Beleg gelöscht");
      fetchFuelReceipts();
    } catch { toast.error("Fehler"); }
  };

  const openFuelPdf = (id) => {
    const token = localStorage.getItem("token");
    window.open(`${process.env.REACT_APP_BACKEND_URL}/api/fuel-receipts/${id}/pdf?token=${token}`, "_blank");
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
                    <FitBounds center={center} generators={generators} assets={assets} radiusKm={order?.radius_km || 5} />
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
                    {assets.map((a) => (
                      <Marker key={a.id} position={[a.latitude, a.longitude]} icon={makeAssetIcon(a.asset_type)}>
                        <Popup>
                          <strong>{a.label || a.asset_type}</strong><br />
                          <span className="text-xs">{a.asset_type}</span><br />
                          {a.plus_code && <span className="text-xs font-mono">{a.plus_code}</span>}
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

          {/* Asset Placement Section */}
          <div className="bg-white rounded-lg border border-gray-200" data-testid="assets-section">
            <div className="p-4 border-b border-gray-100 flex items-center justify-between">
              <h2 className="text-sm font-semibold text-gray-700 flex items-center gap-2">
                <MapPin className="w-4 h-4 text-orange-500" />
                Artikel positionieren
              </h2>
              <span className="text-xs text-gray-400">{assets.length} Artikel platziert</span>
            </div>

            {/* Add Form */}
            <div className="p-4 border-b border-gray-100 bg-gray-50/50">
              <div className="flex flex-wrap items-end gap-3">
                <div>
                  <label className="block text-xs text-gray-500 mb-1">Artikeltyp</label>
                  <select
                    value={assetType}
                    onChange={(e) => setAssetType(e.target.value)}
                    className="px-3 py-1.5 text-sm border border-gray-200 rounded-lg focus:outline-none focus:border-orange-500 bg-white min-w-[160px]"
                    data-testid="asset-type-select"
                  >
                    {ASSET_TYPES.map((t) => (
                      <option key={t.value} value={t.value}>{t.value}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-xs text-gray-500 mb-1">Bezeichnung (optional)</label>
                  <Input
                    value={assetLabel}
                    onChange={(e) => setAssetLabel(e.target.value)}
                    placeholder="z.B. Lichtmast Bühne 1"
                    className="w-48 h-8 text-sm"
                    data-testid="asset-label-input"
                  />
                </div>
                <div className="flex items-end gap-2">
                  <div>
                    <label className="block text-xs text-gray-500 mb-1">Position</label>
                    <div className="flex items-center gap-1.5">
                      <Input
                        value={assetLat}
                        onChange={(e) => setAssetLat(e.target.value)}
                        placeholder="Breitengrad"
                        className="w-28 h-8 text-xs font-mono"
                        data-testid="asset-lat-input"
                      />
                      <Input
                        value={assetLng}
                        onChange={(e) => setAssetLng(e.target.value)}
                        placeholder="Längengrad"
                        className="w-28 h-8 text-xs font-mono"
                        data-testid="asset-lng-input"
                      />
                    </div>
                  </div>
                  <Button
                    size="sm"
                    variant="outline"
                    className="h-8 text-xs border-orange-300 text-orange-600 hover:bg-orange-50"
                    onClick={getMyPosition}
                    disabled={locating}
                    data-testid="get-position-btn"
                  >
                    {locating ? <Loader2 className="w-3 h-3 animate-spin mr-1" /> : <Crosshair className="w-3 h-3 mr-1" />}
                    Meine Position
                  </Button>
                </div>
                <Button
                  size="sm"
                  className="h-8 bg-orange-500 hover:bg-orange-600 text-white"
                  onClick={addAsset}
                  disabled={addingAsset || !assetLat || !assetLng}
                  data-testid="add-asset-btn"
                >
                  {addingAsset ? <Loader2 className="w-3 h-3 animate-spin mr-1" /> : <Plus className="w-3 h-3 mr-1" />}
                  Hinzufügen
                </Button>
              </div>
              {assetLat && assetLng && (
                <p className="mt-2 text-xs text-gray-400 font-mono" data-testid="asset-plus-code">
                  Plus Code: {encodePlusCode(parseFloat(assetLat), parseFloat(assetLng)) || "—"}
                </p>
              )}
            </div>

            {/* Assets List */}
            {assets.length > 0 && (
              <div className="overflow-x-auto">
                <table className="w-full text-sm" data-testid="assets-table">
                  <thead>
                    <tr className="bg-gray-50 border-b border-gray-200">
                      <th className="text-left px-4 py-2 font-medium text-gray-600">Typ</th>
                      <th className="text-left px-4 py-2 font-medium text-gray-600">Bezeichnung</th>
                      <th className="text-left px-4 py-2 font-medium text-gray-600">Plus Code</th>
                      <th className="text-left px-4 py-2 font-medium text-gray-600">Koordinaten</th>
                      <th className="text-left px-4 py-2 font-medium text-gray-600">Erstellt von</th>
                      <th className="w-10"></th>
                    </tr>
                  </thead>
                  <tbody>
                    {assets.map((a) => {
                      const TypeIcon = assetTypeIcon(a.asset_type).icon;
                      return (
                        <tr key={a.id} className="border-b border-gray-100 hover:bg-orange-50/30" data-testid={`asset-row-${a.id}`}>
                          <td className="px-4 py-2.5">
                            <span className="inline-flex items-center gap-1.5 text-orange-600">
                              <TypeIcon className="w-4 h-4" />
                              {a.asset_type}
                            </span>
                          </td>
                          <td className="px-4 py-2.5 font-medium text-gray-900">{a.label || "—"}</td>
                          <td className="px-4 py-2.5 font-mono text-xs text-gray-600">{a.plus_code || "—"}</td>
                          <td className="px-4 py-2.5 font-mono text-xs text-gray-500">
                            {a.latitude.toFixed(5)}, {a.longitude.toFixed(5)}
                          </td>
                          <td className="px-4 py-2.5 text-xs text-gray-400">{a.created_by}</td>
                          <td className="px-2 py-2.5">
                            <button
                              onClick={() => deleteAsset(a.id)}
                              className="p-1 rounded hover:bg-red-100 text-gray-400 hover:text-red-500 transition-colors"
                              data-testid={`delete-asset-${a.id}`}
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* Tankbelege Section */}
          <div className="bg-white rounded-lg border border-gray-200" data-testid="fuel-receipts-section">
            <div className="p-4 border-b border-gray-100 flex items-center justify-between">
              <h2 className="text-sm font-semibold text-gray-700 flex items-center gap-2">
                <Fuel className="w-4 h-4 text-amber-500" />
                Tankbelege
                {fuelLoading && <Loader2 className="w-3 h-3 animate-spin text-gray-400" />}
              </h2>
              <div className="flex items-center gap-2">
                {fuelReceipts.length > 0 && (
                  <span className="text-xs text-gray-400">
                    {fuelReceipts.reduce((s, r) => s + (r.quantity_liters || 0), 0).toFixed(0)} Liter gesamt
                  </span>
                )}
                <Button
                  size="sm"
                  className="h-7 text-xs bg-amber-500 hover:bg-amber-600 text-white"
                  onClick={() => { setEditFuelReceipt(null); setShowFuelModal(true); }}
                  data-testid="add-fuel-receipt-btn"
                >
                  <Plus className="w-3 h-3 mr-1" /> Neuer Beleg
                </Button>
              </div>
            </div>

            {fuelReceipts.length === 0 && !fuelLoading ? (
              <div className="p-8 text-center text-gray-400">
                <Fuel className="w-8 h-8 mx-auto mb-2 opacity-30" />
                <p className="text-sm">Keine Tankbelege für diesen Auftrag</p>
              </div>
            ) : (
              <div className="divide-y divide-gray-100">
                {fuelReceipts.map((r) => (
                  <div key={r.id} className="p-4 hover:bg-amber-50/30 transition-colors" data-testid={`fuel-receipt-${r.id}`}>
                    <div className="flex items-start justify-between gap-3 flex-wrap">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1 flex-wrap">
                          <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                            r.fuel_type === "diesel" ? "bg-amber-100 text-amber-700" :
                            r.fuel_type === "heizoel_leicht" ? "bg-blue-100 text-blue-700" :
                            "bg-emerald-100 text-emerald-700"
                          }`}>
                            {r.fuel_type_label || r.fuel_type}
                          </span>
                          <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                            r.status === "pending" ? "bg-amber-100 text-amber-700" :
                            r.status === "confirmed" ? "bg-emerald-100 text-emerald-700" :
                            "bg-red-100 text-red-700"
                          }`}>
                            {r.status === "pending" ? "Offen" : r.status === "confirmed" ? "Bestätigt" : "Abgelehnt"}
                          </span>
                          <span className="text-xs text-gray-400">{r.date} {r.time}</span>
                        </div>
                        <p className="text-base font-bold text-gray-900">{r.quantity_liters?.toFixed(1)} Liter</p>
                        <div className="flex items-center gap-3 mt-1 text-xs text-gray-500 flex-wrap">
                          {r.location && <span className="flex items-center gap-1"><MapPin className="w-3 h-3" /> {r.location}</span>}
                          {isAdmin && r.gps_lat && <span className="text-gray-400">{r.gps_lat?.toFixed(4)}, {r.gps_lng?.toFixed(4)}</span>}
                          <span>von {r.created_by}</span>
                          {r.confirmed_by && <span className="text-emerald-600">bestätigt von {r.confirmed_by}</span>}
                        </div>
                        {r.notes && <p className="text-xs text-gray-400 mt-1">{r.notes}</p>}
                      </div>
                      <div className="flex items-center gap-1 shrink-0">
                        {r.status === "pending" && (
                          <>
                            <button onClick={() => confirmFuelReceipt(r.id)} className="p-1.5 rounded-lg bg-emerald-50 hover:bg-emerald-100 text-emerald-600" title="Bestätigen" data-testid={`fuel-confirm-${r.id}`}>
                              <Check className="w-4 h-4" />
                            </button>
                            <button onClick={() => rejectFuelReceipt(r.id)} className="p-1.5 rounded-lg bg-red-50 hover:bg-red-100 text-red-600" title="Ablehnen" data-testid={`fuel-reject-${r.id}`}>
                              <X className="w-4 h-4" />
                            </button>
                          </>
                        )}
                        <button onClick={() => { setEditFuelReceipt(r); setShowFuelModal(true); }} className="p-1.5 rounded-lg bg-gray-50 hover:bg-gray-100 text-gray-600" title="Bearbeiten" data-testid={`fuel-edit-${r.id}`}>
                          <Pencil className="w-4 h-4" />
                        </button>
                        <button onClick={() => openFuelPdf(r.id)} className="p-1.5 rounded-lg bg-gray-50 hover:bg-gray-100 text-gray-600" title="PDF" data-testid={`fuel-pdf-${r.id}`}>
                          <Download className="w-4 h-4" />
                        </button>
                        <button onClick={() => deleteFuelReceipt(r.id)} className="p-1.5 rounded-lg bg-gray-50 hover:bg-gray-100 text-red-400" title="Löschen" data-testid={`fuel-delete-${r.id}`}>
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Fuel Receipt Modal */}
          {showFuelModal && (
            <FuelReceiptModal
              receipt={editFuelReceipt}
              orderPk={pk}
              orderName={`${order?.order_no} - ${order?.event || order?.contact_name || ""}`}
              onClose={() => { setShowFuelModal(false); setEditFuelReceipt(null); }}
              onSave={() => { setShowFuelModal(false); setEditFuelReceipt(null); fetchFuelReceipts(); }}
            />
          )}
        </div>
      </main>
    </div>
  );
}


const FUEL_TYPES_OPTIONS = [
  { value: "diesel", label: "Diesel" },
  { value: "heizoel_leicht", label: "Heizöl Leicht" },
  { value: "hvo", label: "HVO" },
];

function FuelReceiptModal({ receipt, orderPk, orderName, onClose, onSave }) {
  const [form, setForm] = useState({
    fuel_type: receipt?.fuel_type || "diesel",
    quantity_liters: receipt?.quantity_liters || "",
    date: receipt?.date || new Date().toISOString().split("T")[0],
    time: receipt?.time || new Date().toTimeString().slice(0, 5),
    location: receipt?.location || "",
    notes: receipt?.notes || "",
  });
  const [saving, setSaving] = useState(false);

  const handleSave = async () => {
    if (!form.quantity_liters) { toast.error("Bitte Menge eingeben"); return; }
    setSaving(true);
    try {
      if (receipt) {
        await api.put(`/fuel-receipts/${receipt.id}`, form);
        toast.success("Beleg aktualisiert");
      } else {
        await api.post("/fuel-receipts", {
          ...form,
          quantity_liters: parseFloat(form.quantity_liters),
          order_pk: orderPk,
          order_name: orderName,
        });
        toast.success("Beleg erstellt");
      }
      onSave();
    } catch (err) {
      toast.error(typeof err?.response?.data?.detail === "string" ? err.response.data.detail : "Fehler");
    } finally { setSaving(false); }
  };

  return (
    <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-white rounded-xl p-6 w-full max-w-md max-h-[90vh] overflow-y-auto" onClick={e => e.stopPropagation()} data-testid="fuel-receipt-modal">
        <h2 className="text-lg font-bold text-gray-900 mb-1">{receipt ? "Beleg bearbeiten" : "Neuer Tankbeleg"}</h2>
        <p className="text-sm text-gray-500 mb-4">Auftrag: {orderName}</p>
        <div className="space-y-3">
          <div>
            <Label className="text-sm text-gray-600">Kraftstoffart</Label>
            <select value={form.fuel_type} onChange={e => setForm(f => ({ ...f, fuel_type: e.target.value }))} className="w-full mt-1 border rounded-lg px-3 py-2 text-sm" data-testid="fuel-modal-type">
              {FUEL_TYPES_OPTIONS.map(t => (
                <option key={t.value} value={t.value}>{t.label}</option>
              ))}
            </select>
          </div>
          <div>
            <Label className="text-sm text-gray-600">Menge (Liter)</Label>
            <Input type="number" step="0.1" value={form.quantity_liters} onChange={e => setForm(f => ({ ...f, quantity_liters: e.target.value }))} placeholder="z.B. 150.5" className="mt-1" data-testid="fuel-modal-qty" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label className="text-sm text-gray-600">Datum</Label>
              <Input type="date" value={form.date} onChange={e => setForm(f => ({ ...f, date: e.target.value }))} className="mt-1" data-testid="fuel-modal-date" />
            </div>
            <div>
              <Label className="text-sm text-gray-600">Uhrzeit</Label>
              <Input type="time" value={form.time} onChange={e => setForm(f => ({ ...f, time: e.target.value }))} className="mt-1" data-testid="fuel-modal-time" />
            </div>
          </div>
          <div>
            <Label className="text-sm text-gray-600">Standort</Label>
            <Input value={form.location} onChange={e => setForm(f => ({ ...f, location: e.target.value }))} placeholder="z.B. Baustelle" className="mt-1" data-testid="fuel-modal-location" />
          </div>
          <div>
            <Label className="text-sm text-gray-600">Bemerkung</Label>
            <Input value={form.notes} onChange={e => setForm(f => ({ ...f, notes: e.target.value }))} placeholder="Optional" className="mt-1" data-testid="fuel-modal-notes" />
          </div>
        </div>
        <div className="flex gap-3 mt-5">
          <Button onClick={handleSave} disabled={saving} className="flex-1 bg-amber-500 hover:bg-amber-600 text-white" data-testid="fuel-modal-save">
            {saving ? <Loader2 className="w-4 h-4 mr-1.5 animate-spin" /> : null}
            {receipt ? "Speichern" : "Erstellen"}
          </Button>
          <Button variant="outline" onClick={onClose} className="flex-1">Abbrechen</Button>
        </div>
      </div>
    </div>
  );
}
