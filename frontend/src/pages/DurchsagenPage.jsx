import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowLeft, Volume2, MapPin, Lightbulb } from "lucide-react";
import api from "../lib/api";
import { Button } from "../components/ui/button";
import { OrderAudioPanel } from "../components/mbox/OrderAudioPanel";

// Kundenseite: Durchsagen fuer alle heute aktiven Auftraege (Upload, Vorschau, zeitgleicher Start auf allen Masten)
export default function DurchsagenPage() {
  const navigate = useNavigate();
  const [orders, setOrders] = useState(null);
  useEffect(() => {
    api.get("/mbox/my/orders").then(r => setOrders(r.data)).catch(() => setOrders([]));
  }, []);
  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200 sticky top-0 z-30">
        <div className="max-w-5xl mx-auto px-4 py-3 flex items-center gap-3">
          <Button variant="ghost" size="sm" onClick={() => navigate("/hub")} className="text-gray-600 hover:text-fuchsia-600" data-testid="durchsagen-back-btn">
            <ArrowLeft className="w-4 h-4 mr-1" /> Zurück
          </Button>
          <div className="min-w-0">
            <h1 className="text-base font-bold text-gray-900 flex items-center gap-2"><Volume2 className="w-5 h-5 text-fuchsia-600" /> Durchsagen</h1>
            <p className="text-xs text-gray-400">Sprachdateien für Ihre Lichtmasten – Start erfolgt zeitgleich auf allen Masten vor Ort</p>
          </div>
          <img src="/logo.png" alt="Eventenergie" className="h-7 ml-auto hidden sm:block" onError={e => { e.currentTarget.style.display = "none"; }} />
        </div>
      </header>
      <main className="max-w-5xl mx-auto px-4 py-6 space-y-6">
        {orders === null && <p className="text-sm text-gray-500">Lade Aufträge…</p>}
        {orders && orders.length === 0 && (
          <div className="bg-white border border-gray-200 rounded-xl p-6 text-sm text-gray-500" data-testid="durchsagen-empty">
            Aktuell ist Ihnen keine laufende Veranstaltung mit Lichtmasten zugeordnet. Die Zuordnung gilt von Lieferung bis Abholung.
          </div>
        )}
        {orders?.map(o => (
          <section key={o.order_pk} className="bg-white border border-gray-200 rounded-xl shadow-sm p-5" data-testid={`durchsagen-order-${o.order_pk}`}>
            <div className="flex items-start justify-between gap-3 flex-wrap mb-4">
              <div>
                <h2 className="text-sm font-bold text-gray-900 flex items-center gap-2"><Lightbulb className="w-4 h-4 text-amber-500" /> {o.event || `Auftrag ${o.order_pk}`}</h2>
                <p className="text-xs text-gray-400 flex items-center gap-1 mt-0.5"><MapPin className="w-3 h-3" /> {o.address || "–"} · {o.dispo_start} bis {o.dispo_end}</p>
              </div>
              <Button size="sm" variant="outline" onClick={() => navigate("/generators")} data-testid={`durchsagen-masten-${o.order_pk}`}>Masten ansehen</Button>
            </div>
            <OrderAudioPanel orderPk={o.order_pk} />
          </section>
        ))}
      </main>
    </div>
  );
}
