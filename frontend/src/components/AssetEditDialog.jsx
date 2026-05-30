/**
 * Asset-Bearbeitungs-Dialog
 *
 * Optik analog zum Asset-Detail-Modal (Fuchsia-Gradient-Header, Karte oben mit
 * draggable Pin, Felder darunter). User kann editieren: Typ / Bezeichnung /
 * Position (per Pin-Drag, per Inputs oder per "Meine GPS-Position"). Plus
 * Code wird beim Speichern automatisch neu berechnet.
 */
import { useEffect, useRef, useState } from "react";
import { MapContainer, Marker, useMap } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import MapTileLayer from "./MapTileLayer";
import { X, MapPin, Save, Loader2, Eye, Crosshair } from "lucide-react";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import api from "../lib/api";
import { toast } from "sonner";

function InvalidateOnMount() {
  const map = useMap();
  useEffect(() => {
    const timers = [50, 200, 500].map((t) => setTimeout(() => map.invalidateSize(), t));
    return () => timers.forEach(clearTimeout);
  }, [map]);
  return null;
}

function PanTo({ lat, lng }) {
  const map = useMap();
  useEffect(() => {
    if (lat != null && lng != null) {
      map.setView([lat, lng], map.getZoom(), { animate: true });
    }
  }, [lat, lng, map]);
  return null;
}

const pinIcon = L.icon({
  iconUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
  iconRetinaUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
  shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41],
});

export default function AssetEditDialog({
  orderPk, asset, assetTypes = [], encodePlusCode, onClose, onSaved,
}) {
  const [assetType, setAssetType] = useState(asset?.asset_type || "");
  const [label, setLabel] = useState(asset?.label || "");
  const [lat, setLat] = useState(asset?.latitude != null ? Number(asset.latitude) : null);
  const [lng, setLng] = useState(asset?.longitude != null ? Number(asset.longitude) : null);
  const [saving, setSaving] = useState(false);
  const [recenterKey, setRecenterKey] = useState(0); // trigger PanTo only on programmatic changes
  const markerRef = useRef(null);

  if (!asset) return null;

  const onMarkerDragEnd = () => {
    const m = markerRef.current;
    if (!m) return;
    const pos = m.getLatLng();
    setLat(Number(pos.lat.toFixed(7)));
    setLng(Number(pos.lng.toFixed(7)));
    // Kein recenter beim Drag - User hat die Karte ja gerade selbst bewegt.
  };

  const onLatInput = (v) => {
    const n = parseFloat(v);
    if (Number.isFinite(n)) {
      setLat(n);
      setRecenterKey((k) => k + 1);
    } else if (v === "" || v === "-") {
      setLat(null);
    }
  };
  const onLngInput = (v) => {
    const n = parseFloat(v);
    if (Number.isFinite(n)) {
      setLng(n);
      setRecenterKey((k) => k + 1);
    } else if (v === "" || v === "-") {
      setLng(null);
    }
  };

  const handleUseMyPosition = () => {
    if (!navigator.geolocation) {
      toast.error("Geolocation nicht verfügbar");
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setLat(Number(pos.coords.latitude.toFixed(7)));
        setLng(Number(pos.coords.longitude.toFixed(7)));
        setRecenterKey((k) => k + 1);
        toast.success(`Position übernommen (±${Math.round(pos.coords.accuracy || 0)}m)`);
      },
      (err) => toast.error(err.message || "GPS-Fehler"),
      { enableHighAccuracy: true, timeout: 15000 },
    );
  };

  const submit = async () => {
    if (!assetType.trim()) {
      toast.error("Artikeltyp ist erforderlich");
      return;
    }
    if (!Number.isFinite(lat) || !Number.isFinite(lng)) {
      toast.error("Bitte gültige Koordinaten setzen");
      return;
    }
    const payload = {
      asset_type: assetType,
      label: label || assetType,
      latitude: lat,
      longitude: lng,
      plus_code: encodePlusCode ? (encodePlusCode(lat, lng) || "") : (asset.plus_code || ""),
    };
    setSaving(true);
    try {
      const res = await api.patch(`/orders/epirent/${orderPk}/assets/${asset.id}`, payload);
      toast.success("Artikel aktualisiert");
      onSaved?.(res.data);
      onClose?.();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Speichern fehlgeschlagen");
    } finally {
      setSaving(false);
    }
  };

  const hasGps = Number.isFinite(lat) && Number.isFinite(lng);
  const plusCode = hasGps && encodePlusCode ? encodePlusCode(lat, lng) : "";

  return (
    <div className="fixed inset-0 z-[10000] bg-black/50 flex items-center justify-center p-4" data-testid="asset-edit-dialog" onClick={onClose}>
      <div className="bg-white rounded-xl shadow-2xl max-w-lg w-full max-h-[90vh] flex flex-col overflow-hidden" onClick={(e) => e.stopPropagation()}>

        {/* Header - identisches Styling wie Asset-Detail-Modal */}
        <div className="flex-shrink-0 flex items-center justify-between px-5 py-4 border-b border-gray-200 bg-gradient-to-r from-fuchsia-600 to-fuchsia-500">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-white/20 flex items-center justify-center">
              <Eye className="w-5 h-5 text-white" />
            </div>
            <div>
              <h3 className="text-sm font-semibold text-white">{label || assetType || "Artikel bearbeiten"}</h3>
              <p className="text-[11px] text-fuchsia-100">{assetType || "—"}</p>
            </div>
          </div>
          <button onClick={onClose} className="text-white/80 hover:text-white p-1" data-testid="asset-edit-close">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Body - scrollbar */}
        <div className="flex-1 overflow-y-auto">

          {/* Map mit ziehbarem Pin */}
          {hasGps ? (
            <div className="h-56 w-full relative">
              <MapContainer
                center={[lat, lng]}
                zoom={17}
                style={{ height: "100%", width: "100%" }}
                scrollWheelZoom
              >
                <InvalidateOnMount />
                <PanTo lat={lat} lng={lng} key={recenterKey} />
                <MapTileLayer />
                <Marker
                  position={[lat, lng]}
                  draggable
                  ref={markerRef}
                  eventHandlers={{ dragend: onMarkerDragEnd }}
                  icon={pinIcon}
                />
              </MapContainer>
              <div className="absolute top-2 left-2 z-[400] bg-white/90 backdrop-blur px-2 py-1 rounded-md text-[10px] text-gray-700 font-medium pointer-events-none flex items-center gap-1 shadow">
                <Crosshair className="w-3 h-3 text-fuchsia-600" />
                Pin verschieben zum Positionieren
              </div>
            </div>
          ) : (
            <div className="h-56 w-full flex items-center justify-center bg-gray-50 text-gray-400 text-xs">
              Keine gueltigen Koordinaten - bitte unten eingeben
            </div>
          )}

          {/* Felder */}
          <div className="p-5 space-y-3">
            <div>
              <Label className="text-xs text-gray-600">Artikeltyp</Label>
              <select
                value={assetType}
                onChange={(e) => setAssetType(e.target.value)}
                className="w-full mt-1 px-3 py-2 border border-gray-200 rounded-lg text-sm bg-white focus:outline-none focus:border-fuchsia-500"
                data-testid="asset-edit-type"
              >
                {assetTypes.map((t) => (
                  <option key={t.value || t} value={t.value || t}>{t.value || t}</option>
                ))}
              </select>
            </div>

            <div>
              <Label className="text-xs text-gray-600">Bezeichnung</Label>
              <Input
                value={label}
                onChange={(e) => setLabel(e.target.value)}
                placeholder="z.B. Lichtmast Bühne 1"
                className="mt-1"
                data-testid="asset-edit-label"
              />
            </div>

            <div>
              <Label className="text-xs text-gray-600">Position</Label>
              <div className="flex gap-2 mt-1">
                <Input
                  value={lat ?? ""}
                  onChange={(e) => onLatInput(e.target.value)}
                  placeholder="Breitengrad"
                  className="font-mono text-xs"
                  data-testid="asset-edit-lat"
                />
                <Input
                  value={lng ?? ""}
                  onChange={(e) => onLngInput(e.target.value)}
                  placeholder="Längengrad"
                  className="font-mono text-xs"
                  data-testid="asset-edit-lng"
                />
              </div>
              <button
                type="button"
                onClick={handleUseMyPosition}
                className="mt-2 inline-flex items-center gap-1.5 text-xs text-orange-600 hover:text-orange-700 font-medium"
                data-testid="asset-edit-my-pos"
              >
                <MapPin className="w-3.5 h-3.5" />
                Meine GPS-Position übernehmen
              </button>
              {plusCode && (
                <p className="mt-1 text-[10px] text-gray-400 font-mono">Plus Code: {plusCode}</p>
              )}
            </div>

            {/* Read-only-Infos analog Detail-Modal */}
            <div className="grid grid-cols-2 gap-3 pt-2">
              <div className="bg-gray-50 rounded-lg p-3">
                <span className="text-[10px] text-gray-400 font-medium block mb-1">Gestellt von</span>
                <p className="text-sm font-medium text-gray-900">{asset.created_by || "—"}</p>
              </div>
              <div className="bg-gray-50 rounded-lg p-3">
                <span className="text-[10px] text-gray-400 font-medium block mb-1">Status</span>
                <p className="text-sm font-medium text-gray-900">{(asset.status || "placed") === "placed" ? "Gestellt" : "Abgebaut"}</p>
              </div>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="flex-shrink-0 px-5 py-3 border-t border-gray-100 flex items-center justify-end gap-2">
          <Button variant="outline" onClick={onClose} data-testid="asset-edit-cancel">Abbrechen</Button>
          <Button
            onClick={submit}
            disabled={saving}
            className="bg-fuchsia-600 hover:bg-fuchsia-700 text-white"
            data-testid="asset-edit-save"
          >
            {saving ? <Loader2 className="w-4 h-4 animate-spin mr-1" /> : <Save className="w-4 h-4 mr-1" />}
            Speichern
          </Button>
        </div>
      </div>
    </div>
  );
}
