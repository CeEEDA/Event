import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import api from "../lib/api";
import { toast } from "sonner";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { ArrowLeft, Activity, Wifi, WifiOff, Calendar, Download, ChevronLeft, ChevronRight } from "lucide-react";
import { Logo } from "../components/Logo";

const uLow = (v) => v != null && v > 0 && v < 200;
const fBad = (v) => v != null && v > 0 && (v < 49 || v > 51);

const fmtDate = (iso) => {
  if (!iso) return "–";
  return new Date(iso).toLocaleString("de-DE", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit", second: "2-digit" });
};

const fmtShort = (iso) => {
  if (!iso) return "–";
  return new Date(iso).toLocaleDateString("de-DE");
};

export default function MeterDiagnosticsPage() {
  const { deviceId, meterId } = useParams();
  const navigate = useNavigate();

  const [data, setData] = useState(null);
  const [history, setHistory] = useState(null);
  const [loading, setLoading] = useState(true);

  // Date range - default: last 7 days
  const today = new Date().toISOString().slice(0, 10);
  const weekAgo = new Date(Date.now() - 7 * 86400000).toISOString().slice(0, 10);
  const [dateFrom, setDateFrom] = useState(weekAgo);
  const [dateTo, setDateTo] = useState(today);

  const fetchData = async (from, to) => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ limit: "200" });
      if (from) params.set("date_from", from);
      if (to) params.set("date_to", to);
      const [diagRes, histRes] = await Promise.all([
        api.get(`/devices/${deviceId}/meters/${meterId}/diagnostics?${params}`),
        api.get(`/devices/${deviceId}/meters/${meterId}/history`),
      ]);
      setData(diagRes.data);
      setHistory(histRes.data);
    } catch (err) {
      toast.error("Fehler beim Laden der Zählerdaten");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchData(dateFrom, dateTo); }, []);

  const handleFilter = () => fetchData(dateFrom, dateTo);

  const shiftDays = (days) => {
    const from = new Date(dateFrom);
    const to = new Date(dateTo);
    from.setDate(from.getDate() + days);
    to.setDate(to.getDate() + days);
    const newFrom = from.toISOString().slice(0, 10);
    const newTo = to.toISOString().slice(0, 10);
    setDateFrom(newFrom);
    setDateTo(newTo);
    fetchData(newFrom, newTo);
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-200 sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <button onClick={() => navigate("/devices")} className="flex items-center gap-1 text-gray-500 hover:text-fuchsia-600 transition-colors" data-testid="back-btn">
              <ArrowLeft className="w-4 h-4" /> <span className="text-sm">Zurück</span>
            </button>
            <span className="text-gray-300">|</span>
            <div className="flex items-center gap-2">
              <Activity className="w-5 h-5 text-fuchsia-500" />
              <h1 className="text-lg font-semibold text-gray-900" data-testid="page-title">
                {data?.meter_name || "Zähler"}
              </h1>
              <span className="text-xs text-gray-400 font-mono">{data?.device_name || ""}</span>
            </div>
          </div>
          <Logo />
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 py-5 space-y-5">
        {/* Date Range Filter */}
        <div className="bg-white rounded-lg border border-gray-200 p-4" data-testid="date-filter">
          <div className="flex flex-wrap items-end gap-3">
            <div>
              <label className="text-[10px] text-gray-500 uppercase tracking-wider block mb-1">Von</label>
              <Input type="date" value={dateFrom} onChange={e => setDateFrom(e.target.value)} className="h-8 text-sm w-36" data-testid="date-from" />
            </div>
            <div>
              <label className="text-[10px] text-gray-500 uppercase tracking-wider block mb-1">Bis</label>
              <Input type="date" value={dateTo} onChange={e => setDateTo(e.target.value)} className="h-8 text-sm w-36" data-testid="date-to" />
            </div>
            <Button size="sm" onClick={handleFilter} className="h-8 bg-fuchsia-600 hover:bg-fuchsia-700 text-white text-xs px-4" data-testid="filter-btn">
              <Calendar className="w-3.5 h-3.5 mr-1" /> Anzeigen
            </Button>
            <div className="flex gap-1">
              <Button size="sm" variant="outline" onClick={() => shiftDays(-7)} className="h-8 text-xs px-2" data-testid="shift-back">
                <ChevronLeft className="w-3.5 h-3.5" /> 7 Tage
              </Button>
              <Button size="sm" variant="outline" onClick={() => shiftDays(7)} className="h-8 text-xs px-2" data-testid="shift-forward">
                7 Tage <ChevronRight className="w-3.5 h-3.5" />
              </Button>
            </div>
            {data && <span className="text-xs text-gray-400 ml-2">{data.count} Messwerte</span>}
          </div>
        </div>

        {/* Assignment History */}
        {history && history.assignments?.length > 0 && (
          <div className="bg-white rounded-lg border border-gray-200" data-testid="assignment-history">
            <div className="px-4 py-2.5 border-b border-gray-100">
              <h2 className="text-sm font-semibold text-gray-900">Verknüpfungshistorie</h2>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="bg-gray-50 text-[10px] text-gray-500 uppercase tracking-wider">
                    <th className="px-3 py-1.5 text-left">Veranstaltung</th>
                    <th className="px-3 py-1.5 text-left">Zeitraum</th>
                    <th className="px-3 py-1.5 text-left">Firma / Kunde</th>
                    <th className="px-3 py-1.5 text-left">Fahrgeschäft</th>
                    <th className="px-3 py-1.5 text-left">Platz</th>
                    <th className="px-3 py-1.5 text-right">Einbau</th>
                    <th className="px-3 py-1.5 text-right">Ausbau</th>
                    <th className="px-3 py-1.5 text-right">Verbrauch</th>
                    <th className="px-3 py-1.5 text-left">Rechnung</th>
                    <th className="px-3 py-1.5 text-left">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {history.assignments.map((a, idx) => (
                    <tr key={idx} className={`border-t border-gray-100 ${a.is_current ? "bg-fuchsia-50/40" : "hover:bg-gray-50"}`} data-testid={`history-row-${idx}`}>
                      <td className="px-3 py-2 font-medium text-gray-900">{a.event_name}</td>
                      <td className="px-3 py-2 text-gray-500 whitespace-nowrap">{fmtShort(a.event_start)} – {fmtShort(a.event_end)}</td>
                      <td className="px-3 py-2 text-gray-700">{a.firma}{a.kunde !== "–" ? ` / ${a.kunde}` : ""}</td>
                      <td className="px-3 py-2 text-gray-600">{a.fahrgeschaeft}</td>
                      <td className="px-3 py-2 font-mono text-gray-600">{a.platznummer}</td>
                      <td className="px-3 py-2 text-right font-mono">{a.kwh_einbau != null ? a.kwh_einbau.toFixed(2) : "–"}</td>
                      <td className="px-3 py-2 text-right font-mono">{a.kwh_ausbau != null ? a.kwh_ausbau.toFixed(2) : "–"}</td>
                      <td className="px-3 py-2 text-right font-mono font-semibold text-fuchsia-700">{a.kwh_used != null ? a.kwh_used.toFixed(2) : "–"}</td>
                      <td className="px-3 py-2 text-emerald-600 font-mono">{a.invoice_number || "–"}</td>
                      <td className="px-3 py-2">
                        {a.is_current ? (
                          <span className="text-[10px] bg-fuchsia-100 text-fuchsia-700 px-1.5 py-0.5 rounded">Aktiv</span>
                        ) : (
                          <span className="text-[10px] bg-gray-100 text-gray-500 px-1.5 py-0.5 rounded">Beendet</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Measurement Data Table */}
        <div className="bg-white rounded-lg border border-gray-200" data-testid="measurement-table">
          <div className="px-4 py-2.5 border-b border-gray-100">
            <h2 className="text-sm font-semibold text-gray-900">Messdaten</h2>
          </div>
          {loading ? (
            <div className="py-8 text-center text-sm text-gray-400">Laden...</div>
          ) : !data || data.count === 0 ? (
            <div className="py-8 text-center text-sm text-gray-400">Keine Messdaten im gewählten Zeitraum</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-xs" data-testid="diagnostics-table">
                <thead>
                  <tr className="bg-gray-50 text-[10px] text-gray-500 uppercase tracking-wider">
                    <th className="px-3 py-1.5 text-left">Zeitstempel</th>
                    <th className="px-2 py-1.5 text-right">kWh</th>
                    <th className="px-2 py-1.5 text-right">kW</th>
                    <th className="px-2 py-1.5 text-right">U L1</th>
                    <th className="px-2 py-1.5 text-right">U L2</th>
                    <th className="px-2 py-1.5 text-right">U L3</th>
                    <th className="px-2 py-1.5 text-right">I L1</th>
                    <th className="px-2 py-1.5 text-right">I L2</th>
                    <th className="px-2 py-1.5 text-right">I L3</th>
                    <th className="px-2 py-1.5 text-right">I ges.</th>
                    <th className="px-2 py-1.5 text-right">Hz</th>
                    <th className="px-2 py-1.5 text-right">cos φ</th>
                  </tr>
                </thead>
                <tbody>
                  {data.data.map((row, idx) => (
                    <tr key={idx} className={`border-t border-gray-100 ${idx === 0 ? "bg-fuchsia-50/30 font-medium" : "hover:bg-gray-50"}`} data-testid={`diag-row-${idx}`}>
                      <td className="px-3 py-1.5 text-gray-700 whitespace-nowrap">{fmtDate(row.ts_utc)}</td>
                      <td className="px-2 py-1.5 text-right font-mono text-gray-900">{row.E_imp_kWh != null ? row.E_imp_kWh.toFixed(2) : "–"}</td>
                      <td className="px-2 py-1.5 text-right font-mono font-semibold text-fuchsia-700">{row.P_sum_kW != null ? row.P_sum_kW.toFixed(3) : "–"}</td>
                      <td className={`px-2 py-1.5 text-right font-mono ${uLow(row.U_L1) ? "text-red-600 font-bold" : "text-gray-700"}`}>{row.U_L1 != null ? row.U_L1.toFixed(1) : "–"}</td>
                      <td className={`px-2 py-1.5 text-right font-mono ${uLow(row.U_L2) ? "text-red-600 font-bold" : "text-gray-700"}`}>{row.U_L2 != null ? row.U_L2.toFixed(1) : "–"}</td>
                      <td className={`px-2 py-1.5 text-right font-mono ${uLow(row.U_L3) ? "text-red-600 font-bold" : "text-gray-700"}`}>{row.U_L3 != null ? row.U_L3.toFixed(1) : "–"}</td>
                      <td className="px-2 py-1.5 text-right font-mono text-gray-600">{row.I_L1 != null ? row.I_L1.toFixed(2) : "–"}</td>
                      <td className="px-2 py-1.5 text-right font-mono text-gray-600">{row.I_L2 != null ? row.I_L2.toFixed(2) : "–"}</td>
                      <td className="px-2 py-1.5 text-right font-mono text-gray-600">{row.I_L3 != null ? row.I_L3.toFixed(2) : "–"}</td>
                      <td className="px-2 py-1.5 text-right font-mono text-gray-700">{row.I_sum != null ? row.I_sum.toFixed(2) : "–"}</td>
                      <td className={`px-2 py-1.5 text-right font-mono ${fBad(row.F_Hz) ? "text-amber-600 font-bold" : "text-gray-700"}`}>{row.F_Hz != null ? row.F_Hz.toFixed(1) : "–"}</td>
                      <td className="px-2 py-1.5 text-right font-mono text-gray-700">{row.cosphi != null ? row.cosphi.toFixed(2) : "–"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
