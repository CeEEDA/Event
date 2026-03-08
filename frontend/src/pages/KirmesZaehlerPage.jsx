import { useState, useEffect, useCallback } from "react";
import { useParams, useNavigate, useSearchParams } from "react-router-dom";
import api, { getErrorMsg } from "../lib/api";
import { toast } from "sonner";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import {
  ArrowLeft, Zap, Activity, Gauge, Download, RefreshCw,
  Clock, Plug, TrendingUp, CalendarDays,
} from "lucide-react";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Area, AreaChart,
} from "recharts";

function MetricCard({ icon: Icon, label, value, unit, color }) {
  return (
    <div className="bg-white border border-gray-200 rounded-lg p-4" data-testid={`metric-${label.toLowerCase().replace(/\s/g, "-")}`}>
      <div className="flex items-center gap-2 mb-2">
        <div className={`w-8 h-8 rounded-lg ${color} flex items-center justify-center`}>
          <Icon className="w-4 h-4 text-white" />
        </div>
        <span className="text-xs text-gray-500">{label}</span>
      </div>
      <p className="text-xl font-bold text-gray-900 font-mono">
        {value != null ? value : "–"}
        {value != null && unit && <span className="text-sm font-normal text-gray-400 ml-1">{unit}</span>}
      </p>
    </div>
  );
}

function toLocalDateStr(d) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

export default function KirmesZaehlerPage() {
  const { eventId, signupId } = useParams();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  const [event, setEvent] = useState(null);
  const [signup, setSignup] = useState(null);
  const [meterData, setMeterData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(false);

  // Date range from event or query params
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

  const loadData = useCallback(async () => {
    try {
      const evtRes = await api.get(`/kirmes/events/${eventId}`);
      const evt = evtRes.data;
      setEvent(evt);

      const s = evt.signups?.find(s => s.id === signupId);
      if (!s) { toast.error("Anmeldung nicht gefunden"); navigate(`/kirmes/${eventId}`); return; }
      setSignup(s);

      // Set date range from event
      if (!dateFrom) setDateFrom(evt.start_date || toLocalDateStr(new Date()));
      if (!dateTo) setDateTo(evt.end_date || toLocalDateStr(new Date()));
    } catch {
      toast.error("Fehler beim Laden");
      navigate(`/kirmes/${eventId}`);
    } finally {
      setLoading(false);
    }
  }, [eventId, signupId, navigate, dateFrom, dateTo]);

  const loadMeterData = useCallback(async () => {
    if (!signupId) return;
    try {
      const params = { limit: 5000 };
      if (dateFrom) params.from_time = new Date(dateFrom).toISOString();
      if (dateTo) params.to_time = new Date(dateTo + "T23:59:59").toISOString();
      const r = await api.get(`/kirmes/signups/${signupId}/meter-data`, { params });
      setMeterData(r.data);
    } catch { /* ignore */ }
  }, [signupId, dateFrom, dateTo]);

  useEffect(() => { loadData(); }, [loadData]);
  useEffect(() => { if (!loading) loadMeterData(); }, [loading, loadMeterData]);

  // Auto-refresh every 30s
  useEffect(() => {
    const iv = setInterval(loadMeterData, 30000);
    return () => clearInterval(iv);
  }, [loadMeterData]);

  const handleExportCSV = async () => {
    setExporting(true);
    try {
      const params = { limit: 999999 };
      if (dateFrom) params.from_time = new Date(dateFrom).toISOString();
      if (dateTo) params.to_time = new Date(dateTo + "T23:59:59").toISOString();
      const r = await api.get(`/kirmes/signups/${signupId}/meter-data`, { params });
      const history = r.data?.history || [];
      if (history.length === 0) { toast.error("Keine Daten zum Exportieren"); return; }

      const cols = ["ts_utc", "P_sum_kW", "I_sum", "U_L1", "F_Hz", "E_imp_kWh"];
      const headers = ["Zeitstempel", "Leistung (kW)", "Strom (A)", "Spannung (V)", "Frequenz (Hz)", "Energie (kWh)"];
      let csv = headers.join(";") + "\n";
      for (const row of history) {
        csv += cols.map(c => row[c] ?? "").join(";") + "\n";
      }

      const blob = new Blob(["\uFEFF" + csv], { type: "text/csv;charset=utf-8;" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      const meterName = signup?.emu_meter_name || "Zaehler";
      a.download = `Zaehlerdaten_${meterName}_${dateFrom}_${dateTo}.csv`;
      a.click();
      URL.revokeObjectURL(url);
      toast.success(`${history.length} Datenpunkte exportiert`);
    } catch (err) {
      toast.error(getErrorMsg(err, "Export fehlgeschlagen"));
    } finally {
      setExporting(false);
    }
  };

  if (loading) return <div className="min-h-screen bg-gray-50 flex items-center justify-center text-gray-400">Laden...</div>;

  const latest = meterData?.latest;
  const history = meterData?.history || [];
  const isOnline = meterData?.is_online;
  const linked = meterData?.linked;

  // Chart data
  const chartData = history.map(h => ({
    time: h.ts_utc ? new Date(h.ts_utc).toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" }) : "",
    date: h.ts_utc ? new Date(h.ts_utc).toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit" }) : "",
    leistung: h.P_sum_kW != null ? parseFloat(h.P_sum_kW.toFixed(3)) : null,
    strom: h.I_sum != null ? parseFloat(h.I_sum.toFixed(2)) : null,
    spannung: h.U_L1 != null ? parseFloat(h.U_L1.toFixed(1)) : null,
    energie: h.E_imp_kWh != null ? parseFloat(h.E_imp_kWh.toFixed(2)) : null,
  }));

  const schausteller = signup?.schausteller;

  return (
    <div className="min-h-screen bg-gray-50" data-testid="zaehler-page">
      <header className="sticky top-0 z-10 bg-white border-b border-gray-200">
        <div className="max-w-6xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Button variant="ghost" size="sm" onClick={() => navigate(`/kirmes/${eventId}`)} className="text-gray-600 hover:text-fuchsia-600" data-testid="back-btn">
              <ArrowLeft className="w-4 h-4 mr-1" /> Zurück
            </Button>
            <div className="h-5 w-px bg-gray-200" />
            <div>
              <h1 className="text-base font-semibold text-gray-900">Zählerdaten</h1>
              <p className="text-xs text-gray-500">
                {signup?.emu_meter_name || "–"} · {schausteller?.name || "–"} · {signup?.fahrgeschaeft || "–"}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {isOnline != null && (
              <span className={`text-xs px-2 py-1 rounded-full ${isOnline ? "bg-emerald-100 text-emerald-700" : "bg-gray-100 text-gray-500"}`}>
                {isOnline ? "Online" : "Offline"}
              </span>
            )}
            <Button size="sm" variant="outline" onClick={loadMeterData} className="text-xs" data-testid="refresh-btn">
              <RefreshCw className="w-3 h-3 mr-1" /> Aktualisieren
            </Button>
          </div>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-4 py-6 space-y-6">
        {/* Event Period Info */}
        <div className="bg-white border border-gray-200 rounded-xl p-4" data-testid="event-period">
          <div className="flex flex-wrap items-center gap-6">
            <div className="flex items-center gap-2">
              <CalendarDays className="w-4 h-4 text-fuchsia-500" />
              <span className="text-sm font-semibold text-gray-900">{event?.name}</span>
            </div>
            <div className="flex items-center gap-3">
              <div>
                <label className="text-[10px] text-gray-400 block">Von</label>
                <Input type="date" value={dateFrom} onChange={e => setDateFrom(e.target.value)}
                  className="h-8 text-xs w-36" data-testid="date-from" />
              </div>
              <div>
                <label className="text-[10px] text-gray-400 block">Bis</label>
                <Input type="date" value={dateTo} onChange={e => setDateTo(e.target.value)}
                  className="h-8 text-xs w-36" data-testid="date-to" />
              </div>
            </div>
            <Button size="sm" onClick={handleExportCSV} disabled={exporting || !linked}
              className="bg-emerald-600 hover:bg-emerald-700 text-white text-xs ml-auto" data-testid="export-csv-btn">
              <Download className="w-3 h-3 mr-1" /> {exporting ? "Exportiert..." : "CSV Export"}
            </Button>
          </div>
        </div>

        {!linked ? (
          <div className="text-center py-12 text-gray-400">
            <Plug className="w-12 h-12 mx-auto mb-3 text-gray-300" />
            <p className="text-sm">Kein Zähler verknüpft</p>
            <p className="text-xs mt-1">Verknüpfen Sie einen EMU-Zähler auf der Event-Detailseite</p>
          </div>
        ) : (
          <>
            {/* Live Metrics */}
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3" data-testid="live-metrics">
              <MetricCard icon={Zap} label="Leistung" value={latest?.P_sum_kW?.toFixed(3)} unit="kW" color="bg-fuchsia-500" />
              <MetricCard icon={Activity} label="Strom" value={latest?.I_sum?.toFixed(2)} unit="A" color="bg-blue-500" />
              <MetricCard icon={Gauge} label="Spannung" value={latest?.U_L1?.toFixed(1)} unit="V" color="bg-amber-500" />
              <MetricCard icon={TrendingUp} label="Energie" value={latest?.E_imp_kWh?.toFixed(2)} unit="kWh" color="bg-emerald-500" />
              <MetricCard icon={Clock} label="Frequenz" value={latest?.F_Hz?.toFixed(1)} unit="Hz" color="bg-purple-500" />
            </div>

            {/* Charts */}
            {chartData.length > 0 ? (
              <div className="space-y-4">
                {/* Power Chart */}
                <div className="bg-white border border-gray-200 rounded-xl p-4" data-testid="chart-power">
                  <h3 className="text-sm font-semibold text-gray-900 mb-3 flex items-center gap-2">
                    <Zap className="w-4 h-4 text-fuchsia-500" /> Leistungsverlauf (kW)
                  </h3>
                  <ResponsiveContainer width="100%" height={240}>
                    <AreaChart data={chartData}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                      <XAxis dataKey="time" tick={{ fontSize: 10 }} />
                      <YAxis tick={{ fontSize: 10 }} />
                      <Tooltip contentStyle={{ fontSize: 12 }} />
                      <Area type="monotone" dataKey="leistung" stroke="#d946ef" fill="#d946ef" fillOpacity={0.1} name="kW" />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>

                {/* Current Chart */}
                <div className="bg-white border border-gray-200 rounded-xl p-4" data-testid="chart-current">
                  <h3 className="text-sm font-semibold text-gray-900 mb-3 flex items-center gap-2">
                    <Activity className="w-4 h-4 text-blue-500" /> Stromverlauf (A)
                  </h3>
                  <ResponsiveContainer width="100%" height={200}>
                    <LineChart data={chartData}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                      <XAxis dataKey="time" tick={{ fontSize: 10 }} />
                      <YAxis tick={{ fontSize: 10 }} />
                      <Tooltip contentStyle={{ fontSize: 12 }} />
                      <Line type="monotone" dataKey="strom" stroke="#3b82f6" dot={false} name="A" />
                    </LineChart>
                  </ResponsiveContainer>
                </div>

                {/* Energy Chart */}
                <div className="bg-white border border-gray-200 rounded-xl p-4" data-testid="chart-energy">
                  <h3 className="text-sm font-semibold text-gray-900 mb-3 flex items-center gap-2">
                    <TrendingUp className="w-4 h-4 text-emerald-500" /> Energieverbrauch (kWh)
                  </h3>
                  <ResponsiveContainer width="100%" height={200}>
                    <AreaChart data={chartData}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                      <XAxis dataKey="time" tick={{ fontSize: 10 }} />
                      <YAxis tick={{ fontSize: 10 }} />
                      <Tooltip contentStyle={{ fontSize: 12 }} />
                      <Area type="monotone" dataKey="energie" stroke="#10b981" fill="#10b981" fillOpacity={0.1} name="kWh" />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              </div>
            ) : (
              <div className="bg-white border border-gray-200 rounded-xl p-8 text-center text-gray-400">
                <Activity className="w-10 h-10 mx-auto mb-3 text-gray-300" />
                <p className="text-sm">Keine Messdaten im gewählten Zeitraum</p>
                <p className="text-xs mt-1">Passen Sie den Zeitraum an oder warten Sie auf neue Daten</p>
              </div>
            )}

            {/* Data Summary */}
            {history.length > 0 && (
              <div className="bg-white border border-gray-200 rounded-xl p-4" data-testid="data-summary">
                <h3 className="text-sm font-semibold text-gray-900 mb-2">Zusammenfassung</h3>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
                  <div>
                    <span className="text-gray-400">Datenpunkte</span>
                    <p className="font-mono font-semibold">{history.length}</p>
                  </div>
                  <div>
                    <span className="text-gray-400">Max. Leistung</span>
                    <p className="font-mono font-semibold">{Math.max(...history.filter(h => h.P_sum_kW != null).map(h => h.P_sum_kW)).toFixed(3)} kW</p>
                  </div>
                  <div>
                    <span className="text-gray-400">Max. Strom</span>
                    <p className="font-mono font-semibold">{Math.max(...history.filter(h => h.I_sum != null).map(h => h.I_sum)).toFixed(2)} A</p>
                  </div>
                  <div>
                    <span className="text-gray-400">Zeitraum</span>
                    <p className="font-mono font-semibold">{dateFrom} – {dateTo}</p>
                  </div>
                </div>
              </div>
            )}
          </>
        )}
      </main>
    </div>
  );
}
