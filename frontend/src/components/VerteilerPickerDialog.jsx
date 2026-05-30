/**
 * Verteiler-Picker: Karte mit allen "placed" Verteilern aus einem Auftrag.
 *
 * Use-Case: Trupp A setzt Montags Verteiler, Trupp C misst Donnerstag. Im
 * Messprotokoll-Dialog soll der Pruefer den passenden Verteiler aus der Karte
 * waehlen koennen, statt die Nr. manuell zu tippen.
 *
 * Bei grossen Events (z.B. Rock am Ring, 280+ Verteiler ueber den ganzen Ring
 * verteilt) wird automatisch auf die GPS-Position des Pruefers zentriert und
 * dicht (Zoom 18) reingezoomt. Optional kann der Pruefer per Toggle nur die
 * Verteiler im 200m-Umkreis sehen, statt durch das ganze Eventgelaende zu pannen.
 *
 * Loadt: GET /api/orders/epirent/{orderPk}/assets, filtert auf
 *        asset_type === "Verteiler" und status === "placed".
 *
 * Auswahl liefert via onSelect: { label, plus_code, latitude, longitude, id }.
 */
import { useEffect, useState, useMemo, useRef } from "react";
import { MapContainer, Marker, Popup, Circle, useMap } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import MapTileLayer from "./MapTileLayer";
import AssetEditDialog from "./AssetEditDialog";
import { OpenLocationCode } from "open-location-code";
import { X, MapPin, Plug, Crosshair, Loader2, Pencil } from "lucide-react";
import { Button } from "./ui/button";
import api from "../lib/api";
import { toast } from "sonner";

// Lokal definiert, damit der Picker nicht auf Props vom Aufrufer angewiesen ist
// (MessprotokollDialog ist generisch, soll keine OrderDetailPage-Internals durchreichen).
const ASSET_TYPES_LOCAL = [
  { value: "Lichtmast" }, { value: "Stromerzeuger" }, { value: "Verteiler" },
  { value: "Tank" }, { value: "Netzwerk" }, { value: "Sonstiges" },
];
const olcLocal = new OpenLocationCode();
const encodePlusCodeLocal = (lat, lng) => {
  try { return olcLocal.encode(lat, lng, 10); } catch { return ""; }
};

// Force size recalc when MapContainer is rendered inside a modal
// (sonst bleibt die Map weiß, weil das Layout beim Mounten 0px Höhe hat).
function InvalidateOnMount() {
  const map = useMap();
  useEffect(() => {
    const timers = [50, 200, 500, 1000].map((t) => setTimeout(() => map.invalidateSize(), t));
    return () => timers.forEach(clearTimeout);
  }, [map]);
  return null;
}

// Recenter map once a GPS fix is available. Wir setzen nur EINMAL beim ersten
// Fix - sonst kaempft das Recentering gegen den manuellen Pan/Zoom des Users.
function RecenterOnFirstFix({ lat, lng, zoom = 18 }) {
  const map = useMap();
  const didRecenterRef = useRef(false);
  useEffect(() => {
    if (didRecenterRef.current) return;
    if (lat == null || lng == null) return;
    map.setView([lat, lng], zoom, { animate: true });
    didRecenterRef.current = true;
  }, [lat, lng, zoom, map]);
  return null;
}

const verteilerIcon = (selected) =>
  L.divIcon({
    className: "verteiler-marker",
    html: `<div style="width:22px;height:22px;background:${selected ? "#7C3AED" : "#FB923C"};border-radius:50%;border:3px solid white;box-shadow:0 2px 6px rgba(0,0,0,0.4);display:flex;align-items:center;justify-content:center;font-size:11px;color:white;font-weight:bold;">V</div>`,
    iconSize: [22, 22],
    iconAnchor: [11, 11],
  });

const userIcon = L.divIcon({
  className: "user-marker",
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

export default function VerteilerPickerDialog({ orderPk, currentId, onClose, onSelect }) {
  const [assets, setAssets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedId, setSelectedId] = useState(currentId || null);
  const [lat, setLat] = useState(null);
  const [lng, setLng] = useState(null);
  const [accuracy, setAccuracy] = useState(null);
  const [gpsError, setGpsError] = useState(null);
  const [nearbyOnly, setNearbyOnly] = useState(true);
  const [radius, setRadius] = useState(200); // Meter
  const [editingAsset, setEditingAsset] = useState(null);
  const watchIdRef = useRef(null);

  // Assets laden
  const reloadAssets = async () => {
    try {
      const res = await api.get(`/orders/epirent/${orderPk}/assets`);
      const verteiler = (res.data?.assets || []).filter(
        (a) => (a.asset_type || "").toLowerCase() === "verteiler"
          && (a.status || "placed") === "placed"
          && a.latitude != null && a.longitude != null,
      );
      setAssets(verteiler);
    } catch {
      toast.error("Verteiler konnten nicht geladen werden");
    }
  };

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await api.get(`/orders/epirent/${orderPk}/assets`);
        if (cancelled) return;
        const verteiler = (res.data?.assets || []).filter(
          (a) => (a.asset_type || "").toLowerCase() === "verteiler"
            && (a.status || "placed") === "placed"
            && a.latitude != null && a.longitude != null,
        );
        setAssets(verteiler);
      } catch {
        toast.error("Verteiler konnten nicht geladen werden");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [orderPk]);

  // GPS watch
  useEffect(() => {
    if (!navigator.geolocation) {
      setGpsError("Geolocation nicht verfügbar");
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

  // Marker, die wir tatsaechlich zeichnen (Nearby-Toggle reduziert auf Umkreis)
  const visibleAssets = useMemo(() => {
    if (!nearbyOnly || lat == null || lng == null) return assets;
    return assets.filter(
      (a) => haversineM(lat, lng, Number(a.latitude), Number(a.longitude)) <= radius,
    );
  }, [assets, nearbyOnly, lat, lng, radius]);

  const center = useMemo(() => {
    if (lat != null && lng != null) return [lat, lng];
    if (assets.length === 0) return [51.1657, 10.4515];
    const la = assets.reduce((s, a) => s + Number(a.latitude), 0) / assets.length;
    const lo = assets.reduce((s, a) => s + Number(a.longitude), 0) / assets.length;
    return [la, lo];
  }, [assets, lat, lng]);

  const initialZoom = lat != null ? 18 : (assets.length === 1 ? 17 : 14);
  const selected = assets.find((a) => a.id === selectedId);

  const confirm = () => {
    if (!selected) return;
    onSelect({
      id: selected.id,
      label: selected.label || "Verteiler",
      plus_code: selected.plus_code || "",
      latitude: selected.latitude,
      longitude: selected.longitude,
    });
    onClose?.();
  };

  return (
    <div className="fixed inset-0 z-[100] bg-black/50 flex items-center justify-center p-4" data-testid="verteiler-picker">
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-3xl max-h-[90vh] flex flex-col">
        <div className="px-5 py-3 border-b border-gray-100 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <MapPin className="w-5 h-5 text-orange-600" />
            <h2 className="text-base font-bold text-gray-900">Verteiler auswählen</h2>
            <span className="text-xs text-gray-400">
              {nearbyOnly && lat != null
                ? `${visibleAssets.length} im Umkreis · ${assets.length} insgesamt`
                : `${assets.length} platzierte Verteiler im Auftrag`}
            </span>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-700" data-testid="verteiler-picker-close">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* GPS + Nearby Toolbar */}
        <div className="px-5 py-2 border-b border-gray-100 bg-gray-50/60 flex items-center gap-3 flex-wrap text-xs">
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
          <label className="flex items-center gap-2 cursor-pointer select-none ml-auto">
            <input
              type="checkbox"
              checked={nearbyOnly}
              onChange={(e) => setNearbyOnly(e.target.checked)}
              disabled={lat == null}
              className="w-3.5 h-3.5 accent-fuchsia-600"
              data-testid="verteiler-picker-nearby-toggle"
            />
            <span className={lat == null ? "text-gray-400" : "text-gray-700"}>Nur im Umkreis</span>
          </label>
          {nearbyOnly && lat != null && (
            <div className="flex items-center gap-2 min-w-[180px] flex-1">
              <span className="text-gray-500 whitespace-nowrap">Radius</span>
              <input
                type="range" min={50} max={1000} step={10}
                value={radius}
                onChange={(e) => setRadius(Number(e.target.value))}
                className="flex-1 accent-fuchsia-600"
                data-testid="verteiler-picker-radius"
              />
              <span className="font-mono w-14 text-right">{radius}m</span>
            </div>
          )}
        </div>

        {/* Map */}
        <div className="relative h-[60vh] max-h-[560px] min-h-[360px]">
          {loading ? (
            <div className="absolute inset-0 flex items-center justify-center text-sm text-gray-400">Lade Verteiler...</div>
          ) : assets.length === 0 ? (
            <div className="absolute inset-0 flex flex-col items-center justify-center text-center text-gray-500 p-8">
              <Plug className="w-10 h-10 text-gray-300 mb-3" />
              <p className="text-sm font-medium">Keine platzierten Verteiler in diesem Auftrag</p>
              <p className="text-xs text-gray-400 mt-1">Trupp A muss die Verteiler zuerst auf der Karte positionieren.</p>
            </div>
          ) : (
            <MapContainer
              center={center}
              zoom={initialZoom}
              style={{ height: "100%", width: "100%" }}
              scrollWheelZoom
            >
              <InvalidateOnMount />
              <RecenterOnFirstFix lat={lat} lng={lng} zoom={18} />
              <MapTileLayer />
              {lat != null && lng != null && (
                <>
                  <Marker position={[lat, lng]} icon={userIcon} />
                  {nearbyOnly && (
                    <Circle
                      center={[lat, lng]}
                      radius={radius}
                      pathOptions={{ color: "#7C3AED", fillColor: "#7C3AED", fillOpacity: 0.06, weight: 1.5 }}
                    />
                  )}
                </>
              )}
              {visibleAssets.map((a) => (
                <Marker
                  key={a.id}
                  position={[Number(a.latitude), Number(a.longitude)]}
                  icon={verteilerIcon(a.id === selectedId)}
                  eventHandlers={{ click: () => setSelectedId(a.id) }}
                >
                  <Popup>
                    <div className="text-xs">
                      <div className="font-semibold text-gray-900">{a.label || "Verteiler"}</div>
                      {a.plus_code && <div className="text-gray-500 mt-0.5">Plus: {a.plus_code}</div>}
                      <div className="mt-1.5 flex items-center gap-3">
                        <button
                          onClick={() => setSelectedId(a.id)}
                          className="text-fuchsia-600 hover:text-fuchsia-800 font-medium"
                          data-testid={`verteiler-popup-select-${a.id}`}
                        >
                          Auswählen
                        </button>
                        <button
                          onClick={() => setEditingAsset(a)}
                          className="text-gray-500 hover:text-gray-800 font-medium inline-flex items-center gap-1"
                          data-testid={`verteiler-popup-edit-${a.id}`}
                        >
                          <Pencil className="w-3 h-3" />
                          Bearbeiten
                        </button>
                      </div>
                    </div>
                  </Popup>
                </Marker>
              ))}
            </MapContainer>
          )}
        </div>

        {/* Footer */}
        <div className="px-5 py-3 border-t border-gray-100 flex items-center justify-between">
          <div className="text-sm">
            {selected ? (
              <span className="text-gray-700">
                Ausgewählt: <span className="font-semibold text-fuchsia-700">{selected.label}</span>
                {selected.plus_code && <span className="text-gray-400 ml-2">({selected.plus_code})</span>}
              </span>
            ) : (
              <span className="text-gray-400">Marker auf der Karte anklicken</span>
            )}
          </div>
          <div className="flex gap-2">
            <Button variant="outline" onClick={onClose} data-testid="verteiler-picker-cancel">Abbrechen</Button>
            <Button onClick={confirm} disabled={!selected} className="bg-fuchsia-600 hover:bg-fuchsia-700 text-white" data-testid="verteiler-picker-confirm">
              Verknüpfen
            </Button>
          </div>
        </div>
      </div>

      {editingAsset && (
        <AssetEditDialog
          orderPk={orderPk}
          asset={editingAsset}
          assetTypes={ASSET_TYPES_LOCAL}
          encodePlusCode={encodePlusCodeLocal}
          onClose={() => { setEditingAsset(null); reloadAssets(); }}
          onSaved={() => { reloadAssets(); setEditingAsset(null); }}
        />
      )}
    </div>
  );
}
