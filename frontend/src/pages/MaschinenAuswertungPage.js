import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { Logo } from "../components/Logo";
import api from "../lib/api";
import { toast } from "sonner";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { ArrowLeft, BarChart3, AlertTriangle, Wrench, CheckCircle } from "lucide-react";

export default function MaschinenAuswertungPage() {
  const navigate = useNavigate();
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [searchText, setSearchText] = useState("");

  const loadStats = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (dateFrom) params.set("date_from", dateFrom);
      if (dateTo) params.set("date_to", dateTo);
      if (searchText.trim()) params.set("search", searchText.trim());
      const res = await api.get(`/serviceplan/fault-reports/stats?${params}`);
      setStats(res.data);
    } catch { toast.error("Fehler beim Laden der Statistiken"); }
    finally { setLoading(false); }
  }, [dateFrom, dateTo, searchText]);

  useEffect(() => { loadStats(); }, [loadStats]);

  return (
    <div className="min-h-screen bg-gray-50" data-testid="maschinen-auswertung-page">
      <header className="sticky top-0 z-10 bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Button variant="ghost" size="sm" onClick={() => navigate("/verwaltung")} className="text-gray-600 hover:text-fuchsia-600" data-testid="back-btn">
              <ArrowLeft className="w-4 h-4 mr-1" /> Zurück
            </Button>
            <div className="h-5 w-px bg-gray-200" />
            <BarChart3 className="w-5 h-5 text-fuchsia-600" />
            <h1 className="text-base font-semibold text-gray-900">Maschinen-Auswertung</h1>
          </div>
          <Logo size="small" />
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-4 py-6">
        {/* Zeitraum-Filter */}
        <div className="bg-white border border-gray-200 rounded-lg p-4 mb-6">
          <div className="flex items-end gap-4 flex-wrap">
            <div className="flex-1 min-w-[200px]">
              <Label className="text-gray-600 text-xs">Fehler suchen</Label>
              <Input placeholder="z.B. Kraftstofffilter, Motorschaden..." value={searchText} onChange={e => setSearchText(e.target.value)} className="mt-1 text-sm" data-testid="search-text" />
            </div>
            <div>
              <Label className="text-gray-600 text-xs">Von</Label>
              <Input type="date" value={dateFrom} onChange={e => setDateFrom(e.target.value)} className="mt-1 text-sm" data-testid="date-from" />
            </div>
            <div>
              <Label className="text-gray-600 text-xs">Bis</Label>
              <Input type="date" value={dateTo} onChange={e => setDateTo(e.target.value)} className="mt-1 text-sm" data-testid="date-to" />
            </div>
            <Button variant="outline" size="sm" onClick={() => { setDateFrom(""); setDateTo(""); setSearchText(""); }} className="text-xs">Zurücksetzen</Button>
          </div>
        </div>

        {loading ? (
          <div className="text-center py-20 text-gray-400">Laden...</div>
        ) : !stats ? (
          <div className="text-center py-16 text-gray-400">Keine Daten</div>
        ) : (
          <>
            {/* Übersichtskarten */}
            <div className="grid grid-cols-4 gap-3 mb-6">
              <div className="bg-white border border-gray-200 rounded-lg p-4 text-center">
                <p className="text-2xl font-bold text-gray-900">{stats.total_reports}</p>
                <p className="text-xs text-gray-500">Gesamt</p>
              </div>
              <div className="bg-white border border-red-200 rounded-lg p-4 text-center">
                <p className="text-2xl font-bold text-red-600">{stats.open}</p>
                <p className="text-xs text-gray-500">Offen</p>
              </div>
              <div className="bg-white border border-amber-200 rounded-lg p-4 text-center">
                <p className="text-2xl font-bold text-amber-600">{stats.in_arbeit}</p>
                <p className="text-xs text-gray-500">In Arbeit</p>
              </div>
              <div className="bg-white border border-emerald-200 rounded-lg p-4 text-center">
                <p className="text-2xl font-bold text-emerald-600">{stats.erledigt}</p>
                <p className="text-xs text-gray-500">Erledigt</p>
              </div>
            </div>

            {/* Maschinen-Tabelle */}
            {stats.devices.length === 0 ? (
              <div className="text-center py-16"><BarChart3 className="w-12 h-12 text-gray-300 mx-auto mb-4" /><p className="text-gray-500">Keine Störmeldungen im gewählten Zeitraum</p></div>
            ) : (
              <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
                <table className="w-full text-sm" data-testid="stats-table">
                  <thead className="bg-gray-50 border-b border-gray-200">
                    <tr>
                      <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase">Maschine</th>
                      <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase">Typ</th>
                      <th className="text-center px-4 py-3 text-xs font-semibold text-gray-500 uppercase">Gesamt</th>
                      <th className="text-center px-4 py-3 text-xs font-semibold text-gray-500 uppercase">Offen</th>
                      <th className="text-center px-4 py-3 text-xs font-semibold text-gray-500 uppercase">In Arbeit</th>
                      <th className="text-center px-4 py-3 text-xs font-semibold text-gray-500 uppercase">Erledigt</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {stats.devices.map(dev => (
                      <tr key={dev.device_id} className="hover:bg-gray-50" data-testid={`stat-row-${dev.device_serial}`}>
                        <td className="px-4 py-3">
                          <p className="font-medium text-gray-900">{dev.device_serial}</p>
                          <p className="text-[10px] text-gray-400">{dev.device_model}</p>
                        </td>
                        <td className="px-4 py-3 text-gray-600">{dev.device_type}</td>
                        <td className="px-4 py-3 text-center">
                          <span className={`inline-flex items-center justify-center w-8 h-8 rounded-full text-sm font-bold ${dev.total_faults > 3 ? "bg-red-100 text-red-700" : dev.total_faults > 1 ? "bg-amber-100 text-amber-700" : "bg-gray-100 text-gray-700"}`}>
                            {dev.total_faults}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-center">{dev.open > 0 ? <span className="text-red-600 font-semibold">{dev.open}</span> : <span className="text-gray-300">0</span>}</td>
                        <td className="px-4 py-3 text-center">{dev.in_arbeit > 0 ? <span className="text-amber-600 font-semibold">{dev.in_arbeit}</span> : <span className="text-gray-300">0</span>}</td>
                        <td className="px-4 py-3 text-center">{dev.erledigt > 0 ? <span className="text-emerald-600 font-semibold">{dev.erledigt}</span> : <span className="text-gray-300">0</span>}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>

                {/* Einzelne Störmeldungen pro Maschine */}
                {stats.devices.map(dev => dev.faults.length > 0 && (
                  <details key={dev.device_id} className="border-t border-gray-200">
                    <summary className="px-4 py-2 text-xs font-medium text-fuchsia-600 cursor-pointer hover:bg-fuchsia-50">
                      {dev.device_serial} - {dev.total_faults} Störmeldung(en) anzeigen
                    </summary>
                    <div className="px-4 pb-3 space-y-1">
                      {dev.faults.map(f => {
                        const statusIcon = f.status === "erledigt" ? <CheckCircle className="w-3.5 h-3.5 text-emerald-500" /> : f.status === "in_arbeit" ? <Wrench className="w-3.5 h-3.5 text-amber-500" /> : <AlertTriangle className="w-3.5 h-3.5 text-red-500" />;
                        return (
                          <div key={f.id} className="flex items-center gap-2 text-xs text-gray-600 py-1">
                            {statusIcon}
                            <span className="text-gray-400">{new Date(f.reported_at).toLocaleDateString("de-DE")}</span>
                            <span className="flex-1">{f.description}</span>
                            {f.repaired_at && <span className="text-emerald-500">Repariert: {new Date(f.repaired_at).toLocaleDateString("de-DE")}</span>}
                          </div>
                        );
                      })}
                    </div>
                  </details>
                ))}
              </div>
            )}
          </>
        )}
      </main>
    </div>
  );
}
