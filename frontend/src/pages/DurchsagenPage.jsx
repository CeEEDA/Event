import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowLeft, Volume2, MapPin, Lightbulb, CalendarClock } from "lucide-react";
import api from "../lib/api";
import { Button } from "../components/ui/button";
import { OrderAudioPanel } from "../components/mbox/OrderAudioPanel";
import { Logo } from "../components/Logo";

const fmt = (d) => (d && d !== "0000-00-00" ? d.slice(0, 10).split("-").reverse().join(".") : "–");

// Kundenseite (auch Handy): Durchsagen fuer aktive + kommende Auftraege (Upload, Vorhoeren, Start/Schleife/Stopp, Timer)
export default function DurchsagenPage() {
  const navigate = useNavigate();
  const [orders, setOrders] = useState(null);
  useEffect(() => {
    api.get("/mbox/my/orders").then(r => setOrders(r.data)).catch(() => setOrders([]));
  }, []);
  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200 sticky top-0 z-30">
        <div className="max-w-5xl mx-auto px-3 sm:px-4 py-2.5 sm:py-3 flex items-center gap-2 sm:gap-3">
          <Button variant="ghost" size="sm" onClick={() => navigate("/hub")} className="text-gray-600 hover:text-fuchsia-600 px-2" data-testid="durchsagen-back-btn">
            <ArrowLeft className="w-4 h-4 sm:mr-1" /><span className="hidden sm:inline">Zurück</span>
          </Button>
          <div className="min-w-0">
            <h1 className="text-base font-bold text-gray-900 flex items-center gap-2"><Volume2 className="w-5 h-5 text-fuchsia-600" /> Durchsagen</h1>
            <p className="text-xs text-gray-400 truncate">Sprachdateien für Ihre Lichtmasten – Start erfolgt zeitgleich auf den gewählten Masten</p>
          </div>
          <div className="ml-auto hidden sm:block"><Logo size="small" /></div>
        </div>
      </header>
      <main className="max-w-5xl mx-auto px-3 sm:px-4 py-4 sm:py-6 space-y-4 sm:space-y-6">
        {orders === null && <p className="text-sm text-gray-500">Lade Aufträge…</p>}
        {orders && orders.length === 0 && (
          <div className="bg-white border border-gray-200 rounded-xl p-6 text-sm text-gray-500" data-testid="durchsagen-empty">
            Aktuell ist Ihnen keine laufende oder kommende Veranstaltung mit Lichtmasten zugeordnet. Bitte wenden Sie sich an Eventenergie, damit Ihr Zugang für den Auftrag freigeschaltet wird.
          </div>
        )}
        {orders?.map(o => (
          <section key={o.order_pk} className="bg-white border border-gray-200 rounded-xl shadow-sm p-3 sm:p-5" data-testid={`durchsagen-order-${o.order_pk}`}>
            <div className="flex items-start justify-between gap-3 flex-wrap mb-4">
              <div className="min-w-0">
                <h2 className="text-sm font-bold text-gray-900 flex items-center gap-2 flex-wrap">
                  <Lightbulb className="w-4 h-4 text-amber-500 shrink-0" /> {o.event || `Auftrag ${o.order_pk}`}
                  {o.active ? (
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-700 font-medium" data-testid={`durchsagen-active-${o.order_pk}`}>läuft</span>
                  ) : (
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-100 text-amber-700 font-medium flex items-center gap-1" data-testid={`durchsagen-upcoming-${o.order_pk}`}><CalendarClock className="w-3 h-3" /> ab {fmt(o.dispo_start)} bedienbar</span>
                  )}
                </h2>
                <p className="text-xs text-gray-400 flex items-center gap-1 mt-0.5"><MapPin className="w-3 h-3 shrink-0" /> <span className="truncate">{o.address || "–"}</span></p>
                <p className="text-xs text-gray-400 flex items-center gap-1 mt-0.5"><CalendarClock className="w-3 h-3 shrink-0" /> {fmt(o.dispo_start)} – {fmt(o.dispo_end)}</p>
              </div>
              {o.active && <Button size="sm" variant="outline" onClick={() => navigate("/generators")} data-testid={`durchsagen-masten-${o.order_pk}`}>Masten ansehen</Button>}
            </div>
            <OrderAudioPanel orderPk={o.order_pk} />
          </section>
        ))}
      </main>
    </div>
  );
}
