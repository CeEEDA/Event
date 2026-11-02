import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, RefreshCw, Fuel, Droplets, AlertTriangle, Calendar, Cpu, MapPin } from "lucide-react";
import L from "leaflet";
import { MapContainer, Marker } from "react-leaflet";
import MapTileLayer from "../components/MapTileLayer";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, ReferenceLine } from "recharts";
import { toast } from "sonner";
import { Logo } from "../components/Logo";
import { Button } from "../components/ui/button";
import api from "../lib/api";

const fmtTime = (iso) => iso ? new Date(iso).toLocaleString("de-DE", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" }) : "–";

function TankGauge({ pct, liters, capacity, warn, crit, error }) {
  const p = pct == null ? 0 : Math.max(0, Math.min(100, pct));
  const color = error ? "bg-gray-300" : p < crit ? "bg-red-500" : p < warn ? "bg-amber-400" : "bg-emerald-500";
  return (
    <div className="bg-white border border-gray-200 rounded-xl shadow-sm p-5 flex flex-col sm:flex-row items-center gap-6" data-testid="tank-gauge">
      <div className="relative w-28 h-56 rounded-2xl border-4 border-gray-300 bg-gray-50 overflow-hidden shrink-0">
        <div className={`absolute bottom-0 left-0 right-0 transition-all duration-1000 ${color}`} style={{ height: `${p}%` }} />
        <div className="absolute left-0 right-0 border-t border-dashed border-amber-400/70" style={{ bottom: `${warn}%` }} title={`Warnung ${warn} %`} />
        <div className="absolute left-0 right-0 border-t border-dashed border-red-500/70" style={{ bottom: `${crit}%` }} title={`Alarm ${crit} %`} />
      </div>
      <div className="text-center sm:text-left">
        <p className="text-5xl font-bold text-gray-900 tabular-nums" data-testid="tank-pct">{error || pct == null ? "–" : Math.round(pct)}<span className="text-2xl text-gray-400"> %</span></p>
        <p className="text-lg text-gray-600 mt-1" data-testid="tank-liters">{liters != null && !error ? `${liters.toLocaleString("de-DE")} L` : "–"}{capacity ? <span className="text-gray-400"> von {capacity.toLocaleString("de-DE")} L</span> : ""}</p>
        {error && <p className="text-sm text-red-600 mt-2 flex items-center gap-1" data-testid="tank-sensor-error"><AlertTriangle className="w-4 h-4" /> {error}</p>}
        <p className="text-xs text-gray-400 mt-3">Warnung unter {warn} % · Alarm unter {crit} %</p>
      </div>
    </div>
  );
}

function Kachel({ icon: Icon, label, value, sub, testId }) {
  return (
    <div className="bg-white border border-gray-200 rounded-xl shadow-sm p-4" data-testid={testId}>
      <p className="text-[10px] font-bold text-gray-400 uppercase tracking-widest flex items-center gap-1.5"><Icon className="w-3.5 h-3.5 text-fuchsia-500" /> {label}</p>
      <p className="text-lg font-semibold text-gray-900 mt-1 truncate">{value}</p>
      {sub && <p className="text-xs text-gray-400 truncate">{sub}</p>}
    </div>
  );
}

export default function TankDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [tank, setTank] = useState(null);
  const [tele, setTele] = useState(null);
  const [hours, setHours] = useState(24);
  const [err, setErr] = useState(null);

  const load = useCallback(async () => {
    try {
      const [t, h] = await Promise.all([api.get(`/tank/${id}`), api.get(`/tank/${id}/telemetry`, { params: { hours } })]);
      setTank(t.data); setTele(h.data); setErr(null);
    } catch (e) { setErr(e.response?.data?.detail || "Tank nicht ladbar"); }
  }, [id, hours]);
  useEffect(() => { load(); const t = setInterval(load, 60000); return () => clearInterval(t); }, [load]);

  if (err) return <div className="min-h-screen bg-gray-50 flex items-center justify-center text-gray-500" data-testid="tank-error">{err}</div>;
  if (!tank) return <div className="min-h-screen bg-gray-50 flex items-center justify-center text-gray-400">Lade Tank…</div>;

  const name = tank.user_field || tank.serial_number;
  const online = tank.pi?.online;
  const gps = tank.gps;
  const position = tank.latitude != null && tank.longitude != null ? [tank.latitude, tank.longitude] : null;
  const points = (tele?.points || []).map(p => ({ t: new Date(p.timestamp).getTime(), pct: p.fuel_level_pct, l: p.liters }));
  const inspDays = tank.next_inspection_date ? Math.ceil((new Date(tank.next_inspection_date) - Date.now()) / 86400000) : null;
  const health = tank.pi?.health || {};

  return (
    <div className="min-h-screen bg-gray-50" data-testid="tank-detail-page">
      <header className="sticky top-0 z-10 bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between gap-3">
          <div className="flex items-center gap-3 min-w-0">
            <Button variant="ghost" size="sm" onClick={() => navigate("/generators")} className="text-gray-600 hover:text-fuchsia-600 shrink-0" data-testid="tank-back-btn"><ArrowLeft className="w-4 h-4 mr-1" /> Zurück</Button>
            <div className="h-5 w-px bg-gray-200 shrink-0" />
            <div className="min-w-0">
              <h1 className="text-sm font-bold text-gray-900 tracking-tight truncate" data-testid="tank-title">{name}</h1>
              <p className="text-xs text-gray-400 truncate">Tank {tank.tank_capacity || ""}{tank.serial_number !== name ? ` · ${tank.serial_number}` : ""}</p>
            </div>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border ${online ? "bg-emerald-50 text-emerald-700 border-emerald-200" : "bg-gray-100 text-gray-500 border-gray-200"}`} data-testid="tank-pill-online">
              <span className={`w-2 h-2 rounded-full ${online ? "bg-emerald-500 animate-pulse" : "bg-gray-400"}`} />{online ? "Pi online" : "Pi offline"}
            </span>
            <Button variant="ghost" size="sm" onClick={() => { load(); toast.success("Aktualisiert"); }} className="text-gray-500 hover:text-fuchsia-600" data-testid="tank-refresh-btn"><RefreshCw className="w-4 h-4" /></Button>
            <Logo size="small" />
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 py-6 space-y-6">
        {tank.alarm_state !== "ok" && (
          <div className={`rounded-lg px-4 py-3 text-sm flex items-center gap-2 ${tank.alarm_state === "crit" ? "bg-red-50 text-red-700 border border-red-200" : "bg-amber-50 text-amber-700 border border-amber-200"}`} data-testid="tank-alarm-banner">
            <AlertTriangle className="w-4 h-4" /> {tank.alarm_state === "crit" ? `Füllstand kritisch (unter ${tank.crit_pct} %) – Betankung dringend` : `Füllstand niedrig (unter ${tank.warn_pct} %) – Betankung einplanen`}
          </div>
        )}
        {!online && <p className="text-xs text-gray-500 bg-white border border-gray-200 rounded-lg px-3 py-2" data-testid="tank-offline-hint">{tank.pi?.last_seen ? `Der Pi hat sich zuletzt ${fmtTime(tank.pi.last_seen)} gemeldet. Werte können veraltet sein.` : "Der Pi hat sich noch nie gemeldet – Pi-Setup in der Geräteverwaltung generieren und auf dem Pi ausführen."}</p>}

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 space-y-6">
            <TankGauge pct={tank.fuel_level_pct} liters={tank.liters} capacity={tank.capacity_l} warn={tank.warn_pct} crit={tank.crit_pct} error={tank.sensor_error} />
            <div className="bg-white border border-gray-200 rounded-xl shadow-sm p-5" data-testid="tank-chart">
              <div className="flex items-center justify-between gap-2 flex-wrap mb-3">
                <h2 className="text-xs font-bold text-gray-500 uppercase tracking-widest">Verlauf</h2>
                <div className="flex gap-1">
                  {[[24, "24 h"], [168, "7 Tage"], [720, "30 Tage"]].map(([h, l]) => (
                    <button key={h} type="button" onClick={() => setHours(h)} className={`px-2.5 py-1 rounded-full text-xs border ${hours === h ? "bg-fuchsia-600 text-white border-fuchsia-600" : "bg-white text-gray-600 border-gray-200 hover:border-fuchsia-300"}`} data-testid={`tank-range-${h}`}>{l}</button>
                  ))}
                </div>
              </div>
              {points.length < 2 ? <p className="text-sm text-gray-400 py-10 text-center">Noch keine Verlaufsdaten.</p> : (
                <div style={{ height: 240 }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={points} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
                      <XAxis dataKey="t" type="number" domain={["dataMin", "dataMax"]} tickFormatter={(v) => new Date(v).toLocaleString("de-DE", hours > 48 ? { day: "2-digit", month: "2-digit" } : { hour: "2-digit", minute: "2-digit" })} tick={{ fontSize: 11 }} />
                      <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} />
                      <Tooltip labelFormatter={(v) => new Date(v).toLocaleString("de-DE")} formatter={(v, n) => n === "pct" ? [`${v} %`, "Füllstand"] : [`${v} L`, "Liter"]} />
                      <ReferenceLine y={tank.warn_pct} stroke="#f59e0b" strokeDasharray="4 4" />
                      <ReferenceLine y={tank.crit_pct} stroke="#ef4444" strokeDasharray="4 4" />
                      <Line type="monotone" dataKey="pct" stroke="#a855f7" strokeWidth={2} dot={false} isAnimationActive={false} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              )}
              {tele?.trend && <p className="text-xs text-gray-500 mt-2" data-testid="tank-trend">Verbrauch ca. {tele.trend.liters_per_hour} L/h{tele.trend.hours_left != null ? ` · reicht noch ca. ${Math.round(tele.trend.hours_left)} h` : ""}</p>}
            </div>
          </div>
          <div className="space-y-4">
            <div className="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden" data-testid="tank-map">
              <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100">
                <h2 className="text-xs font-bold text-gray-500 uppercase tracking-widest flex items-center gap-2"><MapPin className="w-4 h-4 text-fuchsia-500" /> Standort</h2>
                {position && <span className="text-[11px] text-gray-400">{position[0].toFixed(5)}, {position[1].toFixed(5)}</span>}
              </div>
              {position ? (
                <div style={{ height: 220 }}>
                  <MapContainer center={position} zoom={14} style={{ height: "100%", width: "100%" }} scrollWheelZoom={false}>
                    <MapTileLayer />
                    <Marker position={position} icon={L.divIcon({ className: "custom-marker", html: '<div style="width:16px;height:16px;background:#A855F7;border-radius:50%;border:3px solid white;box-shadow:0 2px 6px rgba(0,0,0,0.3)"></div>', iconSize: [16, 16], iconAnchor: [8, 8] })} />
                  </MapContainer>
                </div>
              ) : (
                <p className="text-sm text-gray-400 px-4 py-8 text-center">Noch keine GPS-Position – das LTE-HAT braucht unter freiem Himmel einige Minuten für den ersten Fix.</p>
              )}
              <p className="text-[11px] text-gray-400 px-4 py-2 border-t border-gray-100">{gps?.fix ? `GPS-Fix (Modus ${gps.mode})${gps.ts ? " · " + fmtTime(gps.ts) : ""}` : position ? "letzte bekannte Position (aktuell kein Fix)" : "LTE-HAT GPS"}</p>
            </div>
            <Kachel icon={Droplets} label="Letzte Messung" value={fmtTime(tank.measured_at)} sub={online ? "Pi meldet regelmäßig" : "Pi offline"} testId="tank-measured" />
            <Kachel icon={Cpu} label="Pi" value={online ? "online" : "offline"} sub={`v${tank.pi?.version || "–"}${health.ppp0 != null ? ` · LTE ${health.ppp0 ? "verbunden" : "aus"}` : ""}${health.cpu_temp_c ? ` · ${health.cpu_temp_c} °C` : ""}`} testId="tank-pi" />
            <Kachel icon={Calendar} label="Nächste Prüfung" value={tank.next_inspection_date ? new Date(tank.next_inspection_date).toLocaleDateString("de-DE") : "–"} sub={inspDays != null ? (inspDays < 0 ? `seit ${-inspDays} Tagen überfällig` : `in ${inspDays} Tagen`) : "TÜV / Sachkundige"} testId="tank-inspection" />
          </div>
        </div>

        <div className="bg-white border border-gray-200 rounded-xl shadow-sm" data-testid="tank-alarms">
          <div className="px-5 py-3 border-b border-gray-100"><h2 className="text-xs font-bold text-gray-500 uppercase tracking-widest flex items-center gap-2"><Fuel className="w-4 h-4 text-fuchsia-500" /> Meldungen</h2></div>
          {(tank.alarms || []).length === 0 ? <p className="text-sm text-gray-400 px-5 py-6">Keine Meldungen.</p> : (
            <ul className="divide-y divide-gray-100">
              {tank.alarms.map(a => (
                <li key={a.id} className="px-5 py-2.5 text-sm flex items-center gap-3" data-testid={`tank-alarm-${a.id}`}>
                  <span className={`w-2 h-2 rounded-full shrink-0 ${a.resolved_at ? "bg-gray-300" : a.severity === "alarm" ? "bg-red-500" : "bg-amber-400"}`} />
                  <span className={`flex-1 ${a.resolved_at ? "text-gray-400" : "text-gray-800"}`}>{a.alarm_text}</span>
                  <span className="text-xs text-gray-400 shrink-0">{fmtTime(a.timestamp)}{a.resolved_at ? ` · erledigt ${fmtTime(a.resolved_at)}` : ""}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </main>
    </div>
  );
}
