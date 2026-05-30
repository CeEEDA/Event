/**
 * Tank-Status-Seite
 *
 * Use-Case: Tankwagen-Trupp faehrt taeglich die Stromerzeuger ab, erfasst pro
 * Generator den aktuellen Tankstand + Last + Betriebsstunden + Foto. Beim
 * ersten Eintrag muss die Tank-Gesamtgroesse (z.B. 1.000 L) mitgegeben werden,
 * danach uebernimmt das Backend sie automatisch. Ab 2 Readings je Asset wird
 * ein Verbrauch (L/h) berechnet und eine Prognose ausgewiesen.
 *
 * - Erfassen-Tab: Asset-Auswahl per Liste oder GPS-Naehe, Eingabeformular
 * - Prognose-Tab: Liste sortiert nach Kritikalitaet (rot/gelb/gruen)
 * - CSV-Export
 * - Filter: Min/Max Liter, Asset
 *
 * Endpoints: /api/orders/epirent/{pk}/tank-readings[/forecast|/export.csv]
 */
import { useEffect, useMemo, useRef, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { ArrowLeft, Fuel, Crosshair, AlertTriangle, Camera, Trash2, Download, Loader2, ChevronRight, Calendar } from "lucide-react";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import api from "../lib/api";
import { toast } from "sonner";

function haversineM(lat1, lng1, lat2, lng2) {
  if ([lat1, lng1, lat2, lng2].some((v) => v == null || Number.isNaN(v))) return Infinity;
  const R = 6371000;
  const toRad = (d) => (d * Math.PI) / 180;
  const dLat = toRad(lat2 - lat1);
  const dLng = toRad(lng2 - lng1);
  const a = Math.sin(dLat / 2) ** 2 + Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLng / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(a));
}

const CRIT_STYLES = {
  critical: { dot: "bg-red-500", label: "Kritisch", text: "text-red-700", bg: "bg-red-50 border-red-200" },
  warn: { dot: "bg-amber-500", label: "Warnung", text: "text-amber-700", bg: "bg-amber-50 border-amber-200" },
  ok: { dot: "bg-emerald-500", label: "OK", text: "text-emerald-700", bg: "bg-white border-gray-200" },
};

function formatEta(iso) {
  if (!iso) return "–";
  try {
    return new Date(iso).toLocaleString("de-DE", { dateStyle: "short", timeStyle: "short" });
  } catch { return iso; }
}

export default function TankStatusPage() {
  const { pk } = useParams();
  const navigate = useNavigate();

  const [order, setOrder] = useState(null);
  const [stromerzeuger, setStromerzeuger] = useState([]);
  const [readings, setReadings] = useState([]);
  const [forecast, setForecast] = useState([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState("erfassen");

  // Form-State
  const [selectedAsset, setSelectedAsset] = useState(null);
  const [tankSizeL, setTankSizeL] = useState("");
  const [fuelLevelL, setFuelLevelL] = useState("");
  const [loadKw, setLoadKw] = useState("");
  const [runtimeH, setRuntimeH] = useState("");
  const [comment, setComment] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [photoFile, setPhotoFile] = useState(null);

  // GPS
  const [gps, setGps] = useState({ lat: null, lng: null });
  const watchIdRef = useRef(null);

  // Filter
  const [minFuel, setMinFuel] = useState("");
  const [maxFuel, setMaxFuel] = useState("");
  const [onlyCritical, setOnlyCritical] = useState(false);
  const [sortBy, setSortBy] = useState("criticality");

  useEffect(() => {
    if (!navigator.geolocation) return undefined;
    watchIdRef.current = navigator.geolocation.watchPosition(
      (pos) => setGps({ lat: pos.coords.latitude, lng: pos.coords.longitude }),
      () => {},
      { enableHighAccuracy: true, maximumAge: 10000, timeout: 15000 },
    );
    return () => { if (watchIdRef.current != null) navigator.geolocation.clearWatch(watchIdRef.current); };
  }, []);

  const loadAll = async () => {
    setLoading(true);
    try {
      const [orderRes, assetsRes, listRes, fcRes] = await Promise.all([
        api.get(`/orders/epirent/${pk}`),
        api.get(`/orders/epirent/${pk}/assets`),
        api.get(`/orders/epirent/${pk}/tank-readings`),
        api.get(`/orders/epirent/${pk}/tank-readings/forecast`),
      ]);
      setOrder(orderRes.data);
      const ses = (assetsRes.data?.assets || []).filter(
        (a) => (a.asset_type || "").toLowerCase() === "stromerzeuger",
      );
      setStromerzeuger(ses);
      setReadings(listRes.data?.readings || []);
      setForecast(fcRes.data?.forecast || []);
    } catch {
      toast.error("Daten konnten nicht geladen werden");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadAll(); }, [pk]); // eslint-disable-line react-hooks/exhaustive-deps

  // Hat das Asset schon ein Reading? (-> Tankgroesse muss nicht erneut eingegeben werden)
  const lastReadingForAsset = useMemo(() => {
    if (!selectedAsset) return null;
    return readings.find((r) => r.asset_id === selectedAsset.id) || null;
  }, [selectedAsset, readings]);

  const knownTankSize = lastReadingForAsset?.tank_size_l;

  // Sortiere Assets nach GPS-Naehe falls verfuegbar, sonst alphabetisch
  const sortedAssets = useMemo(() => {
    if (gps.lat == null) return [...stromerzeuger].sort((a, b) => (a.label || "").localeCompare(b.label || ""));
    return [...stromerzeuger].sort((a, b) => {
      const da = haversineM(gps.lat, gps.lng, Number(a.latitude), Number(a.longitude));
      const db = haversineM(gps.lat, gps.lng, Number(b.latitude), Number(b.longitude));
      return da - db;
    });
  }, [stromerzeuger, gps]);

  const submitReading = async () => {
    if (!selectedAsset) { toast.error("Bitte Generator waehlen"); return; }
    const fl = parseFloat(fuelLevelL);
    if (!Number.isFinite(fl) || fl < 0) { toast.error("Tankstand in L eingeben"); return; }
    const payload = {
      asset_id: selectedAsset.id,
      fuel_level_l: fl,
      tank_size_l: knownTankSize ? undefined : parseFloat(tankSizeL),
      load_kw: loadKw ? parseFloat(loadKw) : undefined,
      runtime_h: runtimeH ? parseFloat(runtimeH) : undefined,
      comment: comment || "",
      latitude: gps.lat ?? undefined,
      longitude: gps.lng ?? undefined,
    };
    setSubmitting(true);
    try {
      const res = await api.post(`/orders/epirent/${pk}/tank-readings`, payload);
      // Optional Foto hinterher hochladen
      if (photoFile && res.data?.id) {
        const fd = new FormData();
        fd.append("file", photoFile);
        try { await api.post(`/orders/epirent/${pk}/tank-readings/${res.data.id}/photo`, fd, { headers: { "Content-Type": "multipart/form-data" } }); }
        catch { toast.warning("Reading gespeichert, Foto-Upload fehlgeschlagen"); }
      }
      toast.success("Tankstand erfasst");
      // Reset
      setFuelLevelL("");
      setLoadKw("");
      setRuntimeH("");
      setComment("");
      setPhotoFile(null);
      setTankSizeL("");
      await loadAll();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Speichern fehlgeschlagen");
    } finally {
      setSubmitting(false);
    }
  };

  const deleteReading = async (id) => {
    if (!window.confirm("Reading wirklich loeschen?")) return;
    try {
      await api.delete(`/orders/epirent/${pk}/tank-readings/${id}`);
      toast.success("Geloescht");
      loadAll();
    } catch { toast.error("Loeschen fehlgeschlagen"); }
  };

  const exportCsv = () => {
    const url = `${process.env.REACT_APP_BACKEND_URL}/api/orders/epirent/${pk}/tank-readings/export.csv`;
    // Mit Token via fetch -> blob -> download
    fetch(url, { headers: { Authorization: `Bearer ${localStorage.getItem("token") || ""}` } })
      .then((r) => r.blob())
      .then((blob) => {
        const a = document.createElement("a");
        a.href = window.URL.createObjectURL(blob);
        a.download = `tankstatus_${pk}.csv`;
        a.click();
        window.URL.revokeObjectURL(a.href);
      })
      .catch(() => toast.error("CSV-Export fehlgeschlagen"));
  };

  // Forecast filtern + sortieren
  const visibleForecast = useMemo(() => {
    let out = [...forecast];
    if (onlyCritical) out = out.filter((f) => f.criticality === "critical" || f.criticality === "warn");
    if (minFuel) out = out.filter((f) => (f.current_fuel_l ?? 0) >= parseFloat(minFuel));
    if (maxFuel) out = out.filter((f) => (f.current_fuel_l ?? 0) <= parseFloat(maxFuel));
    if (sortBy === "fuel_asc") out.sort((a, b) => (a.current_fuel_l ?? 1e9) - (b.current_fuel_l ?? 1e9));
    else if (sortBy === "hours_asc") out.sort((a, b) => (a.hours_remaining ?? 1e9) - (b.hours_remaining ?? 1e9));
    else if (sortBy === "label") out.sort((a, b) => (a.asset_label || "").localeCompare(b.asset_label || ""));
    // default "criticality" -> Backend liefert schon sortiert
    return out;
  }, [forecast, onlyCritical, minFuel, maxFuel, sortBy]);

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-6xl mx-auto px-4 py-6">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <button onClick={() => navigate(`/orders/${pk}`)} className="inline-flex items-center text-sm text-fuchsia-600 hover:text-fuchsia-800" data-testid="back-to-order">
            <ArrowLeft className="w-4 h-4 mr-1" />
            Zurueck zum Auftrag
          </button>
          <div className="flex items-center gap-2 text-xs text-gray-500">
            {gps.lat != null ? (
              <span className="text-emerald-600 inline-flex items-center gap-1"><Crosshair className="w-3 h-3" /> GPS aktiv</span>
            ) : (
              <span className="text-gray-400">kein GPS</span>
            )}
          </div>
        </div>

        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5 mb-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-amber-50 text-amber-600 flex items-center justify-center">
              <Fuel className="w-5 h-5" />
            </div>
            <div>
              <h1 className="text-lg font-bold text-gray-900">Tankstatus</h1>
              <p className="text-xs text-gray-500">
                {order?.order_no || pk} · {stromerzeuger.length} Stromerzeuger · {readings.length} Readings
              </p>
            </div>
            <div className="ml-auto">
              <Button variant="outline" onClick={exportCsv} className="text-xs" data-testid="export-csv-btn">
                <Download className="w-3.5 h-3.5 mr-1" /> CSV-Export
              </Button>
            </div>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex gap-2 mb-4">
          {[
            { k: "erfassen", l: "Erfassen" },
            { k: "uebersicht", l: `Prognose & Uebersicht (${forecast.length})` },
            { k: "historie", l: `Historie (${readings.length})` },
          ].map((t) => (
            <button
              key={t.k}
              onClick={() => setTab(t.k)}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${tab === t.k ? "bg-amber-500 text-white" : "bg-white text-gray-600 hover:bg-gray-100"}`}
              data-testid={`tank-tab-${t.k}`}
            >
              {t.l}
            </button>
          ))}
        </div>

        {/* ERFASSEN */}
        {tab === "erfassen" && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Asset-Liste */}
            <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-4">
              <h2 className="text-sm font-semibold text-gray-900 mb-2">Generator wählen</h2>
              <p className="text-[11px] text-gray-400 mb-2">{gps.lat != null ? "Nach GPS-Nähe sortiert" : "Alphabetisch (GPS nicht verfügbar)"}</p>
              <div className="space-y-1 max-h-[60vh] overflow-y-auto pr-1">
                {loading ? (
                  <div className="text-xs text-gray-400 py-6 text-center"><Loader2 className="w-4 h-4 animate-spin inline-block" /></div>
                ) : sortedAssets.length === 0 ? (
                  <p className="text-xs text-gray-400 py-4 text-center">Keine Stromerzeuger im Auftrag positioniert.</p>
                ) : sortedAssets.map((a) => {
                  const distance = gps.lat != null ? haversineM(gps.lat, gps.lng, Number(a.latitude), Number(a.longitude)) : null;
                  const has = readings.some((r) => r.asset_id === a.id);
                  return (
                    <button
                      key={a.id}
                      onClick={() => setSelectedAsset(a)}
                      className={`w-full text-left p-2 rounded-lg border text-xs transition-colors ${selectedAsset?.id === a.id ? "border-amber-500 bg-amber-50" : "border-gray-200 hover:border-amber-300 hover:bg-amber-50/40"}`}
                      data-testid={`tank-asset-${a.id}`}
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-semibold text-gray-900">{a.label || "Stromerzeuger"}</span>
                        {distance != null && <span className="text-[10px] text-gray-400 font-mono">{Math.round(distance)} m</span>}
                      </div>
                      <div className="flex items-center gap-2 text-[10px] text-gray-500 mt-0.5">
                        {a.plus_code && <span className="font-mono">{a.plus_code}</span>}
                        {has && <span className="px-1.5 py-0.5 rounded-full bg-emerald-100 text-emerald-700">erfasst</span>}
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Formular */}
            <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-4">
              {!selectedAsset ? (
                <div className="text-center text-gray-400 py-12 text-sm">
                  <ChevronRight className="w-6 h-6 mx-auto mb-1 text-gray-300" />
                  Generator aus der Liste wählen
                </div>
              ) : (
                <div className="space-y-3">
                  <div className="pb-2 border-b border-gray-100">
                    <p className="text-xs text-gray-500">Tankstand für</p>
                    <p className="font-semibold text-gray-900">{selectedAsset.label}</p>
                    {knownTankSize ? (
                      <p className="text-[11px] text-emerald-600 mt-0.5">Tankgröße bereits hinterlegt: <span className="font-mono">{knownTankSize} L</span></p>
                    ) : (
                      <p className="text-[11px] text-amber-600 mt-0.5">Erster Eintrag — bitte Tankgröße angeben</p>
                    )}
                  </div>

                  {!knownTankSize && (
                    <div>
                      <Label className="text-xs text-gray-600">Tankgröße (Liter) *</Label>
                      <Input
                        type="number" step="1" min="0"
                        value={tankSizeL}
                        onChange={(e) => setTankSizeL(e.target.value)}
                        placeholder="z.B. 1000"
                        data-testid="tank-size-input"
                      />
                    </div>
                  )}

                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <Label className="text-xs text-gray-600">Tankstand (Liter) *</Label>
                      <Input
                        type="number" step="1" min="0"
                        value={fuelLevelL}
                        onChange={(e) => setFuelLevelL(e.target.value)}
                        placeholder="z.B. 850"
                        data-testid="tank-fuel-input"
                      />
                    </div>
                    <div>
                      <Label className="text-xs text-gray-600">Last (kW)</Label>
                      <Input
                        type="number" step="0.1" min="0"
                        value={loadKw}
                        onChange={(e) => setLoadKw(e.target.value)}
                        placeholder="z.B. 45"
                        data-testid="tank-load-input"
                      />
                    </div>
                    <div className="col-span-2">
                      <Label className="text-xs text-gray-600">Betriebsstunden (h)</Label>
                      <Input
                        type="number" step="0.1" min="0"
                        value={runtimeH}
                        onChange={(e) => setRuntimeH(e.target.value)}
                        placeholder="z.B. 124.5"
                        data-testid="tank-runtime-input"
                      />
                      <p className="text-[10px] text-gray-400 mt-1">Aus Generator-Display ablesen — bessere Verbrauchsprognose</p>
                    </div>
                    <div className="col-span-2">
                      <Label className="text-xs text-gray-600">Kommentar</Label>
                      <Input
                        value={comment}
                        onChange={(e) => setComment(e.target.value)}
                        placeholder="z.B. Refill durch Tankwagen"
                        data-testid="tank-comment-input"
                      />
                    </div>
                    <div className="col-span-2">
                      <Label className="text-xs text-gray-600 flex items-center gap-1">
                        <Camera className="w-3 h-3" /> Foto Tank-Display (optional)
                      </Label>
                      <input
                        type="file"
                        accept="image/*"
                        capture="environment"
                        onChange={(e) => setPhotoFile(e.target.files?.[0] || null)}
                        className="mt-1 text-xs"
                        data-testid="tank-photo-input"
                      />
                      {photoFile && <p className="text-[10px] text-gray-500 mt-1">{photoFile.name} · {Math.round(photoFile.size / 1024)} KB</p>}
                    </div>
                  </div>

                  <Button
                    onClick={submitReading}
                    disabled={submitting || !fuelLevelL || (!knownTankSize && !tankSizeL)}
                    className="w-full bg-amber-500 hover:bg-amber-600 text-white"
                    data-testid="tank-submit-btn"
                  >
                    {submitting ? <Loader2 className="w-4 h-4 animate-spin mr-1" /> : <Fuel className="w-4 h-4 mr-1" />}
                    Tankstand speichern
                  </Button>
                </div>
              )}
            </div>
          </div>
        )}

        {/* PROGNOSE & UEBERSICHT */}
        {tab === "uebersicht" && (
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-4">
            <div className="flex items-center gap-2 mb-3 flex-wrap text-xs">
              <Label className="text-gray-500">Min L</Label>
              <Input type="number" value={minFuel} onChange={(e) => setMinFuel(e.target.value)} className="w-20 h-8 text-xs" placeholder="0" data-testid="filter-min-l" />
              <Label className="text-gray-500">Max L</Label>
              <Input type="number" value={maxFuel} onChange={(e) => setMaxFuel(e.target.value)} className="w-20 h-8 text-xs" placeholder="" data-testid="filter-max-l" />
              <label className="inline-flex items-center gap-1.5 cursor-pointer">
                <input type="checkbox" checked={onlyCritical} onChange={(e) => setOnlyCritical(e.target.checked)} className="accent-red-500" data-testid="filter-only-critical" />
                <span>Nur kritisch/warn</span>
              </label>
              <Label className="text-gray-500 ml-auto">Sortierung</Label>
              <select value={sortBy} onChange={(e) => setSortBy(e.target.value)} className="h-8 px-2 text-xs border border-gray-200 rounded-md bg-white" data-testid="filter-sort">
                <option value="criticality">Kritikalität (Backend)</option>
                <option value="hours_asc">Restzeit (aufsteigend)</option>
                <option value="fuel_asc">Tankstand (aufsteigend)</option>
                <option value="label">Bezeichnung A-Z</option>
              </select>
            </div>

            {visibleForecast.length === 0 ? (
              <p className="text-xs text-gray-400 text-center py-8">Noch keine Tank-Readings — zum Tab „Erfassen" wechseln.</p>
            ) : (
              <div className="space-y-2">
                {visibleForecast.map((f) => {
                  const s = CRIT_STYLES[f.criticality] || CRIT_STYLES.ok;
                  const percent = f.current_percent ?? 0;
                  return (
                    <div key={f.asset_id} className={`rounded-lg border p-3 ${s.bg}`} data-testid={`forecast-${f.asset_id}`}>
                      <div className="flex items-center gap-3">
                        <span className={`w-2.5 h-2.5 rounded-full ${s.dot}`} />
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 flex-wrap">
                            <h3 className="text-sm font-semibold text-gray-900">{f.asset_label}</h3>
                            <span className={`text-[10px] font-bold ${s.text}`}>{s.label.toUpperCase()}</span>
                            <span className="text-[10px] text-gray-400">{f.readings_count} Readings</span>
                          </div>
                          {/* Tank-Balken */}
                          <div className="mt-1.5 h-2 bg-gray-200 rounded-full overflow-hidden">
                            <div
                              className={`h-full transition-all ${f.criticality === "critical" ? "bg-red-500" : f.criticality === "warn" ? "bg-amber-500" : "bg-emerald-500"}`}
                              style={{ width: `${Math.max(2, Math.min(100, percent))}%` }}
                            />
                          </div>
                          <div className="grid grid-cols-2 md:grid-cols-4 gap-2 mt-2 text-[11px]">
                            <div><span className="text-gray-400">Tankstand:</span> <span className="font-mono font-semibold">{f.current_fuel_l} / {f.tank_size_l} L ({percent}%)</span></div>
                            <div><span className="text-gray-400">Ø Verbrauch:</span> <span className="font-mono font-semibold">{f.avg_lph != null ? `${f.avg_lph} L/h` : "—"}</span></div>
                            <div><span className="text-gray-400">Restzeit:</span> <span className="font-mono font-semibold">{f.hours_remaining != null ? `${f.hours_remaining} h` : "—"}</span></div>
                            <div className="inline-flex items-center gap-1"><Calendar className="w-3 h-3 text-gray-400" /> <span className="font-mono">{formatEta(f.eta_empty)}</span></div>
                          </div>
                          {f.criticality === "critical" && (
                            <div className="mt-1.5 text-[11px] text-red-700 inline-flex items-center gap-1">
                              <AlertTriangle className="w-3 h-3" /> Refill priorisieren
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {/* HISTORIE */}
        {tab === "historie" && (
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
            <table className="w-full text-xs">
              <thead className="bg-gray-50 text-left">
                <tr className="text-gray-500">
                  <th className="px-3 py-2">Zeitpunkt</th>
                  <th className="px-3 py-2">Generator</th>
                  <th className="px-3 py-2 text-right">Tank-Größe</th>
                  <th className="px-3 py-2 text-right">Stand</th>
                  <th className="px-3 py-2 text-right">Last</th>
                  <th className="px-3 py-2 text-right">Betriebsstd.</th>
                  <th className="px-3 py-2">Kommentar</th>
                  <th className="px-3 py-2">Erfasst von</th>
                  <th className="px-3 py-2"></th>
                </tr>
              </thead>
              <tbody>
                {readings.length === 0 ? (
                  <tr><td colSpan={9} className="px-3 py-6 text-center text-gray-400">Noch keine Readings.</td></tr>
                ) : readings.map((r) => (
                  <tr key={r.id} className="border-t border-gray-100">
                    <td className="px-3 py-2 font-mono text-[10px]">{formatEta(r.recorded_at)}</td>
                    <td className="px-3 py-2 font-medium">{r.asset_label}</td>
                    <td className="px-3 py-2 text-right font-mono">{r.tank_size_l} L</td>
                    <td className="px-3 py-2 text-right font-mono">{r.fuel_level_l} L <span className="text-gray-400">({r.fuel_percent}%)</span></td>
                    <td className="px-3 py-2 text-right font-mono">{r.load_kw != null ? `${r.load_kw} kW` : "—"}</td>
                    <td className="px-3 py-2 text-right font-mono">{r.runtime_h != null ? `${r.runtime_h} h` : "—"}</td>
                    <td className="px-3 py-2 text-gray-600">{r.comment || "—"}</td>
                    <td className="px-3 py-2 text-gray-500">{r.created_by}</td>
                    <td className="px-3 py-2">
                      <button onClick={() => deleteReading(r.id)} className="text-gray-400 hover:text-red-500" data-testid={`tank-delete-${r.id}`}>
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
