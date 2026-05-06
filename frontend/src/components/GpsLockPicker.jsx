import { useEffect, useState, useRef } from "react";
import { MapContainer, Marker, useMap } from "react-leaflet";
import MapTileLayer from "./MapTileLayer";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { Button } from "./ui/button";
import { Crosshair, X, MapPin, Loader2 } from "lucide-react";

// Recenter map when target lat/lng changes (e.g. on first GPS fix)
function Recenter({ lat, lng, zoom }) {
  const map = useMap();
  useEffect(() => {
    if (lat != null && lng != null) {
      map.setView([lat, lng], zoom ?? map.getZoom());
    }
  }, [lat, lng, zoom, map]);
  return null;
}

// Force size recalc when MapContainer is rendered inside a modal
// (sonst bleibt die Map weiß, weil das Layout beim Mounten 0px Höhe hat).
function InvalidateOnMount() {
  const map = useMap();
  useEffect(() => {
    // Mehrfach feuern, weil das Modal ggf. später erst seine Endhöhe bekommt.
    const timers = [50, 200, 500].map(t => setTimeout(() => map.invalidateSize(), t));
    return () => timers.forEach(clearTimeout);
  }, [map]);
  return null;
}

/**
 * GPS-Lock-Picker (WhatsApp-Style)
 * - Beobachtet GPS live (watchPosition) und zeigt Genauigkeit als Ring + Badge
 * - Pin ist drag-bar zur Feinjustierung
 * - "Speichern" liefert finale Lat/Lng zurück, "Abbrechen" schließt ohne Übernahme
 */
export default function GpsLockPicker({ open, onClose, onConfirm, initialLat = null, initialLng = null }) {
  const [lat, setLat] = useState(initialLat);
  const [lng, setLng] = useState(initialLng);
  const [accuracy, setAccuracy] = useState(null); // Meter
  const [error, setError] = useState(null);
  const [hasFix, setHasFix] = useState(false);
  const [pinTouched, setPinTouched] = useState(false); // wenn User die Nadel manuell verschoben hat
  const watchIdRef = useRef(null);
  const markerRef = useRef(null);

  // Start / stop watchPosition mit Modal-Lifecycle
  useEffect(() => {
    if (!open) return;
    if (!navigator.geolocation) {
      setError("Geolocation ist auf diesem Gerät nicht verfügbar.");
      return;
    }
    setError(null);
    setHasFix(false);
    setPinTouched(false);
    setAccuracy(null);
    if (initialLat != null && initialLng != null) {
      setLat(initialLat);
      setLng(initialLng);
    }

    const id = navigator.geolocation.watchPosition(
      (pos) => {
        const a = pos.coords.accuracy;
        setAccuracy(a);
        setHasFix(true);
        setError(null);
        // Pin nur automatisch nachführen, solange der User ihn nicht manuell verschoben hat
        setPinTouched(prev => {
          if (!prev) {
            setLat(pos.coords.latitude);
            setLng(pos.coords.longitude);
          }
          return prev;
        });
      },
      (err) => {
        setError(err.message || "Position konnte nicht ermittelt werden.");
      },
      { enableHighAccuracy: true, maximumAge: 0, timeout: 30000 }
    );
    watchIdRef.current = id;

    return () => {
      if (watchIdRef.current != null) {
        navigator.geolocation.clearWatch(watchIdRef.current);
        watchIdRef.current = null;
      }
    };
  }, [open, initialLat, initialLng]);

  if (!open) return null;

  const handleConfirm = () => {
    if (lat == null || lng == null) return;
    onConfirm({ lat: Number(lat), lng: Number(lng), accuracy });
  };

  const recenterOnGps = () => {
    setPinTouched(false);
    // beim nächsten watchPosition-Tick wird der Pin wieder auto-nachgeführt
  };

  // Genauigkeit-Status (WhatsApp-Stil)
  const getAccuracyStatus = () => {
    if (accuracy == null) return { label: "Suche GPS-Signal …", color: "text-gray-500", bg: "bg-gray-100", spinning: true };
    if (accuracy <= 10) return { label: `Sehr genau · ± ${Math.round(accuracy)} m`, color: "text-emerald-700", bg: "bg-emerald-100", spinning: false };
    if (accuracy <= 30) return { label: `Genau · ± ${Math.round(accuracy)} m`, color: "text-emerald-700", bg: "bg-emerald-50", spinning: false };
    if (accuracy <= 80) return { label: `OK · ± ${Math.round(accuracy)} m`, color: "text-amber-700", bg: "bg-amber-100", spinning: true };
    return { label: `Ungenau · ± ${Math.round(accuracy)} m`, color: "text-red-700", bg: "bg-red-100", spinning: true };
  };
  const status = getAccuracyStatus();

  const center = lat != null && lng != null ? [lat, lng] : [51.1657, 10.4515]; // fallback: DE center
  const zoom = hasFix ? 18 : 6;

  return (
    <div
      className="fixed inset-0 z-[1000] flex items-end sm:items-center justify-center bg-black/50 backdrop-blur-sm"
      onClick={onClose}
      data-testid="gps-lock-modal"
    >
      <div
        className="bg-white w-full sm:max-w-lg sm:rounded-2xl rounded-t-2xl shadow-2xl flex flex-col overflow-hidden max-h-[92vh]"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="px-4 py-3 border-b border-gray-200 flex items-center gap-2">
          <Crosshair className="w-5 h-5 text-orange-500 flex-shrink-0" />
          <div className="flex-1 min-w-0">
            <p className="text-sm font-semibold text-gray-900">Position bestimmen</p>
            <p className="text-[11px] text-gray-500">Stecknadel zur Feinjustierung verschieben</p>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 p-1" data-testid="gps-modal-close">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Status Bar */}
        <div className={`px-4 py-2 flex items-center gap-2 ${status.bg}`} data-testid="gps-accuracy-status">
          {status.spinning ? <Loader2 className={`w-4 h-4 animate-spin ${status.color}`} /> : <MapPin className={`w-4 h-4 ${status.color}`} />}
          <span className={`text-xs font-semibold ${status.color}`}>{status.label}</span>
          {pinTouched && (
            <button
              onClick={recenterOnGps}
              className="ml-auto text-[11px] underline text-orange-700 hover:text-orange-900"
              data-testid="gps-recenter-btn"
            >
              Auf GPS zurücksetzen
            </button>
          )}
        </div>

        {/* Map */}
        <div className="relative" style={{ height: 360 }}>
          {error && (
            <div className="absolute inset-x-0 top-0 bg-red-50 border-b border-red-200 px-3 py-2 z-[400] text-xs text-red-700">
              {error}
            </div>
          )}
          <MapContainer center={center} zoom={zoom} scrollWheelZoom style={{ width: "100%", height: "100%" }}>
            <InvalidateOnMount />
            <MapTileLayer />
            {lat != null && lng != null && (
              <>
                <Recenter lat={pinTouched ? null : lat} lng={pinTouched ? null : lng} zoom={hasFix ? 18 : 6} />
                <Marker
                  position={[lat, lng]}
                  draggable
                  ref={markerRef}
                  eventHandlers={{
                    dragend: (e) => {
                      const m = e.target;
                      const p = m.getLatLng();
                      setLat(p.lat);
                      setLng(p.lng);
                      setPinTouched(true);
                    },
                  }}
                />
              </>
            )}
          </MapContainer>
        </div>

        {/* Coords */}
        <div className="px-4 py-2 border-t border-gray-100 bg-gray-50 text-[11px] font-mono text-gray-600 flex items-center justify-between">
          <span>
            {lat != null && lng != null
              ? `${Number(lat).toFixed(6)}, ${Number(lng).toFixed(6)}`
              : "—"}
          </span>
          {pinTouched && <span className="text-orange-600 font-semibold not-italic">manuell verschoben</span>}
        </div>

        {/* Actions */}
        <div className="px-4 py-3 flex items-center gap-2 border-t border-gray-200 bg-white">
          <Button variant="outline" size="sm" onClick={onClose} className="flex-1" data-testid="gps-cancel-btn">
            Abbrechen
          </Button>
          <Button
            size="sm"
            onClick={handleConfirm}
            disabled={lat == null || lng == null}
            className="flex-1 bg-orange-500 hover:bg-orange-600 text-white"
            data-testid="gps-save-btn"
          >
            <MapPin className="w-3.5 h-3.5 mr-1.5" /> Position speichern
          </Button>
        </div>
      </div>
    </div>
  );
}
