/**
 * Bulk-Abbau-Karte
 *
 * Use-Case: Trupp C steht am Auftragsende vor 50 Verteilern. Statt jeden
 * einzeln in der Liste anzutippen, oeffnet er diese Karte. Sie zeigt seine
 * Live-GPS-Position + alle "gestellt"-Artikel im konfigurierbaren Radius.
 * Per Tap auf den Marker waehlt er die ab, die er gerade abgebaut hat, und
 * bestaetigt unten alle in einem Rutsch.
 *
 * - Live-GPS via watchPosition (mit Accuracy-Ring)
 * - Radius-Slider 10m bis 1000m (Default 100m)
 * - Marker farbcodiert nach Asset-Typ + Selected-Glow
 * - Bulk-API: POST /api/orders/epirent/{pk}/assets/bulk-dismantle
 */
import { useEffect, useMemo, useRef, useState } from "react";
import { MapContainer, Marker, Circle, useMap } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import MapTileLayer from "./MapTileLayer";
import { X, PackageMinus, Crosshair, Loader2 } from "lucide-react";
import { Button } from "./ui/button";
import api from "../lib/api";
import { toast } from "sonner";

function InvalidateOnMount() {
  const map = useMap();
  useEffect(() => {
    const timers = [50, 200, 500, 1000].map((t) => setTimeout(() => map.invalidateSize(), t));
    return () => timers.forEach(clearTimeout);
  }, [map]);
  return null;
}

function RecenterOn({ lat, lng }) {
  const map = useMap();
  useEffect(() => {
    if (lat != null && lng != null) {
      map.setView([lat, lng], Math.max(map.getZoom(), 17), { animate: true });
    }
  }, [lat, lng, map]);
  return null;
}

const TYPE_COLORS = {
  Stromerzeuger: "#ea580c",
  Verteiler: "#16a34a",
  Lichtmast: "#ca8a04",
  Sonstiges: "#6b7280",
};

const assetIcon = (type, selected) => {
  const color = TYPE_COLORS[type] || "#6b7280";
  const ring = selected ? "box-shadow:0 0 0 4px rgba(220,38,38,0.55),0 2px 6px rgba(0,0,0,0.4);" : "box-shadow:0 2px 6px rgba(0,0,0,0.4);";
  return L.divIcon({
    className: "bulk-dismantle-marker",
    html: `<div style="width:20px;height:20px;background:${color};border-radius:50%;border:3px solid white;${ring}"></div>`,
    iconSize: [20, 20],
    iconAnchor: [10, 10],
  });
};

const userIcon = L.divIcon({
  className: "bulk-user-marker",
  html: `<div style="width:14px;height:14px;background:#2563eb;border-radius:50%;border:2px solid white;box-shadow:0 0 0 3px rgba(37,99,235,0.35);"></div>`,
  iconSize: [14, 14],
  iconAnchor: [7, 7],
});

function haversineM(lat1, lng1, lat2, lng2) {
  const R = 6371000;
  const toRad = (d) => (d * Math.PI) / 180;
  const dLat = toRad(lat2 - lat1);
  const dLng = toRad(lng2 - lng1);
  const a = Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLng / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(a));
}

export default function BulkDismantleMapDialog({ orderPk, onClose, onDone }) {
  const [assets, setAssets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [lat, setLat] = useState(null);
  const [lng, setLng] = useState(null);
  const [accuracy, setAccuracy] = useState(null);
  const [gpsError, setGpsError] = useState(null);
  const [radius, setRadius] = useState(100); // Meter
  const [selected, setSelected] = useState(() => new Set());
  const [submitting, setSubmitting] = useState(false);
  const watchIdRef = useRef(null);

  // Assets laden
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await api.get(`/orders/epirent/${orderPk}/assets`);
        if (cancelled) return;
        const placed = (res.data?.assets || []).filter(
          (a) => (a.status || "placed") === "placed" && a.latitude != null && a.longitude != null,
        );
        setAssets(placed);
      } catch {
        toast.error("Artikel konnten nicht geladen werden");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [orderPk]);

  // GPS watch
  useEffect(() => {
    if (!navigator.geolocation) {
      setGpsError("Geolocation nicht verfuegbar");
      return undefined;
    }
    watchIdRef.current = navigator.geolocation.watchPosition(
      (pos) => {
        setLat(pos.coords.latitude);
        setLng(pos.coords.longitude);
        setAccuracy(pos.coords.accuracy);
        setGpsError(null);
      },
      (err) => setGpsError(err.message || "GPS-Fehler"),
      { enableHighAccuracy: true, maximumAge: 5000, timeout: 15000 },
    );
    return () => {
      if (watchIdRef.current != null) {
        navigator.geolocation.clearWatch(watchIdRef.current);
        watchIdRef.current = null;
      }
    };
  }, []);

  const assetsInRadius = useMemo(() => {
    if (lat == null || lng == null) return [];
    return assets.filter(
      (a) => haversineM(lat, lng, Number(a.latitude), Number(a.longitude)) <= radius,
    );
  }, [assets, lat, lng, radius]);

  const center = useMemo(() => {
    if (lat != null && lng != null) return [lat, lng];
    if (assets.length > 0) {
      const la = assets.reduce((s, a) => s + Number(a.latitude), 0) / assets.length;
      const lo = assets.reduce((s, a) => s + Number(a.longitude), 0) / assets.length;
      return [la, lo];
    }
    return [51.1657, 10.4515];
  }, [lat, lng, assets]);

  const toggle = (id) => {
    setSelected((s) => {
      const next = new Set(s);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const selectAllInRadius = () => {
    setSelected(new Set(assetsInRadius.map((a) => a.id)));
  };

  const clearSelection = () => setSelected(new Set());

  const submit = async () => {
    if (selected.size === 0) return;
    setSubmitting(true);
    try {
      const ids = Array.from(selected);
      const res = await api.post(`/orders/epirent/${orderPk}/assets/bulk-dismantle`, { asset_ids: ids });
      const n = res.data?.updated ?? ids.length;
      toast.success(`${n} Artikel als abgebaut markiert`);
      onDone?.();
      onClose?.();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Bulk-Abbau fehlgeschlagen");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[100] bg-black/60 flex items-center justify-center p-2 sm:p-4" data-testid="bulk-dismantle-dialog">
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-3xl flex flex-col" style={{ maxHeight: "92vh" }}>
        {/* Header */}
        <div className="px-4 py-3 border-b border-gray-100 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <PackageMinus className="w-5 h-5 text-red-600" />
            <div>
              <h2 className="text-base font-bold text-gray-900">Bulk-Abbau</h2>
              <p className="text-[11px] text-gray-500">{assetsInRadius.length} im Umkreis · {assets.length} gestellt insgesamt</p>
            </div>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-700" data-testid="bulk-dismantle-close">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Radius + GPS Status */}
        <div className="px-4 py-2 border-b border-gray-100 bg-gray-50/60 flex items-center gap-3 flex-wrap">
          <div className="flex items-center gap-2 text-xs">
            {lat == null ? (
              <span className="text-amber-600 flex items-center gap-1.5">
                <Loader2 className="w-3 h-3 animate-spin" />
                {gpsError || "Suche GPS-Signal..."}
              </span>
            ) : (
              <span className="text-emerald-700 flex items-center gap-1.5">
                <Crosshair className="w-3 h-3" />
                GPS ±{Math.round(accuracy || 0)}m
              </span>
            )}
          </div>
          <div className="flex items-center gap-2 flex-1 min-w-[180px]">
            <span className="text-xs text-gray-500 whitespace-nowrap">Radius</span>
            <input
              type="range" min={10} max={1000} step={10}
              value={radius}
              onChange={(e) => setRadius(Number(e.target.value))}
              className="flex-1 accent-red-500"
              data-testid="bulk-dismantle-radius"
            />
            <span className="text-xs font-mono w-14 text-right">{radius}m</span>
          </div>
        </div>

        {/* Map */}
        <div className="relative h-[55vh] max-h-[520px] min-h-[340px]">
          {loading ? (
            <div className="absolute inset-0 flex items-center justify-center text-sm text-gray-400">Lade Artikel...</div>
          ) : (
            <MapContainer
              center={center}
              zoom={17}
              style={{ height: "100%", width: "100%" }}
              scrollWheelZoom
            >
              <InvalidateOnMount />
              {lat != null && lng != null && <RecenterOn lat={lat} lng={lng} />}
              <MapTileLayer />
              {lat != null && lng != null && (
                <>
                  <Marker position={[lat, lng]} icon={userIcon} />
                  <Circle
                    center={[lat, lng]}
                    radius={radius}
                    pathOptions={{ color: "#dc2626", fillColor: "#dc2626", fillOpacity: 0.08, weight: 1.5 }}
                  />
                </>
              )}
              {assetsInRadius.map((a) => (
                <Marker
                  key={a.id}
                  position={[Number(a.latitude), Number(a.longitude)]}
                  icon={assetIcon(a.asset_type, selected.has(a.id))}
                  eventHandlers={{ click: () => toggle(a.id) }}
                />
              ))}
            </MapContainer>
          )}
        </div>

        {/* Selection-Toolbar */}
        <div className="px-4 py-2 border-t border-b border-gray-100 bg-gray-50/60 flex items-center justify-between gap-3 flex-wrap">
          <div className="text-xs text-gray-600">
            <span className="font-semibold text-red-700">{selected.size}</span> ausgewählt
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={selectAllInRadius}
              disabled={assetsInRadius.length === 0}
              className="text-xs px-2.5 py-1 rounded-md border border-gray-200 bg-white hover:bg-gray-100 disabled:opacity-40 transition-colors"
              data-testid="bulk-dismantle-select-all"
            >
              Alle im Umkreis
            </button>
            <button
              type="button"
              onClick={clearSelection}
              disabled={selected.size === 0}
              className="text-xs px-2.5 py-1 rounded-md border border-gray-200 bg-white hover:bg-gray-100 disabled:opacity-40 transition-colors"
              data-testid="bulk-dismantle-clear"
            >
              Auswahl leeren
            </button>
          </div>
        </div>

        {/* Footer */}
        <div className="px-4 py-3 flex items-center justify-end gap-2">
          <Button variant="outline" onClick={onClose} data-testid="bulk-dismantle-cancel">
            Abbrechen
          </Button>
          <Button
            onClick={submit}
            disabled={selected.size === 0 || submitting}
            className="bg-red-600 hover:bg-red-700 text-white"
            data-testid="bulk-dismantle-confirm"
          >
            {submitting ? <Loader2 className="w-4 h-4 animate-spin mr-1" /> : <PackageMinus className="w-4 h-4 mr-1" />}
            {selected.size > 0 ? `${selected.size} als abgebaut markieren` : "Marker anklicken"}
          </Button>
        </div>
      </div>
    </div>
  );
}
