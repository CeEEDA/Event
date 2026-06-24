import { useState, useEffect } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "./ui/dialog";
import { Loader2, Package, CheckCircle2, CircleDashed, Clock } from "lucide-react";
import api from "../lib/api";
import { toast } from "sonner";

/**
 * Read-only Übersicht aller Artikel auf einen Auftrag.
 * Zeigt jede Gruppe + Item inkl. Liefer-Status (offen / teil / komplett).
 * Datenquelle: GET /api/orders/epirent/{pk}/delivery-notes/prefill?include_delivered=true
 */
export default function ArticleListDialog({ open, onOpenChange, orderPk }) {
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState(null);

  useEffect(() => {
    if (!open || !orderPk) return;
    setLoading(true);
    api.get(`/orders/epirent/${orderPk}/delivery-notes/prefill?include_delivered=true`)
      .then(r => setData(r.data))
      .catch(e => toast.error(`Artikelliste konnte nicht geladen werden: ${e?.response?.data?.detail || e.message}`))
      .finally(() => setLoading(false));
  }, [open, orderPk]);

  const itemStatus = (it) => {
    const total = Number(it.amount_total) || 0;
    const delivered = Number(it.amount_delivered) || 0;
    if (total <= 0) return null;
    if (delivered <= 0) return { label: "Offen", icon: CircleDashed, cls: "bg-gray-50 text-gray-600 border-gray-200" };
    if (delivered >= total) return { label: "Komplett geliefert", icon: CheckCircle2, cls: "bg-emerald-50 text-emerald-700 border-emerald-200" };
    return { label: `${delivered}/${total} geliefert`, icon: Clock, cls: "bg-amber-50 text-amber-700 border-amber-200" };
  };

  // Aggregierte Summen ueber alle Gruppen
  const groups = data?.groups || [];
  let totalArticles = 0, totalOpen = 0, totalDelivered = 0, totalWeight = 0;
  for (const g of groups) {
    for (const it of (g.items || [])) {
      if (it.is_heading) continue;
      totalArticles += 1;
      const tot = Number(it.amount_total) || 0;
      const del = Number(it.amount_delivered) || 0;
      totalOpen += Math.max(0, tot - del);
      totalDelivered += del;
      totalWeight += tot * (Number(it.weight_net) || 0);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-5xl max-h-[92vh] flex flex-col p-0" data-testid="article-list-dialog">
        <DialogHeader className="px-5 pt-5 pb-3 border-b">
          <DialogTitle className="flex items-center gap-2 text-base pr-10">
            <Package className="w-4 h-4 text-teal-600" />
            Artikelliste
            {data && <span className="text-xs text-gray-400 font-mono">Auftrag {data.order_no_fmt}</span>}
          </DialogTitle>
        </DialogHeader>

        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4">
          {loading ? (
            <div className="py-12 text-center text-gray-400"><Loader2 className="w-6 h-6 mx-auto animate-spin" /></div>
          ) : data ? (
            <>
              {/* Summary-Header */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3" data-testid="article-list-summary">
                <div className="bg-teal-50/70 border border-teal-100 rounded-lg p-3">
                  <div className="text-[10px] text-teal-600 uppercase font-semibold tracking-wide">Artikel-Positionen</div>
                  <div className="text-2xl font-bold text-teal-900 mt-0.5" data-testid="summary-articles">{totalArticles}</div>
                </div>
                <div className="bg-gray-50 border border-gray-100 rounded-lg p-3">
                  <div className="text-[10px] text-gray-500 uppercase font-semibold tracking-wide">Noch offen</div>
                  <div className="text-2xl font-bold text-gray-800 mt-0.5" data-testid="summary-open">{totalOpen.toLocaleString("de-DE")}</div>
                </div>
                <div className="bg-emerald-50 border border-emerald-100 rounded-lg p-3">
                  <div className="text-[10px] text-emerald-600 uppercase font-semibold tracking-wide">Bereits geliefert</div>
                  <div className="text-2xl font-bold text-emerald-800 mt-0.5" data-testid="summary-delivered">{totalDelivered.toLocaleString("de-DE")}</div>
                </div>
                <div className="bg-orange-50 border border-orange-100 rounded-lg p-3">
                  <div className="text-[10px] text-orange-600 uppercase font-semibold tracking-wide">Gesamtgewicht</div>
                  <div className="text-2xl font-bold text-orange-800 mt-0.5" data-testid="summary-weight">{totalWeight.toFixed(0)} <span className="text-sm font-normal">kg</span></div>
                </div>
              </div>

              {groups.length === 0 && (
                <div className="text-center text-sm text-gray-400 py-8">Keine Artikel im Auftrag</div>
              )}

              {groups.map((g, gIdx) => {
                const articleItems = (g.items || []).filter(it => !it.is_heading);
                return (
                  <div key={(g.chapter_pk || "manual") + "-" + gIdx} className="bg-white rounded-lg border border-teal-200/60" data-testid={`overview-group-${gIdx}`}>
                    <div className="px-3 py-2 bg-teal-50/70 border-b border-teal-200/60 rounded-t-lg flex items-center gap-2">
                      <span className="text-xs font-mono text-teal-500">{g.chapter_pos}</span>
                      <h3 className="text-sm font-bold text-teal-800 flex-1 truncate">{g.chapter_title}</h3>
                      <span className="text-[11px] text-teal-600/80">{articleItems.length} Artikel</span>
                    </div>
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead className="bg-gray-50 text-[11px] text-gray-500 uppercase tracking-wide">
                          <tr>
                            <th className="text-left px-3 py-1.5 w-20">Pos.</th>
                            <th className="text-left px-3 py-1.5 w-24">Art-Nr.</th>
                            <th className="text-left px-3 py-1.5">Bezeichnung</th>
                            <th className="text-right px-3 py-1.5 w-24">Menge</th>
                            <th className="text-left px-3 py-1.5 w-20">Einheit</th>
                            <th className="text-right px-3 py-1.5 w-24">Gewicht</th>
                            <th className="text-left px-3 py-1.5 w-48">Status</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-100">
                          {(g.items || []).map((it, iIdx) => (
                            it.is_heading ? (
                              <tr key={iIdx} className="bg-gray-50/80">
                                <td className="px-3 py-1.5 text-[10px] text-gray-400 uppercase tracking-wide italic">Überschrift</td>
                                <td className="px-3 py-1.5" colSpan={6}>
                                  <span className="text-xs italic font-medium text-gray-700">{it.title}</span>
                                </td>
                              </tr>
                            ) : (() => {
                              const st = itemStatus(it);
                              const StIcon = st?.icon;
                              const totalW = (Number(it.weight_net) || 0) * (Number(it.amount_total) || 0);
                              return (
                                <tr key={iIdx} data-testid={`overview-item-${gIdx}-${iIdx}`}>
                                  <td className="px-3 py-1.5 text-xs font-mono text-gray-500">{it.pos}</td>
                                  <td className="px-3 py-1.5 text-xs text-gray-500">{it.product_no || "—"}</td>
                                  <td className="px-3 py-1.5 text-xs font-medium text-gray-900">{it.title}</td>
                                  <td className="px-3 py-1.5 text-xs text-right font-semibold tabular-nums">{Number(it.amount_total) || 0}</td>
                                  <td className="px-3 py-1.5 text-xs text-gray-600">{it.unit}</td>
                                  <td className="px-3 py-1.5 text-xs text-right text-gray-500 tabular-nums">
                                    {totalW > 0 ? `${totalW.toFixed(0)} kg` : "—"}
                                  </td>
                                  <td className="px-3 py-1.5">
                                    {st && (
                                      <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full border text-[10px] font-medium ${st.cls}`}>
                                        <StIcon className="w-3 h-3" /> {st.label}
                                      </span>
                                    )}
                                  </td>
                                </tr>
                              );
                            })()
                          ))}
                          {(g.items || []).length === 0 && (
                            <tr><td colSpan={7} className="px-3 py-4 text-center text-xs text-gray-400 italic">Keine Artikel in dieser Gruppe</td></tr>
                          )}
                        </tbody>
                      </table>
                    </div>
                  </div>
                );
              })}
            </>
          ) : (
            <div className="py-8 text-center text-gray-400 text-sm">Keine Daten verfügbar</div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
