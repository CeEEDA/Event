import { useState, useEffect, useCallback } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { Logo } from "../components/Logo";
import api, { BACKEND_URL, getErrorMsg } from "../lib/api";
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
  FileDown,
  Percent,
  PackageMinus,
  PackageCheck,
  Clock,
  User,
  Eye,
  FolderOpen,
  ChevronRight,
  ClipboardCheck,
  MessageSquare,
  Send,
  Search,
  Filter,
} from "lucide-react";
import { MapContainer, TileLayer, Marker, Popup, useMap } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import markerIcon2x from "leaflet/dist/images/marker-icon-2x.png";
import markerIcon from "leaflet/dist/images/marker-icon.png";
import markerShadow from "leaflet/dist/images/marker-shadow.png";

delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: markerIcon2x,
  iconUrl: markerIcon,
  shadowUrl: markerShadow,
});
import { OpenLocationCode } from "open-location-code";
import { openExternal } from "../lib/openExternal";
import MessprotokollDialog from "../components/MessprotokollDialog";
import GpsLockPicker from "../components/GpsLockPicker";

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
  { value: "Tank", icon: Fuel, color: "#f97316" },
  { value: "Sonstiges", icon: Box, color: "#f97316" },
];

const assetTypeIcon = (type) => {
  const cfg = ASSET_TYPES.find((t) => t.value === type) || ASSET_TYPES[ASSET_TYPES.length - 1];
  return cfg;
};

const makeAssetIcon = (type) => {
  const icons = {
    Lichtmast: `<circle cx="12" cy="5" r="3" fill="#fff" stroke="#fff" stroke-width="1.5"/><line x1="12" y1="8" x2="12" y2="20" stroke="#fff" stroke-width="2.5" stroke-linecap="round"/>`,
    Stromerzeuger: `<polygon points="13 2 3 14 12 14 11 22 21 10 12 10" fill="none" stroke="#fff" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>`,
    Verteiler: `<line x1="12" y1="3" x2="12" y2="15" stroke="#fff" stroke-width="2.5" stroke-linecap="round"/><line x1="6" y1="9" x2="12" y2="15" stroke="#fff" stroke-width="2" stroke-linecap="round"/><line x1="18" y1="9" x2="12" y2="15" stroke="#fff" stroke-width="2" stroke-linecap="round"/><circle cx="12" cy="18" r="2.5" fill="#fff"/>`,
    Tank: `<path d="M3 22V8a2 2 0 0 1 2-2h6a2 2 0 0 1 2 2v14M3 22h10M13 12h4l3 3v7M13 22h9" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" fill="none"/>`,
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
  const [showGpsPicker, setShowGpsPicker] = useState(false);
  const [addingAsset, setAddingAsset] = useState(false);
  const [assetComment, setAssetComment] = useState("");
  const [assetSearch, setAssetSearch] = useState("");
  const [assetTypeFilter, setAssetTypeFilter] = useState("all");
  const [selectedAsset, setSelectedAsset] = useState(null);
  const [commentDraft, setCommentDraft] = useState("");
  const [commentSaving, setCommentSaving] = useState(false);

  // Reset Kommentar-Entwurf wenn ein anderes Asset geoeffnet wird oder das Modal schliesst.
  useEffect(() => { setCommentDraft(""); }, [selectedAsset?.id]);

  // Tankbelege
  const [fuelReceipts, setFuelReceipts] = useState([]);
  const [fuelLoading, setFuelLoading] = useState(false);
  const [showFuelModal, setShowFuelModal] = useState(false);
  const [editFuelReceipt, setEditFuelReceipt] = useState(null);
  const [showAdjustModal, setShowAdjustModal] = useState(false);
  const [gpsMapReceipt, setGpsMapReceipt] = useState(null);
  const [editingAddress, setEditingAddress] = useState(false);
  const [addressInput, setAddressInput] = useState("");

  // Projektberichte
  const [projectReports, setProjectReports] = useState([]);
  const [projectReportsLoading, setProjectReportsLoading] = useState(false);

  // Messprotokolle
  const [messprotokolle, setMessprotokolle] = useState([]);
  const [showMessprotokollDialog, setShowMessprotokollDialog] = useState(false);
  const [docCount, setDocCount] = useState(0);

  const { isAdmin, user: currentUser } = useAuth();
  const isFreelancer = currentUser?.role === "freelancer";

  const fetchOrder = useCallback(async () => {
    // Guard against invalid pk (e.g. "undefined", non-numeric, NaN) to avoid 422 + iOS crash
    const pkNum = parseInt(pk, 10);
    if (!Number.isFinite(pkNum) || pkNum <= 0) {
      setLoading(false);
      setError("Ungültige Auftragsnummer");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const { data } = await api.get(`/orders/epirent/${pk}`);
      setOrder(data);
      setRadiusInput(String(data.radius_km || 5));
    } catch (err) {
      setError(getErrorMsg(err, "Fehler beim Laden"));
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
    if (isFreelancer) return;
    setFuelLoading(true);
    try {
      const { data } = await api.get(`/fuel-receipts/by-order/${pk}`);
      setFuelReceipts(data || []);
    } catch {
      // silent
    } finally {
      setFuelLoading(false);
    }
  }, [pk, isFreelancer]);

  const fetchProjectReports = useCallback(async () => {
    setProjectReportsLoading(true);
    try {
      const { data } = await api.get(`/project-reports/by-order/${pk}`);
      setProjectReports(data || []);
    } catch {
      // silent
    } finally {
      setProjectReportsLoading(false);
    }
  }, [pk]);

  const fetchMessprotokolle = useCallback(async () => {
    try {
      const { data } = await api.get(`/orders/messprotokoll/${pk}`);
      setMessprotokolle(data || []);
    } catch {
      setMessprotokolle([]);
    }
  }, [pk]);

  useEffect(() => {
    fetchOrder();
    fetchAssets();
    fetchFuelReceipts();
    fetchProjectReports();
    fetchMessprotokolle();
    // Document count
    api.get(`/orders/order-documents/${pk}`).then(r => setDocCount(r.data?.length || 0)).catch(() => {});
  }, [fetchOrder, fetchAssets, fetchFuelReceipts, fetchProjectReports, fetchMessprotokolle]);

  useEffect(() => {
    // fetchGenerators auch ohne center_lat ausfuehren - manuell zugeordnete
    // Generatoren werden auch angezeigt wenn kein Radius gesetzt ist
    fetchGenerators();
  }, [order?.center_lat, order?.radius_km, fetchGenerators]);

  // ── Manuelle Generator-Zuordnung ──
  const [showAddGenModal, setShowAddGenModal] = useState(false);
  const [allGenerators, setAllGenerators] = useState([]);
  const [genSearch, setGenSearch] = useState("");

  const openAddGenModal = async () => {
    setShowAddGenModal(true);
    if (allGenerators.length === 0) {
      try {
        const { data } = await api.get("/generators");
        setAllGenerators(data || []);
      } catch {
        toast.error("Generatoren konnten nicht geladen werden");
      }
    }
  };

  const addManualGenerator = async (genId) => {
    try {
      await api.post(`/orders/epirent/${pk}/generators/manual`, { generator_id: genId });
      toast.success("Generator zugeordnet");
      setShowAddGenModal(false);
      setGenSearch("");
      fetchGenerators();
    } catch (err) {
      toast.error("Zuordnung fehlgeschlagen");
    }
  };

  const removeManualGenerator = async (genId, name) => {
    if (!window.confirm(`Generator "${name}" aus diesem Auftrag entfernen?`)) return;
    try {
      await api.delete(`/orders/epirent/${pk}/generators/manual/${encodeURIComponent(genId)}`);
      toast.success("Zuordnung entfernt");
      fetchGenerators();
    } catch {
      toast.error("Entfernen fehlgeschlagen");
    }
  };

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
    // WhatsApp-Style: Picker-Modal öffnen, dort live nachverfolgen + Pin manuell platzierbar
    setShowGpsPicker(true);
  };

  const onGpsPicked = ({ lat, lng }) => {
    setAssetLat(lat.toFixed(6));
    setAssetLng(lng.toFixed(6));
    setShowGpsPicker(false);
    toast.success("Position übernommen");
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
      const { data: created } = await api.post(`/orders/epirent/${pk}/assets`, {
        asset_type: assetType,
        latitude: lat,
        longitude: lng,
        label: assetLabel || assetType,
        plus_code: plusCode,
      });
      // Falls beim Anlegen direkt ein Kommentar getippt wurde, gleich
      // hinterherschieben - ein Roundtrip mehr ist akzeptabel und haelt das
      // Backend-Modell schlank (Kommentare sind unabhaengiger Sub-Resource).
      const commentText = (assetComment || "").trim();
      if (commentText && created?.id) {
        try {
          await api.post(`/orders/epirent/${pk}/assets/${created.id}/comments`, { text: commentText });
        } catch (err) {
          // Asset ist bereits angelegt - Kommentar nur als Warnung loggen,
          // damit der User trotzdem den Erfolg sieht und manuell nachpflegen kann.
          toast.warning("Artikel angelegt, aber Kommentar nicht gespeichert");
        }
      }
      toast.success("Artikel hinzugefügt");
      setAssetLabel("");
      setAssetLat("");
      setAssetLng("");
      setAssetComment("");
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

  const toggleAssetStatus = async (assetId, e) => {
    e.stopPropagation();
    try {
      const { data } = await api.patch(`/orders/epirent/${pk}/assets/${assetId}/status`);
      toast.success(data.status === "dismantled" ? "Artikel als abgebaut markiert" : "Artikel wieder als gestellt markiert");
      fetchAssets();
    } catch {
      toast.error("Fehler beim Statuswechsel");
    }
  };

  const addAssetComment = async () => {
    if (!selectedAsset) return;
    const text = commentDraft.trim();
    if (!text) return;
    setCommentSaving(true);
    try {
      const { data: comment } = await api.post(
        `/orders/epirent/${pk}/assets/${selectedAsset.id}/comments`,
        { text },
      );
      // Optimistically merge into selectedAsset so the comment appears
      // without a full reload (also keeps the modal open & scrolled).
      setSelectedAsset((prev) => prev ? { ...prev, comments: [...(prev.comments || []), comment] } : prev);
      setCommentDraft("");
      // Refresh the asset list in the background so the badge counter updates.
      fetchAssets();
    } catch (err) {
      toast.error(getErrorMsg(err) || "Kommentar konnte nicht gespeichert werden");
    } finally {
      setCommentSaving(false);
    }
  };

  const deleteAssetComment = async (commentId) => {
    if (!selectedAsset) return;
    if (!window.confirm("Kommentar wirklich loeschen?")) return;
    try {
      await api.delete(`/orders/epirent/${pk}/assets/${selectedAsset.id}/comments/${commentId}`);
      setSelectedAsset((prev) => prev ? { ...prev, comments: (prev.comments || []).filter(c => c.id !== commentId) } : prev);
      fetchAssets();
    } catch (err) {
      toast.error(getErrorMsg(err) || "Kommentar konnte nicht geloescht werden");
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
    openExternal(`${BACKEND_URL}/api/fuel-receipts/${id}/pdf?token=${token}`);
  };

  const downloadAllPdfs = () => {
    const token = localStorage.getItem("token");
    openExternal(`${BACKEND_URL}/api/fuel-receipts/by-order/${pk}/pdf-all?token=${token}`);
  };

  const deleteProjectReport = async (id) => {
    if (!window.confirm("Projektbericht wirklich loeschen?")) return;
    try {
      await api.delete(`/project-reports/${id}`);
      toast.success("Projektbericht geloescht");
      fetchProjectReports();
    } catch { toast.error("Fehler beim Loeschen"); }
  };

  const saveAddress = async () => {
    try {
      await api.post(`/orders/address-override/${pk}`, { address: addressInput });
      toast.success("Adresse gespeichert");
      setEditingAddress(false);
      fetchOrder();
    } catch { toast.error("Fehler"); }
  };

  // Liter summary helpers
  const fuelSummary = fuelReceipts.reduce((acc, r) => {
    acc.total += r.quantity_liters || 0;
    const key = r.fuel_type || "other";
    acc[key] = (acc[key] || 0) + (r.quantity_liters || 0);
    return acc;
  }, { total: 0 });

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
            {isAdmin && (
              <Button
                variant="outline"
                size="sm"
                className="border-fuchsia-300 text-fuchsia-700 hover:bg-fuchsia-50"
                onClick={() => {
                  const token = localStorage.getItem("token");
                  openExternal(`${BACKEND_URL}/api/orders/epirent/${pk}/billing-pdf?token=${token}`);
                }}
                data-testid="billing-pdf-btn"
              >
                <FileDown className="w-4 h-4 mr-1" /> Abrechnung PDF
              </Button>
            )}
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
              {isFreelancer ? (
                <p className="font-semibold text-gray-400 italic">— ausgeblendet —</p>
              ) : (
                <>
                  <p className="font-semibold text-gray-900">{order?.contact_name || "—"}</p>
                  <p className="text-sm text-gray-500 mt-1">Kd.-Nr. {order?.customer_no || "—"}</p>
                </>
              )}
            </div>
            <div className="bg-white rounded-lg border border-gray-200 p-4" data-testid="order-info-address">
              <p className="text-xs text-gray-500 mb-1">Lieferanschrift</p>
              {editingAddress ? (
                <div className="space-y-2">
                  <Input
                    value={addressInput}
                    onChange={e => setAddressInput(e.target.value)}
                    placeholder="z.B. Nuerburgring Nordschleife, 53520 Nuerburg"
                    className="text-sm"
                    data-testid="address-input"
                  />
                  <div className="flex gap-2">
                    <Button size="sm" className="h-7 text-xs bg-fuchsia-600 hover:bg-fuchsia-700 text-white" onClick={saveAddress} data-testid="address-save-btn">
                      Speichern
                    </Button>
                    <Button size="sm" variant="outline" className="h-7 text-xs" onClick={() => setEditingAddress(false)}>
                      Abbrechen
                    </Button>
                  </div>
                </div>
              ) : (
                <div className="flex items-start justify-between gap-2">
                  <p className="font-semibold text-gray-900 flex items-center gap-1">
                    {order?.address ? (
                      <>
                        <MapPin className="w-4 h-4 text-fuchsia-500 flex-shrink-0" />
                        {order.address}
                        {order.address_manual && <span className="text-[10px] text-fuchsia-500 ml-1">(manuell)</span>}
                      </>
                    ) : "—"}
                  </p>
                  {isAdmin && (
                    <button onClick={() => { setAddressInput(order?.address || ""); setEditingAddress(true); }} className="p-1 rounded hover:bg-gray-100 text-gray-400 hover:text-fuchsia-600 shrink-0" title="Adresse bearbeiten" data-testid="address-edit-btn">
                      <Pencil className="w-3.5 h-3.5" />
                    </button>
                  )}
                </div>
              )}
              {center && !editingAddress && (
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
              <div className="p-3 border-b border-gray-100 flex items-center justify-between">
                <h2 className="text-sm font-semibold text-gray-700 flex items-center gap-2">
                  <Zap className="w-4 h-4 text-fuchsia-500" />
                  Generatoren im Radius
                  {genLoading && <Loader2 className="w-3 h-3 animate-spin text-gray-400" />}
                </h2>
                <button
                  onClick={openAddGenModal}
                  className="p-1.5 rounded-md text-fuchsia-600 hover:bg-fuchsia-50 transition-colors"
                  title="Generator manuell zuordnen"
                  data-testid="add-manual-generator-btn"
                >
                  <Plus className="w-4 h-4" />
                </button>
              </div>
              <div className="divide-y divide-gray-100 max-h-[380px] overflow-y-auto">
                {generators.length === 0 && !genLoading && (
                  <div className="p-6 text-center text-gray-400">
                    <Zap className="w-8 h-8 mx-auto mb-2 opacity-30" />
                    <p className="text-sm">Keine Generatoren im Radius</p>
                    <button
                      onClick={openAddGenModal}
                      className="mt-2 text-xs text-fuchsia-600 hover:underline"
                      data-testid="add-manual-generator-empty-btn"
                    >
                      + Manuell zuordnen
                    </button>
                  </div>
                )}
                {generators.map((g) => {
                  const tel = g.latest_telemetry || {};
                  const kw = tel.power_kw != null ? Number(tel.power_kw) : null;
                  const fuel = tel.fuel_level != null ? Number(tel.fuel_level) : null;
                  return (
                  <div
                    key={g.id}
                    className="p-3 hover:bg-gray-50 transition-colors group"
                    data-testid={`gen-item-${g.id}`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex items-start gap-2 min-w-0 flex-1">
                        <div
                          className="w-2.5 h-2.5 rounded-full flex-shrink-0 mt-1.5"
                          style={{ backgroundColor: statusColors[g.status] || "#9CA3AF" }}
                        />
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-1.5 flex-wrap">
                            <p className="text-sm font-medium text-gray-900 truncate">{g.name}</p>
                            {g.is_manual && (
                              <span className="text-[9px] px-1.5 py-0.5 bg-fuchsia-100 text-fuchsia-700 rounded uppercase tracking-wide font-medium flex-shrink-0">
                                Manuell
                              </span>
                            )}
                          </div>
                          <p className="text-xs text-gray-500 truncate">{g.model} · {g.serial_number}</p>
                          {(kw != null || fuel != null) && (
                            <div className="flex items-center gap-3 mt-1">
                              {kw != null && (
                                <span className="text-xs text-fuchsia-600 font-medium" data-testid={`gen-kw-${g.id}`}>
                                  {kw.toFixed(1)} kW
                                </span>
                              )}
                              {fuel != null && (
                                <span className={`text-xs font-medium ${fuel < 20 ? "text-red-500" : fuel < 40 ? "text-amber-500" : "text-emerald-600"}`} data-testid={`gen-fuel-${g.id}`}>
                                  <Droplets className="w-3 h-3 inline mr-0.5 -mt-0.5" />
                                  {fuel.toFixed(0)} %
                                </span>
                              )}
                            </div>
                          )}
                        </div>
                      </div>
                      <div className="flex items-center gap-1 flex-shrink-0">
                        {g.distance_km != null && (
                          <span className="text-xs text-gray-400 whitespace-nowrap">{g.distance_km} km</span>
                        )}
                        <button
                          onClick={(e) => { e.stopPropagation(); window.open(`/generators/${g.id}`, "_blank"); }}
                          className="p-1 text-gray-300 hover:text-fuchsia-600 opacity-0 group-hover:opacity-100 transition-opacity"
                          title="Generator öffnen (neuer Tab)"
                          data-testid={`open-gen-${g.id}`}
                        >
                          <Eye className="w-3.5 h-3.5" />
                        </button>
                        {g.is_manual && (
                          <button
                            onClick={(e) => { e.stopPropagation(); removeManualGenerator(g.id, g.name); }}
                            className="p-1 text-gray-300 hover:text-red-500 opacity-0 group-hover:opacity-100 transition-opacity"
                            title="Zuordnung entfernen"
                            data-testid={`remove-manual-gen-${g.id}`}
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        )}
                      </div>
                    </div>
                  </div>
                );})}
              </div>
            </div>

            {/* Add Generator Modal */}
            {showAddGenModal && (
              <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4" onClick={() => setShowAddGenModal(false)}>
                <div className="bg-white rounded-lg shadow-xl max-w-lg w-full max-h-[80vh] flex flex-col" onClick={(e) => e.stopPropagation()} data-testid="add-gen-modal">
                  <div className="p-4 border-b border-gray-200 flex items-center justify-between">
                    <h3 className="text-sm font-semibold text-gray-800 flex items-center gap-2">
                      <Zap className="w-4 h-4 text-fuchsia-500" />
                      Generator zuordnen
                    </h3>
                    <button onClick={() => setShowAddGenModal(false)} className="text-gray-400 hover:text-gray-700" data-testid="close-add-gen-modal">
                      <X className="w-4 h-4" />
                    </button>
                  </div>
                  <div className="p-4 border-b border-gray-100">
                    <Input
                      autoFocus
                      placeholder="Suchen nach Name, Seriennummer, Modell..."
                      value={genSearch}
                      onChange={(e) => setGenSearch(e.target.value)}
                      className="h-9 text-sm"
                      data-testid="add-gen-search"
                    />
                  </div>
                  <div className="overflow-y-auto flex-1 divide-y divide-gray-100">
                    {(() => {
                      const assigned = new Set(generators.filter(g => g.is_manual).map(g => g.id));
                      const q = genSearch.trim().toLowerCase();
                      const filtered = allGenerators.filter(g => {
                        if (assigned.has(g.id)) return false;
                        if (!q) return true;
                        return (g.name || "").toLowerCase().includes(q) ||
                               (g.serial_number || "").toLowerCase().includes(q) ||
                               (g.model || "").toLowerCase().includes(q);
                      });
                      if (filtered.length === 0) {
                        return <div className="p-8 text-center text-sm text-gray-400">Keine passenden Generatoren</div>;
                      }
                      return filtered.map((g) => (
                        <button
                          key={g.id}
                          onClick={() => addManualGenerator(g.id)}
                          className="w-full p-3 text-left hover:bg-fuchsia-50 transition-colors flex items-center justify-between group"
                          data-testid={`add-gen-option-${g.id}`}
                        >
                          <div className="flex items-center gap-2 min-w-0">
                            <div
                              className="w-2 h-2 rounded-full flex-shrink-0"
                              style={{ backgroundColor: statusColors[g.status] || "#9CA3AF" }}
                            />
                            <div className="min-w-0">
                              <p className="text-sm font-medium text-gray-900 truncate">{g.name}</p>
                              <p className="text-xs text-gray-500 truncate">{g.model} · {g.serial_number}</p>
                            </div>
                          </div>
                          <Plus className="w-4 h-4 text-gray-300 group-hover:text-fuchsia-500 flex-shrink-0" />
                        </button>
                      ));
                    })()}
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Asset Placement Section */}
          <div className="bg-white rounded-lg border border-gray-200" data-testid="assets-section">
            <div className="p-4 border-b border-gray-100 flex items-center justify-between">
              <h2 className="text-sm font-semibold text-gray-700 flex items-center gap-2">
                <MapPin className="w-4 h-4 text-orange-500" />
                Artikel positionieren
              </h2>
              <span className="text-xs text-gray-400">{assets.filter(a => (a.status || "placed") === "placed").length} gestellt · {assets.filter(a => a.status === "dismantled").length} abgebaut</span>
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
              <div className="mt-2.5">
                <label className="block text-xs text-gray-500 mb-1 flex items-center gap-1.5">
                  <MessageSquare className="w-3 h-3 text-orange-500" />
                  Kommentar (optional)
                </label>
                <textarea
                  value={assetComment}
                  onChange={(e) => setAssetComment(e.target.value)}
                  placeholder="z.B. 'Hinter dem Container, Schluessel beim Pfoertner'"
                  rows={2}
                  maxLength={2000}
                  className="w-full px-3 py-1.5 text-sm bg-white border border-gray-200 rounded-lg focus:outline-none focus:border-orange-400 focus:ring-1 focus:ring-orange-200 resize-none"
                  data-testid="asset-comment-create-input"
                />
              </div>
              {assetLat && assetLng && (
                <p className="mt-2 text-xs text-gray-400 font-mono" data-testid="asset-plus-code">
                  Plus Code: {encodePlusCode(parseFloat(assetLat), parseFloat(assetLng)) || "—"}
                </p>
              )}
            </div>

            {/* Assets List */}
            {assets.length > 0 && (() => {
              // Volltextsuche + Typ-Filter. Wir filtern in einem Memo-Step,
              // damit beim Tippen kein Re-Render-Sturm entsteht (assets bleibt
              // unveraendert, nur die Anzeige aendert sich).
              const q = assetSearch.trim().toLowerCase();
              const filtered = assets.filter((a) => {
                if (assetTypeFilter !== "all" && a.asset_type !== assetTypeFilter) return false;
                if (!q) return true;
                const haystack = [
                  a.asset_type, a.label, a.plus_code, a.created_by,
                  a.latitude?.toFixed?.(5), a.longitude?.toFixed?.(5),
                  ...(a.comments || []).map(c => c.text),
                ].filter(Boolean).join(" ").toLowerCase();
                return haystack.includes(q);
              });
              return (
              <>
              {/* Such- & Filterleiste */}
              <div className="px-4 py-3 border-b border-gray-100 bg-white flex flex-wrap items-center gap-2" data-testid="assets-toolbar">
                <div className="relative flex-1 min-w-[220px]">
                  <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-gray-400 pointer-events-none" />
                  <input
                    type="text"
                    value={assetSearch}
                    onChange={(e) => setAssetSearch(e.target.value)}
                    placeholder="Suche: Bezeichnung, Plus Code, Ersteller, Koordinaten oder Kommentar..."
                    className="w-full h-8 pl-8 pr-8 text-sm border border-gray-200 rounded-lg focus:outline-none focus:border-orange-400 focus:ring-1 focus:ring-orange-200"
                    data-testid="asset-search-input"
                  />
                  {assetSearch && (
                    <button
                      type="button"
                      onClick={() => setAssetSearch("")}
                      className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-300 hover:text-gray-500"
                      data-testid="asset-search-clear"
                      aria-label="Suche loeschen"
                    >
                      <X className="w-3.5 h-3.5" />
                    </button>
                  )}
                </div>
                <div className="flex items-center gap-1.5">
                  <Filter className="w-3.5 h-3.5 text-gray-400" />
                  <select
                    value={assetTypeFilter}
                    onChange={(e) => setAssetTypeFilter(e.target.value)}
                    className="h-8 text-sm border border-gray-200 rounded-lg focus:outline-none focus:border-orange-400 bg-white px-2"
                    data-testid="asset-type-filter"
                  >
                    <option value="all">Alle Typen ({assets.length})</option>
                    {ASSET_TYPES.map((t) => {
                      const count = assets.filter(a => a.asset_type === t.value).length;
                      if (count === 0) return null;
                      return <option key={t.value} value={t.value}>{t.value} ({count})</option>;
                    })}
                  </select>
                  {(assetSearch || assetTypeFilter !== "all") && (
                    <button
                      type="button"
                      onClick={() => { setAssetSearch(""); setAssetTypeFilter("all"); }}
                      className="text-xs text-gray-400 hover:text-orange-600 underline ml-1"
                      data-testid="asset-filter-reset"
                    >
                      Zuruecksetzen
                    </button>
                  )}
                </div>
                <span className="text-xs text-gray-400 ml-auto" data-testid="asset-filter-count">
                  {filtered.length === assets.length ? `${assets.length} Artikel` : `${filtered.length} von ${assets.length} angezeigt`}
                </span>
              </div>
              {filtered.length === 0 ? (
                <div className="px-4 py-8 text-center text-sm text-gray-400" data-testid="assets-empty-filtered">
                  Keine Artikel passen zu "{assetSearch}"{assetTypeFilter !== "all" ? ` in Typ "${assetTypeFilter}"` : ""}.
                </div>
              ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm" data-testid="assets-table">
                  <thead>
                    <tr className="bg-gray-50 border-b border-gray-200">
                      <th className="text-left px-4 py-2 font-medium text-gray-600">Typ</th>
                      <th className="text-left px-4 py-2 font-medium text-gray-600">Bezeichnung</th>
                      <th className="text-left px-4 py-2 font-medium text-gray-600">Plus Code</th>
                      <th className="text-left px-4 py-2 font-medium text-gray-600">Koordinaten</th>
                      <th className="text-left px-4 py-2 font-medium text-gray-600">Erstellt von</th>
                      <th className="text-left px-4 py-2 font-medium text-gray-600">Status</th>
                      <th className="w-20"></th>
                    </tr>
                  </thead>
                  <tbody>
                    {[...filtered].sort((a, b) => {
                      const aPlaced = (a.status || "placed") === "placed" ? 0 : 1;
                      const bPlaced = (b.status || "placed") === "placed" ? 0 : 1;
                      return aPlaced - bPlaced;
                    }).map((a) => {
                      const TypeIcon = assetTypeIcon(a.asset_type).icon;
                      const isPlaced = (a.status || "placed") === "placed";
                      return (
                        <tr
                          key={a.id}
                          className={`border-b border-gray-100 cursor-pointer transition-colors ${
                            isPlaced
                              ? "bg-fuchsia-100 border-l-[5px] border-l-fuchsia-500 hover:bg-fuchsia-200"
                              : "bg-white hover:bg-gray-50"
                          }`}
                          data-testid={`asset-row-${a.id}`}
                          onClick={() => setSelectedAsset(a)}
                        >
                          <td className="px-4 py-2.5">
                            <span className="inline-flex items-center gap-1.5 text-orange-600">
                              <TypeIcon className="w-4 h-4" />
                              {a.asset_type}
                            </span>
                          </td>
                          <td className="px-4 py-2.5 font-medium text-gray-900">
                            <div className="flex items-center gap-1.5">
                              <span>{a.label || "—"}</span>
                              {a.comments?.length > 0 && (
                                <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded-full bg-fuchsia-100 text-fuchsia-700 text-[10px] font-semibold" title={`${a.comments.length} Kommentar${a.comments.length === 1 ? "" : "e"}`} data-testid={`asset-comment-count-${a.id}`}>
                                  <MessageSquare className="w-2.5 h-2.5" />
                                  {a.comments.length}
                                </span>
                              )}
                            </div>
                          </td>
                          <td className="px-4 py-2.5 font-mono text-xs text-gray-600">{a.plus_code || "—"}</td>
                          <td className="px-4 py-2.5 font-mono text-xs text-gray-500">
                            {a.latitude.toFixed(5)}, {a.longitude.toFixed(5)}
                          </td>
                          <td className="px-4 py-2.5 text-xs text-gray-400">{a.created_by}</td>
                          <td className="px-4 py-2.5">
                            {isPlaced ? (
                              <button
                                onClick={(e) => toggleAssetStatus(a.id, e)}
                                className="inline-flex items-center gap-1 px-2 py-1 rounded text-xs font-medium bg-fuchsia-100 text-fuchsia-700 hover:bg-fuchsia-200 transition-colors"
                                data-testid={`asset-dismantle-${a.id}`}
                              >
                                <PackageMinus className="w-3 h-3" /> Abgebaut
                              </button>
                            ) : (
                              <button
                                onClick={(e) => toggleAssetStatus(a.id, e)}
                                className="inline-flex items-center gap-1 px-2 py-1 rounded text-xs font-medium bg-gray-100 text-gray-500 hover:bg-gray-200 transition-colors"
                                data-testid={`asset-restore-${a.id}`}
                              >
                                <PackageCheck className="w-3 h-3" /> Gestellt
                              </button>
                            )}
                          </td>
                          <td className="px-2 py-2.5">
                            <button
                              onClick={(e) => { e.stopPropagation(); deleteAsset(a.id); }}
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
              </>
              );
            })()}
          </div>

          {/* Asset Detail Modal */}
          {selectedAsset && (
            <div className="fixed inset-0 z-[9999] bg-black/50 flex items-center justify-center p-4" onClick={() => setSelectedAsset(null)} data-testid="asset-detail-modal">
              <div className="bg-white rounded-xl shadow-2xl max-w-lg w-full max-h-[85vh] overflow-hidden" onClick={(e) => e.stopPropagation()}>
                {/* Header */}
                <div className="flex items-center justify-between px-5 py-4 border-b border-gray-200 bg-gradient-to-r from-fuchsia-600 to-fuchsia-500">
                  <div className="flex items-center gap-3">
                    <div className="w-9 h-9 rounded-lg bg-white/20 flex items-center justify-center">
                      <Eye className="w-5 h-5 text-white" />
                    </div>
                    <div>
                      <h3 className="text-sm font-semibold text-white">{selectedAsset.label || selectedAsset.asset_type}</h3>
                      <p className="text-[11px] text-fuchsia-100">{selectedAsset.asset_type}</p>
                    </div>
                  </div>
                  <button onClick={() => setSelectedAsset(null)} className="text-white/80 hover:text-white p-1" data-testid="close-asset-modal">
                    <X className="w-5 h-5" />
                  </button>
                </div>

                {/* Map */}
                <div className="h-56 w-full">
                  <MapContainer
                    center={[selectedAsset.latitude, selectedAsset.longitude]}
                    zoom={17}
                    style={{ height: "100%", width: "100%" }}
                    scrollWheelZoom={true}
                  >
                    <TileLayer
                      attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a>'
                      url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                    />
                    <Marker position={[selectedAsset.latitude, selectedAsset.longitude]}>
                      <Popup>{selectedAsset.label || selectedAsset.asset_type}</Popup>
                    </Marker>
                  </MapContainer>
                </div>

                {/* Details */}
                <div className="p-5 space-y-3">
                  <div className="grid grid-cols-2 gap-3">
                    <div className="bg-gray-50 rounded-lg p-3">
                      <div className="flex items-center gap-1.5 mb-1">
                        <User className="w-3.5 h-3.5 text-fuchsia-500" />
                        <span className="text-[10px] text-gray-400 font-medium">Gestellt von</span>
                      </div>
                      <p className="text-sm font-medium text-gray-900" data-testid="asset-detail-created-by">{selectedAsset.created_by}</p>
                    </div>
                    <div className="bg-gray-50 rounded-lg p-3">
                      <div className="flex items-center gap-1.5 mb-1">
                        <Clock className="w-3.5 h-3.5 text-fuchsia-500" />
                        <span className="text-[10px] text-gray-400 font-medium">Gestellt am</span>
                      </div>
                      <p className="text-sm font-medium text-gray-900" data-testid="asset-detail-created-at">
                        {selectedAsset.created_at ? new Date(selectedAsset.created_at).toLocaleString("de-DE", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" }) : "—"}
                      </p>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <div className="bg-gray-50 rounded-lg p-3">
                      <div className="flex items-center gap-1.5 mb-1">
                        <MapPin className="w-3.5 h-3.5 text-fuchsia-500" />
                        <span className="text-[10px] text-gray-400 font-medium">Koordinaten</span>
                      </div>
                      <p className="text-xs font-mono text-gray-700" data-testid="asset-detail-coords">{selectedAsset.latitude.toFixed(6)}, {selectedAsset.longitude.toFixed(6)}</p>
                      {selectedAsset.plus_code && <p className="text-[10px] font-mono text-gray-400 mt-0.5">{selectedAsset.plus_code}</p>}
                    </div>
                    <div className="bg-gray-50 rounded-lg p-3">
                      <div className="flex items-center gap-1.5 mb-1">
                        {(selectedAsset.status || "placed") === "placed" ? (
                          <PackageCheck className="w-3.5 h-3.5 text-fuchsia-500" />
                        ) : (
                          <PackageMinus className="w-3.5 h-3.5 text-gray-400" />
                        )}
                        <span className="text-[10px] text-gray-400 font-medium">Status</span>
                      </div>
                      {(selectedAsset.status || "placed") === "placed" ? (
                        <p className="text-sm font-medium text-fuchsia-700">Gestellt</p>
                      ) : (
                        <>
                          <p className="text-sm font-medium text-gray-500">Abgebaut</p>
                          {selectedAsset.dismantled_by && (
                            <p className="text-[10px] text-gray-400 mt-0.5">
                              von {selectedAsset.dismantled_by}
                              {selectedAsset.dismantled_at && ` am ${new Date(selectedAsset.dismantled_at).toLocaleString("de-DE", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" })}`}
                            </p>
                          )}
                        </>
                      )}
                    </div>
                  </div>

                  {/* Open in Google Maps */}
                  <a
                    href={`https://www.google.com/maps?q=${selectedAsset.latitude},${selectedAsset.longitude}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center justify-center gap-2 w-full px-4 py-2.5 bg-fuchsia-50 text-fuchsia-700 rounded-lg text-sm font-medium hover:bg-fuchsia-100 transition-colors"
                    data-testid="asset-detail-google-maps"
                  >
                    <MapPin className="w-4 h-4" />
                    In Google Maps öffnen
                  </a>

                  {/* Kommentare */}
                  <div className="pt-2 border-t border-gray-100" data-testid="asset-comments-section">
                    <div className="flex items-center gap-2 mb-3">
                      <MessageSquare className="w-4 h-4 text-fuchsia-500" />
                      <h4 className="text-sm font-semibold text-gray-800">
                        Kommentare
                        {selectedAsset.comments?.length > 0 && (
                          <span className="ml-1.5 text-xs text-gray-400 font-normal">({selectedAsset.comments.length})</span>
                        )}
                      </h4>
                    </div>

                    <div className="space-y-2 max-h-56 overflow-y-auto pr-1">
                      {(selectedAsset.comments || []).length === 0 ? (
                        <p className="text-xs text-gray-400 italic py-2" data-testid="asset-comments-empty">
                          Noch keine Kommentare. Schreib den ersten unten.
                        </p>
                      ) : (
                        (selectedAsset.comments || []).map((c) => {
                          const myName = currentUser?.name || currentUser?.email || "";
                          const myId = currentUser?.id || currentUser?.user_id || currentUser?.email || "";
                          const isMine = c.created_by_id === myId || c.created_by === myName;
                          const canDelete = isMine || isAdmin;
                          return (
                            <div key={c.id} className="bg-gray-50 rounded-lg p-2.5 border border-gray-100" data-testid={`asset-comment-${c.id}`}>
                              <div className="flex items-start justify-between gap-2 mb-1">
                                <div className="flex items-center gap-1.5 min-w-0">
                                  <User className="w-3 h-3 text-fuchsia-400 shrink-0" />
                                  <span className="text-[11px] font-medium text-gray-700 truncate">{c.created_by || "—"}</span>
                                  <span className="text-[10px] text-gray-400 whitespace-nowrap">
                                    · {c.created_at ? new Date(c.created_at).toLocaleString("de-DE", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" }) : ""}
                                  </span>
                                </div>
                                {canDelete && (
                                  <button
                                    onClick={() => deleteAssetComment(c.id)}
                                    className="text-gray-300 hover:text-red-500 transition-colors shrink-0 p-0.5"
                                    title="Kommentar loeschen"
                                    data-testid={`asset-comment-delete-${c.id}`}
                                  >
                                    <Trash2 className="w-3 h-3" />
                                  </button>
                                )}
                              </div>
                              <p className="text-xs text-gray-700 whitespace-pre-wrap break-words leading-relaxed pl-4">{c.text}</p>
                            </div>
                          );
                        })
                      )}
                    </div>

                    {/* Eingabe-Form */}
                    <form
                      onSubmit={(e) => { e.preventDefault(); addAssetComment(); }}
                      className="mt-3 flex items-end gap-2"
                    >
                      <textarea
                        value={commentDraft}
                        onChange={(e) => setCommentDraft(e.target.value)}
                        onKeyDown={(e) => {
                          // Cmd/Ctrl+Enter oder Enter (ohne Shift) sendet ab
                          if (e.key === "Enter" && !e.shiftKey) {
                            e.preventDefault();
                            addAssetComment();
                          }
                        }}
                        placeholder="Kommentar schreiben..."
                        rows={2}
                        maxLength={2000}
                        className="flex-1 text-xs px-3 py-2 bg-white border border-gray-200 rounded-lg focus:outline-none focus:border-fuchsia-400 focus:ring-1 focus:ring-fuchsia-200 resize-none"
                        data-testid="asset-comment-input"
                        disabled={commentSaving}
                      />
                      <button
                        type="submit"
                        disabled={commentSaving || !commentDraft.trim()}
                        className="shrink-0 flex items-center justify-center w-9 h-9 bg-fuchsia-500 text-white rounded-lg hover:bg-fuchsia-600 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                        title="Senden (Enter)"
                        data-testid="asset-comment-submit"
                      >
                        {commentSaving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
                      </button>
                    </form>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Dokumentenablage */}
          <div
            className="bg-white rounded-lg border border-gray-200 p-4 cursor-pointer hover:border-fuchsia-300 hover:bg-fuchsia-50/30 transition-colors"
            onClick={() => navigate(`/orders/${pk}/dokumente`)}
            data-testid="documents-card"
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 bg-fuchsia-50 rounded-lg flex items-center justify-center">
                  <FolderOpen className="w-5 h-5 text-fuchsia-600" />
                </div>
                <div>
                  <p className="text-sm font-semibold text-gray-900">Dokumentenablage</p>
                  <p className="text-xs text-gray-500">Lageplan, Fotos & Unterlagen</p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                {docCount > 0 && (
                  <span className="text-xs bg-fuchsia-100 text-fuchsia-700 px-2 py-0.5 rounded-full font-medium">{docCount}</span>
                )}
                <ChevronRight className="w-4 h-4 text-gray-400" />
              </div>
            </div>
          </div>

          {/* Projektberichte Section */}
          <div className="bg-white rounded-lg border border-gray-200" data-testid="project-reports-section">
            <div className="p-4 border-b border-gray-100">
              <div className="flex items-center justify-between flex-wrap gap-2">
                <h2 className="text-sm font-semibold text-gray-700 flex items-center gap-2">
                  <ClipboardList className="w-4 h-4 text-fuchsia-500" />
                  Projektberichte
                  {projectReportsLoading && <Loader2 className="w-3 h-3 animate-spin text-gray-400" />}
                </h2>
                <div className="flex items-center gap-2">
                  {projectReports.length > 0 && (
                    <Button
                      size="sm" variant="outline"
                      className="h-7 text-xs border-gray-300"
                      onClick={() => {
                        const token = localStorage.getItem("token");
                        openExternal(`${BACKEND_URL}/api/orders/epirent/${pk}/billing-pdf?token=${token}`);
                      }}
                      data-testid="reports-download-all-btn"
                    >
                      <FileDown className="w-3 h-3 mr-1" /> Alle PDFs
                    </Button>
                  )}
                  <Button
                    size="sm"
                    className="h-7 text-xs min-w-[150px] bg-fuchsia-600 hover:bg-fuchsia-700 text-white"
                    onClick={() => navigate(`/project-report/new?order_pk=${pk}&order_name=${encodeURIComponent(`${order?.order_no || ""} - ${order?.event || order?.contact_name || ""}`)}`)}
                    data-testid="add-project-report-btn"
                  >
                    <Plus className="w-3 h-3 mr-1" /> Neuer Bericht
                  </Button>
                </div>
              </div>
            </div>

            {projectReports.length === 0 && !projectReportsLoading ? (
              <div className="p-8 text-center text-gray-400">
                <ClipboardList className="w-8 h-8 mx-auto mb-2 opacity-30" />
                <p className="text-sm">Keine Projektberichte fuer diesen Auftrag</p>
              </div>
            ) : (
              <div className="divide-y divide-gray-100">
                {projectReports.map((r) => (
                  <div key={r.id} className="p-4 hover:bg-fuchsia-50/30 transition-colors" data-testid={`project-report-${r.id}`}>
                    <div className="flex items-start justify-between gap-3 flex-wrap">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1 flex-wrap">
                          <span className="text-xs px-2 py-0.5 rounded-full font-medium bg-fuchsia-100 text-fuchsia-700">
                            Projektbericht
                          </span>
                          {r.projektnummer && <span className="text-xs text-gray-400 font-mono">Nr. {r.projektnummer}</span>}
                          <span className="text-xs text-gray-400">{r.projekt_datum}</span>
                        </div>
                        <p className="text-sm font-semibold text-gray-900">
                          {r.kunde_name || "Kein Kunde"} {r.kunde_ort ? `- ${r.kunde_ort}` : ""}
                        </p>
                        <div className="flex items-center gap-3 mt-1 text-xs text-gray-500 flex-wrap">
                          {r.mitarbeiter?.length > 0 && (
                            <span className="flex items-center gap-1">
                              <User className="w-3 h-3" />
                              {r.mitarbeiter.map(m => m.name).filter(Boolean).join(", ") || "Keine MA"}
                            </span>
                          )}
                          {r.work_log?.length > 0 && (
                            <span className="flex items-center gap-1">
                              <Clock className="w-3 h-3" /> {r.work_log.length} Eintraege
                            </span>
                          )}
                          <span>erstellt von {r.created_by}</span>
                          {r.unterschrift_kunde && <span className="text-emerald-600">Kunde unterschrieben</span>}
                        </div>
                      </div>
                      <div className="flex items-center gap-1 shrink-0">
                        {!r.unterschrift_kunde && (
                          <button
                            onClick={() => navigate(`/project-report/${r.id}`)}
                            className="p-1.5 rounded-lg bg-gray-50 hover:bg-gray-100 text-gray-600"
                            title="Bearbeiten"
                            data-testid={`report-edit-${r.id}`}
                          >
                            <Pencil className="w-4 h-4" />
                          </button>
                        )}
                        {r.unterschrift_kunde && (
                          <button
                            onClick={() => navigate(`/project-report/${r.id}`)}
                            className="p-1.5 rounded-lg bg-emerald-50 hover:bg-emerald-100 text-emerald-600"
                            title="Ansehen (gesperrt)"
                            data-testid={`report-view-${r.id}`}
                          >
                            <Eye className="w-4 h-4" />
                          </button>
                        )}
                        <button
                          onClick={() => {
                            const token = localStorage.getItem("token");
                            openExternal(`${BACKEND_URL}/api/project-reports/${r.id}/pdf?token=${token}`);
                          }}
                          className="p-1.5 rounded-lg bg-gray-50 hover:bg-gray-100 text-gray-600"
                          title="PDF herunterladen"
                          data-testid={`report-pdf-${r.id}`}
                        >
                          <FileDown className="w-4 h-4" />
                        </button>
                        {isAdmin && (
                          <button
                            onClick={() => deleteProjectReport(r.id)}
                            className="p-1.5 rounded-lg bg-gray-50 hover:bg-gray-100 text-red-400"
                            title="Loeschen"
                            data-testid={`report-delete-${r.id}`}
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Tankbelege Section */}
          {!isFreelancer && (
          <div className="bg-white rounded-lg border border-gray-200" data-testid="fuel-receipts-section">
            <div className="p-4 border-b border-gray-100">
              <div className="flex items-center justify-between flex-wrap gap-2">
                <h2 className="text-sm font-semibold text-gray-700 flex items-center gap-2">
                  <Fuel className="w-4 h-4 text-amber-500" />
                  Tankbelege
                  {fuelLoading && <Loader2 className="w-3 h-3 animate-spin text-gray-400" />}
                </h2>
                <div className="flex items-center gap-2">
                  {isAdmin && fuelReceipts.length > 0 && (
                    <>
                      <Button
                        size="sm" variant="outline"
                        className="h-7 text-xs border-gray-300"
                        onClick={() => setShowAdjustModal(true)}
                        data-testid="fuel-adjust-btn"
                      >
                        <Percent className="w-3 h-3 mr-1" /> Anpassen
                      </Button>
                      <Button
                        size="sm" variant="outline"
                        className="h-7 text-xs border-gray-300"
                        onClick={downloadAllPdfs}
                        data-testid="fuel-download-all-btn"
                      >
                        <FileDown className="w-3 h-3 mr-1" /> Alle PDFs
                      </Button>
                    </>
                  )}
                  <Button
                    size="sm"
                    className="h-7 text-xs min-w-[150px] bg-amber-500 hover:bg-amber-600 text-white"
                    onClick={() => { setEditFuelReceipt(null); setShowFuelModal(true); }}
                    data-testid="add-fuel-receipt-btn"
                  >
                    <Plus className="w-3 h-3 mr-1" /> Neuer Tankbeleg
                  </Button>
                </div>
              </div>
              {/* Liter Summary */}
              {fuelReceipts.length > 0 && (
                <div className="flex items-center gap-4 mt-2 text-xs flex-wrap">
                  <span className="font-semibold text-gray-700">{fuelSummary.total.toFixed(0)} L gesamt</span>
                  {fuelSummary.diesel > 0 && <span className="text-amber-600">Diesel: {fuelSummary.diesel.toFixed(0)} L</span>}
                  {fuelSummary.heizoel_leicht > 0 && <span className="text-blue-600">HEL: {fuelSummary.heizoel_leicht.toFixed(0)} L</span>}
                  {fuelSummary.hvo > 0 && <span className="text-emerald-600">HVO: {fuelSummary.hvo.toFixed(0)} L</span>}
                </div>
              )}
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
                          {r.beleg_nr && <span className="text-xs text-gray-400 font-mono">Beleg #{r.beleg_nr}</span>}
                          <span className="text-xs text-gray-400">{r.date} {r.time}</span>
                        </div>
                        <p className="text-base font-bold text-gray-900">{r.quantity_liters?.toFixed(1)} Liter</p>
                        <div className="flex items-center gap-3 mt-1 text-xs text-gray-500 flex-wrap">
                          {r.location && <span className="flex items-center gap-1"><MapPin className="w-3 h-3" /> {r.location}</span>}
                          {r.fahrer && <span>Fahrer: {r.fahrer}</span>}
                          {r.abgabe_start && <span>{r.abgabe_start} - {r.abgabe_ende || "?"}</span>}
                          {r.zaehler_nr && <span className="font-mono">Z-Nr: {r.zaehler_nr}</span>}
                          {isAdmin && r.gps_lat && <span className="text-gray-400">{r.gps_lat?.toFixed(4)}, {r.gps_lng?.toFixed(4)}</span>}
                          {!r.fahrer && <span>von {r.created_by}</span>}
                          {r.confirmed_by && <span className="text-emerald-600">bestaetigt von {r.confirmed_by}</span>}
                        </div>
                        {r.notes && <p className="text-xs text-gray-400 mt-1">{r.notes}</p>}
                      </div>
                      <div className="flex items-center gap-1 shrink-0">
                        {isAdmin && r.gps_lat && r.gps_lng && (
                          <button onClick={() => setGpsMapReceipt(r)} className="p-1.5 rounded-lg bg-blue-50 hover:bg-blue-100 text-blue-600" title="GPS-Position" data-testid={`fuel-gps-${r.id}`}>
                            <MapPin className="w-4 h-4" />
                          </button>
                        )}
                        {isAdmin && (
                          <button onClick={() => { setEditFuelReceipt(r); setShowFuelModal(true); }} className="p-1.5 rounded-lg bg-gray-50 hover:bg-gray-100 text-gray-600" title="Bearbeiten" data-testid={`fuel-edit-${r.id}`}>
                            <Pencil className="w-4 h-4" />
                          </button>
                        )}
                        <button onClick={() => openFuelPdf(r.id)} className="p-1.5 rounded-lg bg-gray-50 hover:bg-gray-100 text-gray-600" title="PDF" data-testid={`fuel-pdf-${r.id}`}>
                          <FileDown className="w-4 h-4" />
                        </button>
                        {isAdmin && (
                          <button onClick={() => deleteFuelReceipt(r.id)} className="p-1.5 rounded-lg bg-gray-50 hover:bg-gray-100 text-red-400" title="Loeschen" data-testid={`fuel-delete-${r.id}`}>
                            <Trash2 className="w-4 h-4" />
                          </button>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
          )}

          {/* ═════ Messprotokolle ═════ */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-5">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-3">
                <ClipboardCheck className="w-5 h-5 text-violet-600" />
                <h3 className="text-base font-bold text-gray-900">Messprotokolle</h3>
                {messprotokolle.length > 0 && (
                  <span className="px-2 py-0.5 text-xs font-medium rounded-full bg-violet-100 text-violet-700">{messprotokolle.length}</span>
                )}
              </div>
              <Button
                size="sm"
                onClick={() => setShowMessprotokollDialog(true)}
                className="h-7 text-xs min-w-[150px] bg-fuchsia-600 hover:bg-fuchsia-700 text-white"
                data-testid="messprotokoll-new-btn"
              >
                <Plus className="w-3 h-3 mr-1" /> Neues Messprotokoll
              </Button>
            </div>

            {messprotokolle.length === 0 ? (
              <div className="text-center py-8 text-sm text-gray-400">
                <ClipboardCheck className="w-10 h-10 mx-auto mb-2 text-gray-300" />
                Noch kein Messprotokoll erstellt.
              </div>
            ) : (
              <div className="divide-y divide-gray-100">
                {messprotokolle.map((mp) => (
                  <div key={mp.id} className="flex items-center justify-between py-3" data-testid={`messprotokoll-${mp.id}`}>
                    <div className="flex items-center gap-3 min-w-0">
                      <ClipboardCheck className="w-4 h-4 text-violet-500 flex-shrink-0" />
                      <div className="min-w-0">
                        <div className="text-sm font-medium text-gray-900 truncate">{mp.protokoll_nr}</div>
                        <div className="text-xs text-gray-500">
                          Prüfer: {mp.pruefer_name} · {mp.pruef_datum}
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-1.5">
                      <button
                        onClick={async () => {
                          try {
                            const resp = await api.get(`/orders/order-documents/${pk}/${mp.document_id}/file`, { responseType: "blob" });
                            const url = window.URL.createObjectURL(resp.data);
                            window.open(url, "_blank");
                          } catch { toast.error("PDF nicht gefunden"); }
                        }}
                        className="p-1.5 rounded-lg bg-gray-50 hover:bg-gray-100 text-gray-600"
                        title="PDF öffnen"
                        data-testid={`messprotokoll-open-${mp.id}`}
                      >
                        <FileDown className="w-4 h-4" />
                      </button>
                      {isAdmin && (
                        <button
                          onClick={async () => {
                            if (!window.confirm(`Messprotokoll ${mp.protokoll_nr} wirklich löschen?`)) return;
                            try {
                              await api.delete(`/orders/messprotokoll/${pk}/${mp.id}`);
                              toast.success("Messprotokoll gelöscht");
                              fetchMessprotokolle();
                              setDocCount((c) => Math.max(0, c - 1));
                            } catch (e) {
                              toast.error(e?.response?.data?.detail || "Löschen fehlgeschlagen");
                            }
                          }}
                          className="p-1.5 rounded-lg bg-red-50 hover:bg-red-100 text-red-600"
                          title="Messprotokoll löschen"
                          data-testid={`messprotokoll-delete-${mp.id}`}
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {showMessprotokollDialog && (
            <MessprotokollDialog
              order={{ ...order, primary_key: pk }}
              onClose={() => setShowMessprotokollDialog(false)}
              onSaved={() => { setShowMessprotokollDialog(false); fetchMessprotokolle(); setDocCount((c) => c + 1); }}
            />
          )}

          {/* GPS Lock Picker (WhatsApp-Style Position-Modal) */}
          <GpsLockPicker
            open={showGpsPicker}
            onClose={() => setShowGpsPicker(false)}
            onConfirm={onGpsPicked}
            initialLat={assetLat ? parseFloat(assetLat) : null}
            initialLng={assetLng ? parseFloat(assetLng) : null}
          />

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

          {/* Adjust Modal */}
          {showAdjustModal && (
            <FuelAdjustModal
              orderPk={pk}
              receipts={fuelReceipts}
              onClose={() => setShowAdjustModal(false)}
              onSave={() => { setShowAdjustModal(false); fetchFuelReceipts(); }}
            />
          )}

          {/* GPS Map Modal */}
          {gpsMapReceipt && (
            <GpsMapModal
              receipt={gpsMapReceipt}
              onClose={() => setGpsMapReceipt(null)}
            />
          )}
        </div>
      </main>
    </div>
  );
}


const FUEL_TYPES_OPTIONS = [
  { value: "diesel", label: "Diesel" },
  { value: "heizoel_leicht", label: "HEL schwefelarm" },
  { value: "hvo", label: "HVO" },
];

function FuelReceiptModal({ receipt, orderPk, orderName, onClose, onSave }) {
  const [form, setForm] = useState({
    fuel_type: receipt?.fuel_type || "diesel",
    quantity_liters: receipt?.quantity_liters || "",
    date: receipt?.date || new Date().toISOString().split("T")[0],
    time: receipt?.time || new Date().toTimeString().slice(0, 5),
    location: receipt?.location || "",
    abgabe_start: receipt?.abgabe_start || "",
    abgabe_ende: receipt?.abgabe_ende || "",
    fahrer: receipt?.fahrer || "",
    notes: receipt?.notes || "",
  });
  const [saving, setSaving] = useState(false);

  const handleSave = async () => {
    if (!form.quantity_liters) { toast.error("Bitte Menge eingeben"); return; }
    setSaving(true);
    try {
      const payload = {
        ...form,
        quantity_liters: parseFloat(form.quantity_liters),
      };
      if (receipt) {
        await api.put(`/fuel-receipts/${receipt.id}`, payload);
        toast.success("Beleg aktualisiert");
      } else {
        await api.post("/fuel-receipts", {
          ...payload,
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
            <Label className="text-sm text-gray-600">Menge bei 15 C (Liter)</Label>
            <Input type="number" step="0.1" value={form.quantity_liters} onChange={e => setForm(f => ({ ...f, quantity_liters: e.target.value }))} placeholder="z.B. 183" className="mt-1" data-testid="fuel-modal-qty" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label className="text-sm text-gray-600">Abgabe-Datum</Label>
              <Input type="date" value={form.date} onChange={e => setForm(f => ({ ...f, date: e.target.value }))} className="mt-1" data-testid="fuel-modal-date" />
            </div>
            <div>
              <Label className="text-sm text-gray-600">Uhrzeit</Label>
              <Input type="time" value={form.time} onChange={e => setForm(f => ({ ...f, time: e.target.value }))} className="mt-1" data-testid="fuel-modal-time" />
            </div>
          </div>

          {/* Druckerdaten */}
          <p className="text-xs text-gray-400 pt-2 border-t border-gray-100 font-medium uppercase tracking-wide">Druckerdaten</p>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label className="text-sm text-gray-600">Abgabe-Start</Label>
              <Input type="time" step="1" value={form.abgabe_start} onChange={e => setForm(f => ({ ...f, abgabe_start: e.target.value }))} className="mt-1 font-mono" data-testid="fuel-modal-start" />
            </div>
            <div>
              <Label className="text-sm text-gray-600">Abgabe-Ende</Label>
              <Input type="time" step="1" value={form.abgabe_ende} onChange={e => setForm(f => ({ ...f, abgabe_ende: e.target.value }))} className="mt-1 font-mono" data-testid="fuel-modal-ende" />
            </div>
          </div>

          {/* Manuelle Felder */}
          <p className="text-xs text-gray-400 pt-2 border-t border-gray-100 font-medium uppercase tracking-wide">Manuelle Eingabe</p>
          <div>
            <Label className="text-sm text-gray-600">Standort</Label>
            <Input value={form.location} onChange={e => setForm(f => ({ ...f, location: e.target.value }))} placeholder="z.B. Baustelle" className="mt-1" data-testid="fuel-modal-location" />
          </div>
          <div>
            <Label className="text-sm text-gray-600">Fahrer</Label>
            <Input value={form.fahrer} onChange={e => setForm(f => ({ ...f, fahrer: e.target.value }))} placeholder="z.B. Timo" className="mt-1" data-testid="fuel-modal-fahrer" />
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


function FuelAdjustModal({ orderPk, receipts, onClose, onSave }) {
  const [pct, setPct] = useState(receipts[0]?.adjustment_percent || 0);
  const [saving, setSaving] = useState(false);

  // Calculate original totals (before adjustment)
  const originals = receipts.map(r => ({
    ...r,
    orig: r.original_quantity_liters || r.quantity_liters,
  }));
  const origTotal = originals.reduce((s, r) => s + r.orig, 0);
  const adjustedTotal = origTotal * (1 + pct / 100);

  const byType = originals.reduce((acc, r) => {
    const k = r.fuel_type || "other";
    acc[k] = (acc[k] || 0) + r.orig;
    return acc;
  }, {});

  const handleSave = async () => {
    setSaving(true);
    try {
      await api.post(`/fuel-receipts/by-order/${orderPk}/adjustment`, { adjustment_percent: parseFloat(pct) });
      toast.success("Anpassung gespeichert");
      onSave();
    } catch { toast.error("Fehler"); }
    finally { setSaving(false); }
  };

  const typeLabels = { diesel: "Diesel", heizoel_leicht: "HEL schwefelarm", hvo: "HVO" };

  return (
    <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-white rounded-xl p-6 w-full max-w-md" onClick={e => e.stopPropagation()} data-testid="fuel-adjust-modal">
        <h2 className="text-lg font-bold text-gray-900 mb-1">Liter-Anpassung</h2>
        <p className="text-sm text-gray-500 mb-4">Alle Tankbelege dieses Auftrags prozentual anpassen</p>

        {/* Original totals */}
        <div className="bg-gray-50 rounded-lg p-3 mb-4 space-y-1">
          <div className="flex justify-between text-sm">
            <span className="font-medium text-gray-700">Tatsaechliche Menge gesamt</span>
            <span className="font-bold text-gray-900">{origTotal.toFixed(0)} L</span>
          </div>
          {Object.entries(byType).map(([k, v]) => (
            <div key={k} className="flex justify-between text-xs text-gray-500">
              <span>{typeLabels[k] || k}</span>
              <span>{v.toFixed(0)} L</span>
            </div>
          ))}
        </div>

        {/* Adjustment slider */}
        <div className="mb-4">
          <Label className="text-sm text-gray-600">Anpassung (%)</Label>
          <div className="flex items-center gap-3 mt-1">
            <Input
              type="number" step="0.5" value={pct}
              onChange={e => setPct(e.target.value)}
              className="w-24 font-mono text-center"
              data-testid="fuel-adjust-input"
            />
            <span className="text-sm text-gray-500">%</span>
          </div>
        </div>

        {/* Preview */}
        <div className="bg-amber-50 rounded-lg p-3 mb-4">
          <div className="flex justify-between text-sm">
            <span className="font-medium text-amber-700">Angepasste Menge gesamt</span>
            <span className="font-bold text-amber-900">{adjustedTotal.toFixed(0)} L</span>
          </div>
          <p className="text-xs text-amber-600 mt-1">
            {pct > 0 ? `+${pct}%` : pct < 0 ? `${pct}%` : "Keine Anpassung"} auf alle Belege
          </p>
        </div>

        <div className="flex gap-3">
          <Button onClick={handleSave} disabled={saving} className="flex-1 bg-fuchsia-600 hover:bg-fuchsia-700 text-white" data-testid="fuel-adjust-save">
            {saving ? <Loader2 className="w-4 h-4 mr-1.5 animate-spin" /> : null}
            Speichern
          </Button>
          <Button variant="outline" onClick={onClose} className="flex-1">Abbrechen</Button>
        </div>
      </div>
    </div>
  );
}


function GpsMapModal({ receipt, onClose }) {
  const lat = receipt.gps_lat;
  const lng = receipt.gps_lng;
  const mapUrl = `https://www.openstreetmap.org/export/embed.html?bbox=${lng - 0.005},${lat - 0.003},${lng + 0.005},${lat + 0.003}&layer=mapnik&marker=${lat},${lng}`;

  return (
    <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-white rounded-xl w-full max-w-lg overflow-hidden" onClick={e => e.stopPropagation()} data-testid="gps-map-modal">
        <div className="p-4 border-b border-gray-100">
          <h2 className="text-sm font-semibold text-gray-900 flex items-center gap-2">
            <MapPin className="w-4 h-4 text-blue-500" />
            GPS-Position Tankvorgang
          </h2>
          <p className="text-xs text-gray-500 mt-1">
            Beleg #{receipt.beleg_nr || "—"} | {receipt.date} {receipt.time} | {receipt.fuel_type_label} {receipt.quantity_liters?.toFixed(0)} L
          </p>
          <p className="text-xs font-mono text-gray-400 mt-0.5">{lat?.toFixed(6)}, {lng?.toFixed(6)}</p>
        </div>
        <iframe
          title="GPS Position"
          src={mapUrl}
          className="w-full h-72 border-0"
          loading="lazy"
        />
        <div className="p-3 flex justify-end gap-2">
          <Button
            size="sm" variant="outline"
            onClick={() => openExternal(`https://www.google.com/maps?q=${lat},${lng}`)}
            className="text-xs"
            data-testid="gps-google-maps-btn"
          >
            In Google Maps oeffnen
          </Button>
          <Button size="sm" variant="outline" onClick={onClose} className="text-xs">Schliessen</Button>
        </div>
      </div>
    </div>
  );
}
