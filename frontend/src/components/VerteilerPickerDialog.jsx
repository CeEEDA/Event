/**
 * Verteiler-Picker: Karte mit allen "placed" Verteilern aus einem Auftrag.
 *
 * Use-Case: Trupp A setzt Montags Verteiler, Trupp C misst Donnerstag. Im
 * Messprotokoll-Dialog soll der Pruefer den passenden Verteiler aus der Karte
 * waehlen koennen, statt die Nr. manuell zu tippen.
 *
 * Loadt: GET /api/orders/epirent/{orderPk}/assets, filtert auf
 *        asset_type === "Verteiler" und status === "placed".
 *
 * Auswahl liefert via onSelect: { label, plus_code, latitude, longitude, id }.
 */
import { useEffect, useState, useMemo } from "react";
import { MapContainer, Marker, Popup, useMap } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import MapTileLayer from "./MapTileLayer";
import { X, MapPin, Plug } from "lucide-react";
import { Button } from "./ui/button";
import api from "../lib/api";
import { toast } from "sonner";

// Force size recalc when MapContainer is rendered inside a modal
// (sonst bleibt die Map weiß, weil das Layout beim Mounten 0px Höhe hat).
function InvalidateOnMount() {
  const map = useMap();
  useEffect(() => {
    const timers = [50, 200, 500, 1000].map(t => setTimeout(() => map.invalidateSize(), t));
    return () => timers.forEach(clearTimeout);
  }, [map]);
  return null;
}

const verteilerIcon = (selected) =>
  L.divIcon({
    className: "verteiler-marker",
    html: `<div style="width:22px;height:22px;background:${selected ? "#7C3AED" : "#FB923C"};border-radius:50%;border:3px solid white;box-shadow:0 2px 6px rgba(0,0,0,0.4);display:flex;align-items:center;justify-content:center;font-size:11px;color:white;font-weight:bold;">V</div>`,
    iconSize: [22, 22],
    iconAnchor: [11, 11],
  });

export default function VerteilerPickerDialog({ orderPk, currentId, onClose, onSelect }) {
  const [assets, setAssets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedId, setSelectedId] = useState(currentId || null);

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
      } catch (e) {
        toast.error("Verteiler konnten nicht geladen werden");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [orderPk]);

  const center = useMemo(() => {
    if (assets.length === 0) return [51.1657, 10.4515]; // DE-Mitte als Fallback
    const lat = assets.reduce((s, a) => s + Number(a.latitude), 0) / assets.length;
    const lng = assets.reduce((s, a) => s + Number(a.longitude), 0) / assets.length;
    return [lat, lng];
  }, [assets]);

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
            <span className="text-xs text-gray-400">{assets.length} platzierte Verteiler im Auftrag</span>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-700" data-testid="verteiler-picker-close">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Map - feste Pixel-Hoehe, weil flex-1 + min-h-0 das Leaflet-Container
           auf 0px Hoehe schrumpfen liess (Tailwind min-h-0 ueberschreibt inline
           minHeight) und die Karte dann trotz geladenen Tiles unsichtbar blieb. */}
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
              zoom={assets.length === 1 ? 17 : 14}
              style={{ height: "100%", width: "100%" }}
              scrollWheelZoom={true}
            >
              <InvalidateOnMount />
              <MapTileLayer />
              {assets.map((a) => (
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
                      <button
                        onClick={() => setSelectedId(a.id)}
                        className="mt-1.5 text-fuchsia-600 hover:text-fuchsia-800 font-medium"
                      >
                        Auswählen
                      </button>
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
    </div>
  );
}
