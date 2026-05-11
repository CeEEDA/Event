import { useState, useEffect } from "react";
import { TileLayer, LayersControl, LayerGroup } from "react-leaflet";

/**
 * Globaler Map-Layer-Switcher.
 *
 * - Default: "hybrid" (Esri Sat + transparente Strassen-Labels via Stamen)
 * - Auswahl wird in localStorage unter "mapLayer" gespeichert und gilt damit
 *   ueber alle Karten der App hinweg konsistent. Das ist die einfache Loesung
 *   fuer "alle Karten umstellen" - wenn der User einmal auf OSM zurueckschaltet,
 *   merkt sich das die App in jeder Map.
 * - Andere Komponenten brauchen keinen State - sie rendern einfach
 *   <MapTileLayer/> im MapContainer und der Switcher ist da.
 *
 * Props:
 * - position: "topright" (default) | "topleft" | "bottomright" | "bottomleft"
 * - storageKey: optional, sonst "mapLayer"
 */
export const DEFAULT_MAP_LAYER = "hybrid";

export function getInitialMapLayer(storageKey = "mapLayer") {
  if (typeof window === "undefined") return DEFAULT_MAP_LAYER;
  return localStorage.getItem(storageKey) || DEFAULT_MAP_LAYER;
}

export default function MapTileLayer({ position = "topright", storageKey = "mapLayer" }) {
  const [layer, setLayer] = useState(() => getInitialMapLayer(storageKey));

  useEffect(() => {
    if (typeof window !== "undefined") {
      localStorage.setItem(storageKey, layer);
    }
  }, [layer, storageKey]);

  return (
    <LayersControl position={position}>
      <LayersControl.BaseLayer checked={layer === "osm"} name="Karte (OSM)">
        <TileLayer
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a>'
          eventHandlers={{ add: () => setLayer("osm") }}
        />
      </LayersControl.BaseLayer>
      <LayersControl.BaseLayer checked={layer === "sat"} name="Satellit">
        {/* Esri World Imagery: frei nutzbar ohne API-Key, vergleichbar mit Google Sat */}
        <TileLayer
          url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
          attribution="Tiles &copy; Esri"
          maxZoom={19}
          eventHandlers={{ add: () => setLayer("sat") }}
        />
      </LayersControl.BaseLayer>
      <LayersControl.BaseLayer checked={layer === "hybrid"} name="Hybrid">
        {/* Layer-Group: Satellit + Esri-Labels (Strassen, Orte, Grenzen).
           Stamen-Tiles wurden Ende 2023 eingestellt - jetzt durchgehend Esri. */}
        <LayerGroup>
          <TileLayer
            url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
            attribution="Tiles &copy; Esri"
            maxZoom={19}
            eventHandlers={{ add: () => setLayer("hybrid") }}
          />
          <TileLayer
            url="https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Transportation/MapServer/tile/{z}/{y}/{x}"
            attribution=""
            maxZoom={19}
          />
          <TileLayer
            url="https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}"
            attribution="Labels &copy; Esri"
            maxZoom={19}
          />
        </LayerGroup>
      </LayersControl.BaseLayer>
    </LayersControl>
  );
}
