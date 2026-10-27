import { MapContainer, Marker } from "react-leaflet";
import L from "leaflet";
import { MapPin } from "lucide-react";
import MapTileLayer from "../MapTileLayer";

// Standort-Karte wie bei Stromerzeugern/Lichtmasten (GeneratorDetailPage): Position = Pi-GPS, sonst Koordinaten am Geraet
export function MBoxStandortKarte({ device }) {
  const pos = device?.position;
  const gps = device?.pi?.gps;
  if (!pos) return null;
  const [lat, lng] = pos;
  const quelle = gps?.fix && gps.lat === lat && gps.lon === lng ? "GPS (Pi)" : "Koordinaten am Gerät";
  return (
    <div className="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden" data-testid="mbox-map">
      <div className="flex items-center justify-between px-5 py-3 border-b border-gray-100 gap-2 flex-wrap">
        <h2 className="text-xs font-bold text-gray-500 uppercase tracking-widest flex items-center gap-2">
          <MapPin className="w-4 h-4 text-fuchsia-500" /> Standort
        </h2>
        <span className="text-xs text-gray-400" data-testid="mbox-map-coords">
          {Number(lat).toFixed(5)}, {Number(lng).toFixed(5)}
          <span className="ml-2">· {quelle}{gps?.fix && gps.ts ? ` · ${new Date(gps.ts).toLocaleString("de-DE")}` : ""}</span>
          <a href={`https://www.google.com/maps?q=${lat},${lng}`} target="_blank" rel="noreferrer" className="ml-2 underline hover:text-fuchsia-600" data-testid="mbox-map-google-link">Google Maps</a>
        </span>
      </div>
      <div style={{ height: 260 }}>
        <MapContainer key={`${lat},${lng}`} center={[lat, lng]} zoom={14} style={{ height: "100%", width: "100%" }} scrollWheelZoom={false}>
          <MapTileLayer />
          <Marker
            position={[lat, lng]}
            icon={L.divIcon({
              className: "custom-marker",
              html: '<div style="width:16px;height:16px;background:#A855F7;border-radius:50%;border:3px solid white;box-shadow:0 2px 6px rgba(0,0,0,0.3)"></div>',
              iconSize: [16, 16],
              iconAnchor: [8, 8],
            })}
          />
        </MapContainer>
      </div>
    </div>
  );
}
