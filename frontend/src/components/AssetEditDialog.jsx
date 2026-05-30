/**
 * Asset-Bearbeitungs-Dialog
 *
 * Use-Case: Trupp hat einen Verteiler mit falscher Bezeichnung gespeichert,
 * versehentlichen falschen Typ gewaehlt, oder die Koordinaten manuell
 * verbessern moechte (z.B. nachtraegliche Vermessung). Dialog erlaubt
 * Aenderung von Typ / Bezeichnung / Lat-Lng / Plus-Code in einem Schritt.
 *
 * Plus Code wird automatisch beim Speichern neu berechnet wenn Lat/Lng
 * geaendert wurde (via uebergebene encodePlusCode-Hilfsfunktion).
 */
import { useState } from "react";
import { X, MapPin, Save, Loader2 } from "lucide-react";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import api from "../lib/api";
import { toast } from "sonner";

export default function AssetEditDialog({
  orderPk, asset, assetTypes = [], encodePlusCode, onClose, onSaved,
}) {
  const [assetType, setAssetType] = useState(asset?.asset_type || "");
  const [label, setLabel] = useState(asset?.label || "");
  const [lat, setLat] = useState(asset?.latitude != null ? String(asset.latitude) : "");
  const [lng, setLng] = useState(asset?.longitude != null ? String(asset.longitude) : "");
  const [saving, setSaving] = useState(false);

  if (!asset) return null;

  const handleUseMyPosition = () => {
    if (!navigator.geolocation) {
      toast.error("Geolocation nicht verfügbar");
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setLat(pos.coords.latitude.toFixed(7));
        setLng(pos.coords.longitude.toFixed(7));
        toast.success(`Position übernommen (±${Math.round(pos.coords.accuracy || 0)}m)`);
      },
      (err) => toast.error(err.message || "GPS-Fehler"),
      { enableHighAccuracy: true, timeout: 15000 },
    );
  };

  const submit = async () => {
    const latNum = parseFloat(lat);
    const lngNum = parseFloat(lng);
    if (!assetType.trim()) {
      toast.error("Artikeltyp ist erforderlich");
      return;
    }
    if (!Number.isFinite(latNum) || !Number.isFinite(lngNum)) {
      toast.error("Bitte gültige Koordinaten eingeben");
      return;
    }
    const payload = {
      asset_type: assetType,
      label: label || assetType,
      latitude: latNum,
      longitude: lngNum,
      plus_code: encodePlusCode ? (encodePlusCode(latNum, lngNum) || "") : (asset.plus_code || ""),
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

  return (
    <div className="fixed inset-0 z-[10000] bg-black/60 flex items-center justify-center p-4" data-testid="asset-edit-dialog" onClick={onClose}>
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-md flex flex-col" onClick={(e) => e.stopPropagation()}>
        <div className="px-5 py-3 border-b border-gray-100 flex items-center justify-between">
          <div>
            <h2 className="text-base font-bold text-gray-900">Artikel bearbeiten</h2>
            <p className="text-[11px] text-gray-500">Gestellt von {asset.created_by || "–"}</p>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-700" data-testid="asset-edit-close">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-5 space-y-3">
          <div>
            <Label className="text-xs text-gray-600">Artikeltyp</Label>
            <select
              value={assetType}
              onChange={(e) => setAssetType(e.target.value)}
              className="w-full mt-1 px-3 py-2 border border-gray-200 rounded-lg text-sm bg-white focus:outline-none focus:border-orange-500"
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
                value={lat}
                onChange={(e) => setLat(e.target.value)}
                placeholder="Breitengrad"
                className="font-mono text-xs"
                data-testid="asset-edit-lat"
              />
              <Input
                value={lng}
                onChange={(e) => setLng(e.target.value)}
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
            {lat && lng && encodePlusCode && (() => {
              const code = encodePlusCode(parseFloat(lat), parseFloat(lng));
              return code ? (
                <p className="mt-1 text-[10px] text-gray-400 font-mono">Plus Code: {code}</p>
              ) : null;
            })()}
          </div>
        </div>

        <div className="px-5 py-3 border-t border-gray-100 flex items-center justify-end gap-2">
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
