import { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowLeft, Search, ArrowRight, MapPin, Calendar, User, Hash, AlertTriangle, RefreshCw, Loader2 } from "lucide-react";
import { Input } from "../components/ui/input";
import { Button } from "../components/ui/button";
import api from "../lib/api";
import { toast } from "sonner";

/**
 * AdminAssetMoveAuditPage
 *
 * Komplette Verschoben-Historie aller Assets: zeigt, welcher Artikel
 * wann von wem aus welchem Auftrag in welchen anderen Auftrag verschoben
 * wurde - und wo er JETZT lebt. Dadurch lassen sich "verlorene" Standorte
 * sofort wiederfinden und ggf. zurueckholen.
 */
export default function AdminAssetMoveAuditPage() {
  const navigate = useNavigate();
  const [moves, setMoves] = useState([]);
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState("");
  const [filterOrder, setFilterOrder] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = {};
      if (q.trim()) params.q = q.trim();
      if (filterOrder.trim() && /^\d+$/.test(filterOrder.trim())) params.order_pk = filterOrder.trim();
      const res = await api.get("/orders/asset-move-audit", { params });
      setMoves(res.data.moves || []);
    } catch (e) {
      toast.error("Audit konnte nicht geladen werden: " + (e.response?.data?.detail || e.message));
    } finally {
      setLoading(false);
    }
  }, [q, filterOrder]);

  useEffect(() => { load(); }, [load]);

  const fmtDate = (iso) => {
    if (!iso) return "—";
    try { return new Date(iso).toLocaleString("de-DE", { day: "2-digit", month: "2-digit", year: "2-digit", hour: "2-digit", minute: "2-digit" }); }
    catch { return iso; }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 py-4 flex items-center gap-3">
          <button onClick={() => navigate("/admin")} className="p-2 -ml-2 hover:bg-gray-100 rounded-lg" data-testid="back-to-admin">
            <ArrowLeft className="w-5 h-5" />
          </button>
          <div className="flex-1">
            <h1 className="text-lg font-bold text-gray-900">Verschoben-Audit</h1>
            <p className="text-xs text-gray-500">Alle Asset-Verschiebungen zwischen Aufträgen — Quelle, Ziel, aktueller Standort</p>
          </div>
          <button onClick={load} className="p-2 hover:bg-gray-100 rounded-lg text-gray-500" data-testid="reload-audit">
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
          </button>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 py-6 space-y-4">
        {/* Filter-Leiste */}
        <div className="bg-white border border-gray-200 rounded-lg p-4 flex gap-3 flex-wrap items-end">
          <div className="flex-1 min-w-[200px]">
            <label className="text-xs font-medium text-gray-600 mb-1 block">Suche (Label, Typ, User, Auftragsnummer)</label>
            <div className="relative">
              <Search className="absolute left-2.5 top-2.5 w-4 h-4 text-gray-400" />
              <Input
                value={q}
                onChange={e => setQ(e.target.value)}
                placeholder="z.B. Lichtmast, Ecker, 260123-01…"
                className="pl-9 text-sm"
                data-testid="audit-search"
              />
            </div>
          </div>
          <div className="w-44">
            <label className="text-xs font-medium text-gray-600 mb-1 block">Nur Quell-Auftrag (PK)</label>
            <Input
              value={filterOrder}
              onChange={e => setFilterOrder(e.target.value)}
              placeholder="z.B. 158"
              type="number"
              className="text-sm"
              data-testid="audit-filter-order"
            />
          </div>
          <div className="text-xs text-gray-500 ml-auto">
            <span className="font-bold text-gray-700">{moves.length}</span> Verschiebungen
          </div>
        </div>

        {/* Liste / Tabelle */}
        {loading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-6 h-6 animate-spin text-fuchsia-500" />
          </div>
        ) : !moves.length ? (
          <div className="text-center py-12 text-sm text-gray-400">
            <AlertTriangle className="w-8 h-8 mx-auto mb-2 text-gray-300" />
            Keine Asset-Verschiebungen im System.
          </div>
        ) : (
          <div className="bg-white border border-gray-200 rounded-lg overflow-hidden" data-testid="audit-list">
            {/* Desktop Tabelle */}
            <div className="hidden lg:block overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-gray-50 border-b border-gray-200 text-[11px] uppercase tracking-wide text-gray-500">
                  <tr>
                    <th className="px-3 py-2 text-left">Artikel</th>
                    <th className="px-3 py-2 text-left">Quelle</th>
                    <th className="px-3 py-2 text-center w-8"></th>
                    <th className="px-3 py-2 text-left">Ziel (zum Zeitpunkt)</th>
                    <th className="px-3 py-2 text-left">Jetziger Standort</th>
                    <th className="px-3 py-2 text-left">Wer</th>
                    <th className="px-3 py-2 text-left">Wann</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {moves.map((m, idx) => {
                    const movedAway = m.from_pk !== m.current_pk;
                    return (
                      <tr key={`${m.asset_id}-${idx}`} className="hover:bg-gray-50" data-testid={`audit-row-${m.asset_id}`}>
                        <td className="px-3 py-2.5">
                          <div className="font-medium text-gray-900">{m.label || "—"}</div>
                          <div className="text-[11px] text-gray-500">{m.asset_type}</div>
                        </td>
                        <td className="px-3 py-2.5 text-xs">
                          <button
                            onClick={() => navigate(`/orders/${m.from_pk}`)}
                            className="text-fuchsia-600 hover:underline font-mono"
                            data-testid={`audit-jump-from-${m.asset_id}-${idx}`}
                          >
                            {m.from_order_no}
                          </button>
                          {m.from_event && <div className="text-[10px] text-gray-400 truncate max-w-[180px]">{m.from_event}</div>}
                        </td>
                        <td className="px-3 py-2.5 text-center">
                          <ArrowRight className="w-3.5 h-3.5 text-gray-400 inline" />
                        </td>
                        <td className="px-3 py-2.5 text-xs">
                          <button
                            onClick={() => navigate(`/orders/${m.to_pk}`)}
                            className="text-fuchsia-600 hover:underline font-mono"
                          >
                            {m.to_order_no}
                          </button>
                        </td>
                        <td className="px-3 py-2.5 text-xs">
                          <button
                            onClick={() => navigate(`/orders/${m.current_pk}`)}
                            className={`hover:underline font-mono ${movedAway ? "text-emerald-700 font-semibold" : "text-gray-500"}`}
                            data-testid={`audit-jump-current-${m.asset_id}-${idx}`}
                          >
                            {m.current_order_no}
                          </button>
                          {m.current_event && <div className="text-[10px] text-gray-400 truncate max-w-[180px]">{m.current_event}</div>}
                        </td>
                        <td className="px-3 py-2.5 text-xs text-gray-700">
                          <div className="inline-flex items-center gap-1"><User className="w-3 h-3 text-gray-400" /> {m.moved_by}</div>
                        </td>
                        <td className="px-3 py-2.5 text-xs text-gray-500 whitespace-nowrap">
                          <div className="inline-flex items-center gap-1"><Calendar className="w-3 h-3 text-gray-400" /> {fmtDate(m.moved_at)}</div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {/* Mobile Cards */}
            <div className="lg:hidden divide-y divide-gray-100">
              {moves.map((m, idx) => (
                <div key={`${m.asset_id}-${idx}`} className="p-3" data-testid={`audit-card-${m.asset_id}`}>
                  <div className="flex items-center justify-between gap-2 mb-2">
                    <div>
                      <div className="font-semibold text-sm text-gray-900">{m.label}</div>
                      <div className="text-[10px] text-gray-500">{m.asset_type}</div>
                    </div>
                    <div className="text-[10px] text-gray-500 text-right">
                      <div className="inline-flex items-center gap-1"><User className="w-3 h-3" /> {m.moved_by}</div>
                      <div>{fmtDate(m.moved_at)}</div>
                    </div>
                  </div>
                  <div className="flex items-center gap-2 text-xs">
                    <button onClick={() => navigate(`/orders/${m.from_pk}`)} className="font-mono text-fuchsia-600 hover:underline">{m.from_order_no}</button>
                    <ArrowRight className="w-3.5 h-3.5 text-gray-400" />
                    <button onClick={() => navigate(`/orders/${m.current_pk}`)} className="font-mono text-emerald-700 hover:underline font-semibold">{m.current_order_no}</button>
                  </div>
                  {m.plus_code && (
                    <div className="mt-1.5 text-[10px] text-gray-500 inline-flex items-center gap-1"><MapPin className="w-3 h-3" /> {m.plus_code}</div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="text-[10px] text-gray-400">
          <Hash className="w-3 h-3 inline mr-1" />
          Quelle: Audit-Kommentare „Verschoben aus Auftrag #X nach #Y" in `order_assets.comments`.
        </div>
      </div>
    </div>
  );
}
