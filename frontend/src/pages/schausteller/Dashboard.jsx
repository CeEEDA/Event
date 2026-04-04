import { Button } from "../../components/ui/button";
import { CalendarDays, MapPin, Zap, FileText, Download, LayoutDashboard, Plus } from "lucide-react";
import { BACKEND_URL, STATUS_LABELS } from "./constants";

export function Dashboard({ schausteller, myBookings, lastdiagramme, onNewBooking, onDownloadInvoice, onPurchaseLastdiagramm, onDownloadLastdiagramm, ldPurchasing, ldDownloading }) {
  return (
    <div data-testid="dashboard-step">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-lg font-bold text-gray-900">Mein Bereich</h2>
          <p className="text-sm text-gray-500">{schausteller.firma ? `${schausteller.firma} · ` : ""}{schausteller.name}</p>
        </div>
        <Button size="sm" onClick={onNewBooking} className="bg-fuchsia-600 hover:bg-fuchsia-700 text-white" data-testid="new-booking-btn">
          <Plus className="w-4 h-4 mr-1" /> Neue Anmeldung
        </Button>
      </div>

      {/* Buchungen */}
      <div className="bg-white border border-gray-200 rounded-xl overflow-hidden mb-4">
        <div className="px-4 py-3 bg-gray-50 border-b border-gray-200 flex items-center gap-2">
          <LayoutDashboard className="w-4 h-4 text-fuchsia-600" />
          <span className="text-sm font-semibold text-gray-700">Meine Buchungen ({myBookings.signups.length})</span>
        </div>
        {myBookings.signups.length === 0 ? (
          <div className="p-6 text-center text-sm text-gray-400">Noch keine Buchungen vorhanden</div>
        ) : (
          <div className="divide-y divide-gray-100">
            {myBookings.signups.map(s => {
              const st = STATUS_LABELS[s.payment_status] || STATUS_LABELS.ausstehend;
              return (
                <div key={s.id} className="px-4 py-3" data-testid={`booking-${s.id}`}>
                  <div className="flex items-start justify-between">
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-semibold text-gray-900">{s.event?.name || "–"}</p>
                      <div className="flex flex-wrap gap-x-3 gap-y-1 mt-1 text-xs text-gray-500">
                        {s.event?.location && <span className="flex items-center gap-1"><MapPin className="w-3 h-3" />{s.event.location}</span>}
                        {s.event?.start_date && <span className="flex items-center gap-1"><CalendarDays className="w-3 h-3" />{new Date(s.event.start_date).toLocaleDateString("de-DE")} – {new Date(s.event.end_date).toLocaleDateString("de-DE")}</span>}
                      </div>
                      <div className="flex flex-wrap gap-x-3 gap-y-1 mt-1 text-xs text-gray-500">
                        <span>Platz: <strong>{s.platznummer}</strong></span>
                        <span>{s.fahrgeschaeft}</span>
                        <span className="flex items-center gap-1"><Zap className="w-3 h-3" />{s.connection_type}</span>
                      </div>
                    </div>
                    <span className={`ml-2 px-2 py-0.5 rounded text-[10px] font-medium whitespace-nowrap ${st.cls}`}>{st.text}</span>
                  </div>
                  {s.invoice_number && <div className="mt-2 text-xs text-emerald-600 font-medium">Rechnung: {s.invoice_number}</div>}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Rechnungen */}
      <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
        <div className="px-4 py-3 bg-gray-50 border-b border-gray-200 flex items-center gap-2">
          <FileText className="w-4 h-4 text-emerald-600" />
          <span className="text-sm font-semibold text-gray-700">Meine Rechnungen ({myBookings.invoices.length})</span>
        </div>
        {myBookings.invoices.length === 0 ? (
          <div className="p-6 text-center text-sm text-gray-400">Noch keine Rechnungen vorhanden</div>
        ) : (
          <div className="divide-y divide-gray-100">
            {myBookings.invoices.map(inv => {
              const ist = STATUS_LABELS[inv.status] || { text: inv.status, cls: "bg-gray-100 text-gray-600" };
              return (
                <div key={inv.id} className="px-4 py-3 flex items-center justify-between" data-testid={`invoice-${inv.id}`}>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-semibold text-gray-900 font-mono">{inv.invoice_number}</span>
                      <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${ist.cls}`}>{ist.text}</span>
                    </div>
                    <p className="text-xs text-gray-500 mt-0.5">{inv.event_name} · {inv.invoice_date}</p>
                  </div>
                  <div className="flex items-center gap-3 ml-2">
                    <span className="text-sm font-bold text-gray-900">{inv.brutto?.toFixed(2)} EUR</span>
                    <button onClick={() => onDownloadInvoice(inv.id)} className="p-1.5 text-emerald-500 hover:text-emerald-700 transition-colors" title="PDF herunterladen" data-testid={`dl-inv-${inv.id}`}>
                      <Download className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Lastdiagramme */}
      <div className="bg-white border border-gray-200 rounded-xl overflow-hidden mt-4" data-testid="lastdiagramm-section">
        <div className="px-4 py-3 bg-gray-50 border-b border-gray-200 flex items-center gap-2">
          <Zap className="w-4 h-4 text-amber-500" />
          <span className="text-sm font-semibold text-gray-700">Lastdiagramme ({lastdiagramme.available.length + lastdiagramme.purchased.length})</span>
        </div>
        {(lastdiagramme.available.length > 0 || lastdiagramme.purchased.length > 0) ? (
          <div className="divide-y divide-gray-100">
            {lastdiagramme.purchased.map(item => (
              <div key={item.signup_id} className="px-4 py-3" data-testid={`ld-purchased-${item.signup_id}`}>
                <div className="flex items-start justify-between">
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-semibold text-gray-900">{item.event_name}</p>
                    <div className="flex flex-wrap gap-x-3 gap-y-1 mt-1 text-xs text-gray-500">
                      {item.event_start && <span className="flex items-center gap-1"><CalendarDays className="w-3 h-3" />{new Date(item.event_start).toLocaleDateString("de-DE")} – {new Date(item.event_end).toLocaleDateString("de-DE")}</span>}
                      <span className="flex items-center gap-1"><Zap className="w-3 h-3" />{item.connection_type}</span>
                      <span>Platz: <strong>{item.platznummer}</strong></span>
                    </div>
                    <div className="mt-1.5 flex items-center gap-2">
                      <span className="text-[10px] bg-emerald-100 text-emerald-700 px-1.5 py-0.5 rounded font-medium">Gekauft</span>
                      <span className="text-xs text-gray-400 font-mono">{item.invoice_number}</span>
                    </div>
                  </div>
                  <button onClick={() => onDownloadLastdiagramm(item.order_id)} disabled={ldDownloading === item.order_id}
                    className="ml-2 flex items-center gap-1.5 px-3 py-1.5 bg-fuchsia-600 hover:bg-fuchsia-700 text-white text-xs rounded-lg transition-colors disabled:opacity-50" data-testid={`ld-download-${item.signup_id}`}>
                    <Download className="w-3.5 h-3.5" />{ldDownloading === item.order_id ? "Laden..." : "PDF"}
                  </button>
                </div>
              </div>
            ))}
            {lastdiagramme.available.map(item => (
              <div key={item.signup_id} className="px-4 py-3" data-testid={`ld-available-${item.signup_id}`}>
                <div className="flex items-start justify-between">
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-semibold text-gray-900">{item.event_name}</p>
                    <div className="flex flex-wrap gap-x-3 gap-y-1 mt-1 text-xs text-gray-500">
                      {item.event_start && <span className="flex items-center gap-1"><CalendarDays className="w-3 h-3" />{new Date(item.event_start).toLocaleDateString("de-DE")} – {new Date(item.event_end).toLocaleDateString("de-DE")}</span>}
                      <span className="flex items-center gap-1"><Zap className="w-3 h-3" />{item.connection_type}</span>
                      <span>Platz: <strong>{item.platznummer}</strong></span>
                      {item.kwh_used != null && <span>Verbrauch: <strong>{item.kwh_used.toFixed(2)} kWh</strong></span>}
                    </div>
                  </div>
                  <button onClick={() => onPurchaseLastdiagramm(item.signup_id, item.event_name, schausteller?.kauf_auf_rechnung)}
                    disabled={ldPurchasing === item.signup_id}
                    className="ml-2 flex items-center gap-1.5 px-3 py-1.5 bg-amber-500 hover:bg-amber-600 text-white text-xs rounded-lg transition-colors disabled:opacity-50 whitespace-nowrap" data-testid={`ld-buy-${item.signup_id}`}>
                    {ldPurchasing === item.signup_id ? "Wird bestellt..." : "Kaufen (148,75 EUR)"}
                  </button>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="p-6 text-center text-sm text-gray-400">Noch keine Lastdiagramme vorhanden</div>
        )}
      </div>
    </div>
  );
}
