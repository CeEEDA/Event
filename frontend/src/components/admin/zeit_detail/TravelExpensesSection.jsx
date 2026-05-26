/**
 * Reisekosten-Sektion (Travel Expenses) aus AdminZeitDetailPage.jsx extrahiert.
 */
import { Plane, Download, FileDown, Check, X, Trash2 } from "lucide-react";
import { Button } from "../../ui/button";

export default function TravelExpensesSection({
  payrollMonth,
  travelTrips,
  loadingTravel,
  downloadTravelXlsx,
  downloadTripPdf,
  approveTrip,
  rejectTrip,
  deleteTripAdmin,
}) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-4" data-testid="travel-section">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Plane className="w-4 h-4 text-cyan-600" />
          <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider">Reisekosten – {payrollMonth}</p>
        </div>
        {travelTrips.length > 0 && (
          <Button onClick={downloadTravelXlsx} size="sm" variant="outline" className="text-cyan-700 border-cyan-300 hover:bg-cyan-50" data-testid="travel-xlsx-btn">
            <Download className="w-3.5 h-3.5 mr-1" /> Excel (Steuerbüro)
          </Button>
        )}
      </div>

      {loadingTravel ? (
        <p className="text-sm text-gray-400 text-center py-3">Lade...</p>
      ) : travelTrips.length === 0 ? (
        <p className="text-sm text-gray-400 text-center py-3">Keine Reisen in diesem Monat</p>
      ) : (
        <>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-[10px] text-gray-400 uppercase tracking-wider">
                  <th className="text-left pb-2 pr-1 font-semibold">Datum</th>
                  <th className="text-left pb-2 px-1 font-semibold">Zweck</th>
                  <th className="text-left pb-2 px-1 font-semibold">Land</th>
                  <th className="text-right pb-2 px-1 font-semibold">VMA</th>
                  <th className="text-right pb-2 px-1 font-semibold">KM</th>
                  <th className="text-right pb-2 px-1 font-semibold">Übern.</th>
                  <th className="text-right pb-2 px-1 font-semibold">Sonst.</th>
                  <th className="text-right pb-2 px-1 font-semibold">Gesamt</th>
                  <th className="pb-2 px-1 font-semibold text-center">Status</th>
                  <th className="pb-2 pl-1 font-semibold"></th>
                </tr>
              </thead>
              <tbody>
                {travelTrips.map(t => {
                  const c = t.computed || {};
                  const dep = new Date(t.departure_at);
                  const statusCls = {
                    submitted: "bg-amber-100 text-amber-700",
                    approved: "bg-emerald-100 text-emerald-700",
                    rejected: "bg-red-100 text-red-700",
                  }[t.status] || "bg-gray-100 text-gray-700";
                  const statusLbl = { submitted: "Offen", approved: "Genehmigt", rejected: "Abgelehnt" }[t.status] || t.status;
                  return (
                    <tr key={t.id} className="border-t border-gray-50">
                      <td className="py-1 pr-1 text-gray-700 whitespace-nowrap">{dep.toLocaleDateString("de-DE", { day:"2-digit", month:"2-digit"})}</td>
                      <td className="py-1 px-1 max-w-[180px] truncate" title={t.trip_purpose}>{t.trip_purpose}</td>
                      <td className="py-1 px-1 text-gray-500">{c.country_name}</td>
                      <td className="py-1 px-1 text-right">{(c.per_diem_net || 0).toFixed(2)}€</td>
                      <td className="py-1 px-1 text-right text-gray-500">{(c.km_eur || 0).toFixed(2)}€</td>
                      <td className="py-1 px-1 text-right text-gray-500">{(c.accommodation_eur || 0).toFixed(2)}€</td>
                      <td className="py-1 px-1 text-right text-gray-500">{(c.other_eur || 0).toFixed(2)}€</td>
                      <td className="py-1 px-1 text-right font-bold">{(c.total_eur || 0).toFixed(2)}€</td>
                      <td className="py-1 px-1 text-center">
                        <span className={`text-[10px] font-semibold uppercase px-1.5 py-0.5 rounded ${statusCls}`} title={t.rejection_reason || ""}>
                          {statusLbl}
                        </span>
                      </td>
                      <td className="py-1 pl-1">
                        <div className="flex items-center justify-end gap-0.5">
                          <button onClick={() => downloadTripPdf(t.id)} className="p-1 text-gray-400 hover:text-cyan-600 rounded" title="PDF" data-testid={`tx-pdf-${t.id}`}>
                            <FileDown className="w-3.5 h-3.5" />
                          </button>
                          {t.status !== "approved" && (
                            <button onClick={() => approveTrip(t.id)} className="p-1 text-gray-400 hover:text-emerald-600 rounded" title="Genehmigen" data-testid={`tx-approve-${t.id}`}>
                              <Check className="w-3.5 h-3.5" />
                            </button>
                          )}
                          {t.status !== "rejected" && (
                            <button onClick={() => rejectTrip(t.id)} className="p-1 text-gray-400 hover:text-red-500 rounded" title="Ablehnen" data-testid={`tx-reject-${t.id}`}>
                              <X className="w-3.5 h-3.5" />
                            </button>
                          )}
                          <button onClick={() => deleteTripAdmin(t.id)} className="p-1 text-gray-400 hover:text-red-700 rounded" title="Löschen" data-testid={`tx-delete-${t.id}`}>
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          {/* Summen */}
          {(() => {
            const approved = travelTrips.filter(t => t.status === "approved");
            const submitted = travelTrips.filter(t => t.status === "submitted");
            const approvedTotal = approved.reduce((s, t) => s + (t.computed?.total_eur || 0), 0);
            const pendingTotal = submitted.reduce((s, t) => s + (t.computed?.total_eur || 0), 0);
            return (
              <div className="mt-3 pt-3 border-t border-gray-200 grid grid-cols-2 sm:grid-cols-3 gap-2">
                <div className="bg-emerald-50 rounded-lg p-2.5 text-center">
                  <p className="text-[10px] text-emerald-600 uppercase font-semibold">Genehmigt (in Lohn)</p>
                  <p className="text-lg font-bold text-emerald-700">{approvedTotal.toFixed(2)}€</p>
                  <p className="text-[10px] text-emerald-500">{approved.length} Reisen</p>
                </div>
                {submitted.length > 0 && (
                  <div className="bg-amber-50 rounded-lg p-2.5 text-center">
                    <p className="text-[10px] text-amber-600 uppercase font-semibold">Offen (Prüfung)</p>
                    <p className="text-lg font-bold text-amber-700">{pendingTotal.toFixed(2)}€</p>
                    <p className="text-[10px] text-amber-500">{submitted.length} Reisen</p>
                  </div>
                )}
                <div className="bg-cyan-50 rounded-lg p-2.5 text-center">
                  <p className="text-[10px] text-cyan-600 uppercase font-semibold">Steuerfrei nach §3 Nr.13/16 EStG</p>
                  <p className="text-[10px] text-cyan-700 mt-1.5">Nur „Genehmigt" fließt in die Lohnabrechnung</p>
                </div>
              </div>
            );
          })()}
        </>
      )}
    </div>
  );
}
