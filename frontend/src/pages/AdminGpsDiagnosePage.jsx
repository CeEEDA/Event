import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { Logo } from "../components/Logo";
import api from "../lib/api";
import { toast } from "sonner";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import {
  ArrowLeft,
  RefreshCw,
  MapPin,
  AlertTriangle,
  Trash2,
  FileText,
  CheckCircle2,
  Clock,
  Link2,
  HelpCircle,
} from "lucide-react";

function fmtCoord(v) {
  if (v == null) return "—";
  return Number(v).toFixed(6);
}

function fmtAge(h) {
  if (h == null) return "—";
  if (h < 1) return `${Math.round(h * 60)} min`;
  if (h < 48) return `${h.toFixed(1)} h`;
  return `${(h / 24).toFixed(1)} Tage`;
}

function ageColor(h) {
  if (h == null) return "text-gray-400";
  if (h < 1) return "text-emerald-600";
  if (h < 6) return "text-amber-600";
  return "text-red-600";
}

export default function AdminGpsDiagnosePage() {
  const navigate = useNavigate();
  const [tab, setTab] = useState("status");
  const [status, setStatus] = useState(null);
  const [log, setLog] = useState(null);
  const [loading, setLoading] = useState(false);
  const [resetHours, setResetHours] = useState("6");
  const [resetting, setResetting] = useState(false);
  const [unknownGateways, setUnknownGateways] = useState(null);
  const [linkTarget, setLinkTarget] = useState({}); // {gwUid: {target_type, target_id}}
  const [linking, setLinking] = useState({}); // {gwUid: bool}

  const fetchUnknown = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get("/admin/gps/unknown");
      setUnknownGateways(res.data);
    } catch (err) {
      toast.error("Fehler: " + (err.response?.data?.detail || err.message));
    } finally {
      setLoading(false);
    }
  }, []);

  const handleLink = async (gwUid) => {
    const target = linkTarget[gwUid];
    if (!target?.target_id) {
      toast.error("Bitte Ziel auswaehlen");
      return;
    }
    setLinking((s) => ({ ...s, [gwUid]: true }));
    try {
      const res = await api.post(`/admin/gps/unknown/${gwUid}/link`, target);
      toast.success(`Verknuepft: ${res.data.target_name}`);
      fetchUnknown();
      fetchStatus();
    } catch (err) {
      toast.error("Verknuepfen fehlgeschlagen: " + (err.response?.data?.detail || err.message));
    } finally {
      setLinking((s) => ({ ...s, [gwUid]: false }));
    }
  };

  const handleDeleteUnknown = async (gwUid) => {
    if (!window.confirm(`Eintrag ${gwUid} wirklich loeschen? (Bei naechstem GPS-Event wird er neu erstellt)`)) return;
    try {
      await api.delete(`/admin/gps/unknown/${gwUid}`);
      toast.success("Eintrag geloescht");
      fetchUnknown();
    } catch (err) {
      toast.error("Loeschen fehlgeschlagen: " + (err.response?.data?.detail || err.message));
    }
  };

  const fetchStatus = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get("/admin/gps/status");
      setStatus(res.data);
    } catch (err) {
      toast.error("Fehler beim Laden des Status: " + (err.response?.data?.detail || err.message));
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchLog = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get("/admin/gps/log?limit=200");
      setLog(res.data);
    } catch (err) {
      toast.error("Fehler beim Laden des Logs: " + (err.response?.data?.detail || err.message));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (tab === "status") fetchStatus();
    if (tab === "log") fetchLog();
    if (tab === "unknown") {
      fetchUnknown();
      // Status laden falls nicht da (fuer Device/Generator-Liste im Dropdown)
      if (!status) fetchStatus();
    }
  }, [tab, fetchStatus, fetchLog, fetchUnknown, status]);

  const handleReset = async () => {
    const h = parseInt(resetHours, 10);
    if (isNaN(h) || h < 0) {
      toast.error("Bitte gültige Stundenzahl angeben (0 = alle)");
      return;
    }
    if (!window.confirm(
      `Wirklich alle GPS-Einträge älter als ${h}h (bzw. ohne Update) zurücksetzen?\n\n` +
      `Beim nächsten echten GPS-Telegramm pro Gerät wird die korrekte Position automatisch neu geschrieben.`
    )) return;

    setResetting(true);
    try {
      const params = h === 0 ? "?all=true" : `?older_than_hours=${h}`;
      const res = await api.post(`/admin/gps/reset${params}`);
      toast.success(
        `Reset OK: ${res.data.devices_reset} Geräte, ${res.data.generators_reset} Generatoren zurückgesetzt`
      );
      fetchStatus();
    } catch (err) {
      toast.error("Reset fehlgeschlagen: " + (err.response?.data?.detail || err.message));
    } finally {
      setResetting(false);
    }
  };

  const dupCount = status?.duplicate_coords
    ? Object.values(status.duplicate_coords).reduce((a, b) => a + b, 0)
    : 0;

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col" data-testid="admin-gps-page">
      <header className="bg-white border-b border-gray-200 p-4">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => navigate("/admin")}
              className="text-gray-600 hover:text-fuchsia-600"
              data-testid="back-btn"
            >
              <ArrowLeft className="w-4 h-4 mr-2" />
              Zurück
            </Button>
            <div className="h-6 w-px bg-gray-200" />
            <h1 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
              <MapPin className="w-4 h-4 text-fuchsia-600" />
              GPS-Diagnose & Reset
            </h1>
          </div>
          <Logo size="small" />
        </div>
      </header>

      <main className="flex-1 p-4 md:p-6">
        <div className="max-w-7xl mx-auto space-y-4">
          {/* Tabs */}
          <div className="flex gap-2 border-b border-gray-200">
            {[
              { key: "status", label: "Status & Duplikate", icon: MapPin },
              { key: "log", label: "Live-Log", icon: FileText },
              { key: "unknown", label: "Unbekannte Gateways", icon: HelpCircle },
              { key: "reset", label: "Reset", icon: Trash2 },
            ].map((t) => {
              const Icon = t.icon;
              return (
                <button
                  key={t.key}
                  onClick={() => setTab(t.key)}
                  data-testid={`tab-${t.key}`}
                  className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors flex items-center gap-2 ${
                    tab === t.key
                      ? "border-fuchsia-600 text-fuchsia-700"
                      : "border-transparent text-gray-500 hover:text-gray-700"
                  }`}
                >
                  <Icon className="w-4 h-4" />
                  {t.label}
                </button>
              );
            })}
          </div>

          {/* STATUS Tab */}
          {tab === "status" && status && (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="bg-white border border-gray-200 rounded-lg px-4 py-2 text-sm">
                    <span className="text-gray-500">Geräte:</span>{" "}
                    <strong>{status.devices.length}</strong>
                  </div>
                  <div className="bg-white border border-gray-200 rounded-lg px-4 py-2 text-sm">
                    <span className="text-gray-500">Generatoren:</span>{" "}
                    <strong>{status.generators.length}</strong>
                  </div>
                  {dupCount > 0 ? (
                    <div className="bg-red-50 border border-red-200 rounded-lg px-4 py-2 text-sm text-red-700 flex items-center gap-2" data-testid="dup-warning">
                      <AlertTriangle className="w-4 h-4" />
                      <strong>{dupCount}</strong> Einträge auf {Object.keys(status.duplicate_coords).length} identischen Koordinaten
                    </div>
                  ) : (
                    <div className="bg-emerald-50 border border-emerald-200 rounded-lg px-4 py-2 text-sm text-emerald-700 flex items-center gap-2">
                      <CheckCircle2 className="w-4 h-4" />
                      Keine Duplikate
                    </div>
                  )}
                  {status.missing_dse_module_uid && status.missing_dse_module_uid.total > 0 && (
                    <div className="bg-amber-50 border border-amber-200 rounded-lg px-4 py-2 text-sm text-amber-800 flex items-center gap-2" data-testid="missing-uid-warning">
                      <AlertTriangle className="w-4 h-4" />
                      <strong>{status.missing_dse_module_uid.total}</strong> Einträge ohne <code className="text-xs">dse_module_uid</code> (kein GPS möglich)
                    </div>
                  )}
                </div>
                <Button size="sm" variant="outline" onClick={fetchStatus} disabled={loading} data-testid="refresh-status-btn">
                  <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
                </Button>
              </div>

              {status.missing_dse_module_uid && status.missing_dse_module_uid.total > 0 && (
                <div className="bg-white border border-amber-200 rounded-lg p-4" data-testid="missing-uid-list">
                  <h3 className="text-sm font-semibold text-amber-700 mb-2">
                    Geräte ohne hinterlegte <code className="text-xs">dse_module_uid</code> ({status.missing_dse_module_uid.total})
                  </h3>
                  <p className="text-xs text-amber-700 mb-3">
                    Ohne diese UID kann das GPS-Telegramm im JSON-Payload nicht zugeordnet werden — die Maschine bleibt ohne Position.
                    Trage die 10-stellige Modul-UID (z.B. <code>6D2B5CD695</code>) in der Geräte- bzw. Generator-Verwaltung nach.
                  </p>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-xs">
                    {[...status.missing_dse_module_uid.devices, ...status.missing_dse_module_uid.generators].map((e) => (
                      <div key={e.id} className="border border-amber-100 rounded px-2 py-1 bg-amber-50">
                        <strong>{e.name || e.serial_number || "—"}</strong>
                        <span className="text-gray-500 ml-2 font-mono">{e.serial_number}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {dupCount > 0 && (
                <div className="bg-white border border-red-200 rounded-lg p-4" data-testid="dup-list">
                  <h3 className="text-sm font-semibold text-red-700 mb-2">Doppelt vergebene Koordinaten</h3>
                  <div className="space-y-1 text-xs font-mono">
                    {Object.entries(status.duplicate_coords).map(([k, v]) => (
                      <div key={k} className="flex justify-between border-b border-red-100 py-1">
                        <span>{k}</span>
                        <span className="text-red-600 font-bold">{v}× verwendet</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
                <table className="w-full text-xs">
                  <thead className="bg-gray-50 border-b border-gray-200">
                    <tr>
                      <th className="text-left p-2 font-semibold">Typ</th>
                      <th className="text-left p-2 font-semibold">Name / Serial</th>
                      <th className="text-left p-2 font-semibold">Latitude</th>
                      <th className="text-left p-2 font-semibold">Longitude</th>
                      <th className="text-left p-2 font-semibold">Alter</th>
                      <th className="text-left p-2 font-semibold">DSE UID / Topic</th>
                    </tr>
                  </thead>
                  <tbody>
                    {[...status.devices, ...status.generators].map((r, i) => {
                      const coordKey =
                        r.latitude != null && r.longitude != null
                          ? `${Number(r.latitude).toFixed(5)},${Number(r.longitude).toFixed(5)}`
                          : null;
                      const isDup = coordKey && status.duplicate_coords[coordKey];
                      return (
                        <tr
                          key={`${r.kind}-${r.id}-${i}`}
                          className={`border-b border-gray-100 hover:bg-gray-50 ${
                            isDup ? "bg-red-50" : ""
                          }`}
                          data-testid={`gps-row-${r.id}`}
                        >
                          <td className="p-2">
                            <span className={`px-2 py-0.5 rounded text-[10px] font-medium ${
                              r.kind === "device"
                                ? "bg-blue-100 text-blue-700"
                                : "bg-purple-100 text-purple-700"
                            }`}>
                              {r.kind === "device" ? "Device" : "Gen"}
                            </span>
                          </td>
                          <td className="p-2 font-mono">
                            <div>{r.name || "—"}</div>
                            <div className="text-gray-400 text-[10px]">{r.serial_number || ""}</div>
                          </td>
                          <td className={`p-2 font-mono ${isDup ? "text-red-700 font-bold" : ""}`}>
                            {fmtCoord(r.latitude)}
                          </td>
                          <td className={`p-2 font-mono ${isDup ? "text-red-700 font-bold" : ""}`}>
                            {fmtCoord(r.longitude)}
                          </td>
                          <td className={`p-2 ${ageColor(r.age_hours)}`}>{fmtAge(r.age_hours)}</td>
                          <td className="p-2 text-gray-500 font-mono text-[10px]">
                            {r.dse_module_uid || r.dse_mqtt_topic_prefix || "—"}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* LOG Tab */}
          {tab === "log" && (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3 text-sm">
                  <span className="text-gray-500">Events:</span>
                  <strong>{log?.count || 0}</strong>
                  {log?.by_route && Object.entries(log.by_route).map(([k, v]) => (
                    <span key={k} className="px-2 py-1 rounded bg-gray-100 text-gray-700 text-xs">
                      {k}: <strong>{v}</strong>
                    </span>
                  ))}
                </div>
                <Button size="sm" variant="outline" onClick={fetchLog} disabled={loading} data-testid="refresh-log-btn">
                  <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
                </Button>
              </div>

              {log?.count === 0 ? (
                <div className="bg-amber-50 border border-amber-200 rounded-lg p-6 text-center">
                  <Clock className="w-8 h-8 text-amber-500 mx-auto mb-2" />
                  <p className="text-sm font-semibold text-amber-800">Keine GPS-Telegramme im Log</p>
                  <p className="text-xs text-amber-700 mt-1">
                    Entweder senden die Geräte aktuell kein GPS, oder der MQTT-Broker liefert keine GPS-Topics aus.
                    Bitte prüfen: GPS-Antenne der DSE890, MQTT-Subscriptions, Pi-Connectivity.
                  </p>
                </div>
              ) : (
                <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
                  <table className="w-full text-xs">
                    <thead className="bg-gray-50 border-b border-gray-200">
                      <tr>
                        <th className="text-left p-2 font-semibold">Zeit</th>
                        <th className="text-left p-2 font-semibold">Route</th>
                        <th className="text-left p-2 font-semibold">Topic</th>
                        <th className="text-left p-2 font-semibold">Lat / Lng</th>
                        <th className="text-left p-2 font-semibold">Module-UID</th>
                        <th className="text-left p-2 font-semibold">Match</th>
                        <th className="text-left p-2 font-semibold">Applied / Payload</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(log?.events || []).map((e) => (
                        <tr key={e.id} className="border-b border-gray-100 hover:bg-gray-50 align-top">
                          <td className="p-2 text-gray-500 font-mono text-[10px]">
                            {new Date(e.ts).toLocaleString("de-DE")}
                          </td>
                          <td className="p-2">
                            <span className={`px-2 py-0.5 rounded text-[10px] font-medium whitespace-nowrap ${
                              e.route?.startsWith("rejected") ? "bg-red-100 text-red-700" :
                              e.route === "gateway_module_match" ? "bg-emerald-100 text-emerald-700" :
                              e.route === "pi_ingest" ? "bg-blue-100 text-blue-700" :
                              "bg-emerald-100 text-emerald-700"
                            }`}>
                              {e.route}
                            </span>
                          </td>
                          <td className="p-2 font-mono text-[10px] max-w-xs truncate" title={e.topic}>{e.topic}</td>
                          <td className="p-2 font-mono text-[10px] whitespace-nowrap">
                            {fmtCoord(e.lat)} / {fmtCoord(e.lng)}
                          </td>
                          <td className={`p-2 font-mono text-[10px] ${e.module_uid ? "text-amber-700 font-semibold" : "text-gray-300"}`}>
                            {e.module_uid || "—"}
                          </td>
                          <td className="p-2 text-center font-semibold">{e.match_count}</td>
                          <td className="p-2 font-mono text-[10px] text-gray-500 max-w-md">
                            {e.applied_to && e.applied_to.length > 0 ? (
                              <div className="truncate" title={e.applied_to.join(", ")}>{e.applied_to.join(", ")}</div>
                            ) : (
                              <div className="text-gray-400 truncate" title={e.raw_preview}>{e.raw_preview || "—"}</div>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}

          {/* UNKNOWN GATEWAYS Tab */}
          {tab === "unknown" && (
            <div className="space-y-4" data-testid="unknown-tab">
              <div className="flex items-center justify-between">
                <div className="bg-amber-50 border border-amber-200 rounded-lg px-4 py-2 text-sm text-amber-800 flex items-center gap-2">
                  <HelpCircle className="w-4 h-4" />
                  <span>
                    <strong>{unknownGateways?.count ?? "—"}</strong> unbekannte Gateway-UIDs gesendet GPS,
                    aber sind keinem Device/Generator zugeordnet.
                  </span>
                </div>
                <Button size="sm" variant="outline" onClick={fetchUnknown} disabled={loading} data-testid="refresh-unknown-btn">
                  <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
                </Button>
              </div>

              {(!unknownGateways || unknownGateways.count === 0) ? (
                <div className="bg-emerald-50 border border-emerald-200 rounded-lg p-6 text-center">
                  <CheckCircle2 className="w-8 h-8 text-emerald-600 mx-auto mb-2" />
                  <p className="text-sm font-semibold text-emerald-800">Alles sauber verknuepft</p>
                  <p className="text-xs text-emerald-700 mt-1">
                    Keine unbekannten Gateway-UIDs. Falls neue GPS-Events ohne Match reinkommen,
                    erscheinen sie automatisch hier.
                  </p>
                </div>
              ) : (
                <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
                  <table className="w-full text-xs">
                    <thead className="bg-gray-50 border-b border-gray-200">
                      <tr>
                        <th className="text-left p-2 font-semibold">Gateway-UID</th>
                        <th className="text-left p-2 font-semibold">Anlage</th>
                        <th className="text-left p-2 font-semibold">Letzte Position</th>
                        <th className="text-left p-2 font-semibold">Events</th>
                        <th className="text-left p-2 font-semibold">Erstmals</th>
                        <th className="text-left p-2 font-semibold w-[480px]">Verknuepfen</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(unknownGateways.unknown_gateways || []).map((gw) => (
                        <tr key={gw.gateway_uid} className="border-b border-gray-100 hover:bg-gray-50 align-top" data-testid={`unknown-row-${gw.gateway_uid}`}>
                          <td className="p-2 font-mono text-[11px] text-amber-800 font-semibold">{gw.gateway_uid}</td>
                          <td className="p-2 font-mono text-[10px]">{gw.anlage_id || "—"}</td>
                          <td className="p-2 font-mono text-[10px] whitespace-nowrap">
                            {fmtCoord(gw.last_lat)} / {fmtCoord(gw.last_lng)}
                          </td>
                          <td className="p-2 text-center font-semibold">{gw.event_count || 0}</td>
                          <td className="p-2 text-[10px] text-gray-500 whitespace-nowrap">
                            {gw.first_seen ? new Date(gw.first_seen).toLocaleString("de-DE") : "—"}
                          </td>
                          <td className="p-2">
                            <div className="flex items-center gap-1">
                              <select
                                className="border border-gray-300 rounded px-1 py-0.5 text-[10px] flex-1 min-w-0"
                                data-testid={`select-${gw.gateway_uid}`}
                                value={linkTarget[gw.gateway_uid]?.target_id
                                  ? `${linkTarget[gw.gateway_uid].target_type}:${linkTarget[gw.gateway_uid].target_id}`
                                  : ""}
                                onChange={(e) => {
                                  const v = e.target.value;
                                  if (!v) {
                                    setLinkTarget((s) => ({ ...s, [gw.gateway_uid]: null }));
                                    return;
                                  }
                                  const [target_type, target_id] = v.split(":");
                                  setLinkTarget((s) => ({ ...s, [gw.gateway_uid]: { target_type, target_id } }));
                                }}
                              >
                                <option value="">— Ziel auswaehlen —</option>
                                <optgroup label="Generatoren">
                                  {(status?.generators || []).map((g) => (
                                    <option key={`g-${g.id}`} value={`generator:${g.id}`}>
                                      {g.name || g.serial_number || g.id}
                                    </option>
                                  ))}
                                </optgroup>
                                <optgroup label="Geraete">
                                  {(status?.devices || []).map((d) => (
                                    <option key={`d-${d.id}`} value={`device:${d.id}`}>
                                      {d.name || d.serial_number || d.id}
                                    </option>
                                  ))}
                                </optgroup>
                              </select>
                              <Button
                                size="sm"
                                onClick={() => handleLink(gw.gateway_uid)}
                                disabled={linking[gw.gateway_uid]}
                                className="h-7 px-2 text-[10px] bg-emerald-600 hover:bg-emerald-700"
                                data-testid={`link-btn-${gw.gateway_uid}`}
                              >
                                {linking[gw.gateway_uid] ? <RefreshCw className="w-3 h-3 animate-spin" /> : <Link2 className="w-3 h-3" />}
                              </Button>
                              <Button
                                size="sm"
                                variant="ghost"
                                onClick={() => handleDeleteUnknown(gw.gateway_uid)}
                                className="h-7 px-2 text-[10px] text-red-600 hover:bg-red-50"
                                data-testid={`delete-unknown-${gw.gateway_uid}`}
                                title="Stub loeschen"
                              >
                                <Trash2 className="w-3 h-3" />
                              </Button>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 text-xs text-blue-700">
                <strong>So funktioniert's:</strong> Jede GPS-Nachricht mit unbekannter Gateway-UID
                wird hier gesammelt. Waehle das passende Geraet/Generator aus dem Dropdown und klicke
                auf <Link2 className="inline w-3 h-3" />. Beim naechsten GPS-Telegramm wird die Position
                automatisch auf dieses Geraet geschrieben — keine weitere Konfiguration noetig.
              </div>
            </div>
          )}

          {/* RESET Tab */}
          {tab === "reset" && (
            <div className="bg-white border border-gray-200 rounded-lg p-6 space-y-4 max-w-2xl">
              <div className="flex items-start gap-3">
                <AlertTriangle className="w-5 h-5 text-amber-500 flex-shrink-0 mt-0.5" />
                <div>
                  <h3 className="text-sm font-semibold text-gray-900">Stale GPS zurücksetzen</h3>
                  <p className="text-xs text-gray-600 mt-1">
                    Löscht <code>latitude</code>, <code>longitude</code> und <code>last_gps_update</code> aus
                    Devices/Generators, deren GPS-Update älter ist als die angegebene Stundenzahl
                    (oder gar nicht gesetzt aber mit Restwerten).
                    Beim nächsten echten Telegramm pro Gerät wird die korrekte Position individuell neu geschrieben.
                  </p>
                </div>
              </div>

              <div className="flex items-end gap-3">
                <div className="flex-1">
                  <label className="text-xs font-medium text-gray-700 mb-1 block">
                    Älter als (Stunden) — 0 = alle
                  </label>
                  <Input
                    type="number"
                    min="0"
                    value={resetHours}
                    onChange={(e) => setResetHours(e.target.value)}
                    data-testid="reset-hours-input"
                  />
                </div>
                <Button
                  onClick={handleReset}
                  disabled={resetting}
                  className="bg-red-600 hover:bg-red-700"
                  data-testid="reset-btn"
                >
                  {resetting ? (
                    <RefreshCw className="w-4 h-4 animate-spin mr-2" />
                  ) : (
                    <Trash2 className="w-4 h-4 mr-2" />
                  )}
                  Reset ausführen
                </Button>
              </div>

              <div className="text-xs text-gray-500 border-t border-gray-100 pt-3">
                <strong>Tipp:</strong> Zuerst auf "Status & Duplikate" prüfen, wie viele Geräte
                derzeit dieselbe Position teilen. Im "Live-Log" siehst du, ob aktuell überhaupt
                GPS-Telegramme reinkommen — wenn dort 0 Events stehen, hilft ein Reset alleine nicht
                (Gerät sendet kein GPS).
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
