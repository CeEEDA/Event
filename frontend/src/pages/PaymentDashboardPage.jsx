import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import api, { getErrorMsg } from "../lib/api";
import { toast } from "sonner";
import { Button } from "../components/ui/button";
import {
  ArrowLeft, CreditCard, Banknote, Clock, CheckCircle2,
  AlertCircle, TrendingUp, Send, Filter, ChevronDown,
} from "lucide-react";

const STATUS_BADGE = {
  paid: { cls: "bg-emerald-100 text-emerald-700", label: "Bezahlt" },
  pending: { cls: "bg-amber-100 text-amber-700", label: "Offen" },
  expired: { cls: "bg-gray-100 text-gray-500", label: "Abgelaufen" },
};

function KpiCard({ icon: Icon, label, value, sub, color }) {
  return (
    <div className="bg-white border border-gray-200 rounded-xl p-4">
      <div className="flex items-center gap-2 mb-2">
        <div className={`w-8 h-8 rounded-lg ${color} flex items-center justify-center`}>
          <Icon className="w-4 h-4 text-white" />
        </div>
        <span className="text-xs text-gray-500">{label}</span>
      </div>
      <p className="text-xl font-bold text-gray-900 font-mono">{value}</p>
      {sub && <p className="text-[10px] text-gray-400 mt-1">{sub}</p>}
    </div>
  );
}

export default function PaymentDashboardPage() {
  const navigate = useNavigate();
  const [dashboard, setDashboard] = useState(null);
  const [events, setEvents] = useState([]);
  const [selectedEvent, setSelectedEvent] = useState("");
  const [loading, setLoading] = useState(true);
  const [sendingLink, setSendingLink] = useState(null);

  const loadDashboard = useCallback(async () => {
    try {
      const params = selectedEvent ? `?event_id=${selectedEvent}` : "";
      const [dashRes, eventsRes] = await Promise.all([
        api.get(`/payments/dashboard${params}`),
        api.get("/payments/dashboard/events"),
      ]);
      setDashboard(dashRes.data);
      setEvents(eventsRes.data);
    } catch {
      toast.error("Fehler beim Laden");
    } finally {
      setLoading(false);
    }
  }, [selectedEvent]);

  useEffect(() => { loadDashboard(); }, [loadDashboard]);

  const handleSendLink = async (tx) => {
    setSendingLink(tx.id);
    try {
      const body = { origin_url: window.location.origin };
      if (tx.type === "deposit") body.signup_id = tx.signup_id;
      else body.invoice_id = tx.invoice_id;
      const r = await api.post("/payments/send-payment-link", body);
      toast.success(`Zahlungslink an ${r.data.email} gesendet`);
    } catch (err) {
      toast.error(getErrorMsg(err, "Fehler beim Senden"));
    } finally {
      setSendingLink(null);
    }
  };

  const fmt = (n) => (n || 0).toFixed(2).replace(".", ",") + " €";

  if (loading) return <div className="min-h-screen bg-gray-50 flex items-center justify-center text-gray-400">Laden...</div>;

  const d = dashboard?.deposits || {};
  const inv = dashboard?.invoices || {};
  const txs = dashboard?.recent_transactions || [];

  return (
    <div className="min-h-screen bg-gray-50" data-testid="payment-dashboard">
      <header className="sticky top-0 z-10 bg-white border-b border-gray-200">
        <div className="max-w-6xl mx-auto px-4 py-3 flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="sm" onClick={() => navigate("/kirmes")} className="text-gray-600 hover:text-fuchsia-600" data-testid="back-btn">
              <ArrowLeft className="w-4 h-4 sm:mr-1" /> <span className="hidden sm:inline">Zurück</span>
            </Button>
            <div className="h-5 w-px bg-gray-200 hidden sm:block" />
            <h1 className="text-sm sm:text-base font-semibold text-gray-900">Zahlungsübersicht</h1>
          </div>
          <div className="flex items-center gap-2">
            <select value={selectedEvent} onChange={e => setSelectedEvent(e.target.value)}
              className="text-xs border border-gray-200 rounded-lg px-2 py-1.5 focus:outline-none focus:border-fuchsia-500 max-w-[200px]"
              data-testid="event-filter">
              <option value="">Alle Veranstaltungen</option>
              {events.map(e => (
                <option key={e.id} value={e.id}>{e.name}</option>
              ))}
            </select>
          </div>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-4 py-6 space-y-6">
        {/* KPI Cards */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3" data-testid="kpi-cards">
          <KpiCard icon={Banknote} label="Kautionen bezahlt" value={fmt(d.paid_amount)} sub={`${d.paid || 0} von ${d.total || 0}`} color="bg-emerald-500" />
          <KpiCard icon={AlertCircle} label="Kautionen offen" value={fmt(d.pending_amount)} sub={`${d.pending || 0} ausstehend`} color="bg-amber-500" />
          <KpiCard icon={CheckCircle2} label="Rechnungen bezahlt" value={fmt(inv.paid_amount)} sub={`${inv.paid || 0} von ${inv.total || 0}`} color="bg-blue-500" />
          <KpiCard icon={Clock} label="Rechnungen offen" value={fmt(inv.pending_amount)} sub={`${inv.pending || 0} ausstehend`} color="bg-red-500" />
        </div>

        {/* Total Revenue */}
        <div className="bg-white border border-gray-200 rounded-xl p-5">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-fuchsia-50 rounded-lg flex items-center justify-center">
                <TrendingUp className="w-5 h-5 text-fuchsia-600" />
              </div>
              <div>
                <p className="text-xs text-gray-500">Gesamteinnahmen</p>
                <p className="text-2xl font-bold text-gray-900 font-mono">{fmt((d.paid_amount || 0) + (inv.paid_amount || 0))}</p>
              </div>
            </div>
            <div className="text-right text-xs text-gray-400">
              <p>Kautionen: {fmt(d.paid_amount)}</p>
              <p>Rechnungen: {fmt(inv.paid_amount)}</p>
            </div>
          </div>
        </div>

        {/* Events Summary */}
        {!selectedEvent && events.length > 0 && (
          <div className="bg-white border border-gray-200 rounded-xl p-5" data-testid="events-summary">
            <h2 className="text-sm font-semibold text-gray-900 mb-3 flex items-center gap-2">
              <Filter className="w-4 h-4 text-fuchsia-500" /> Veranstaltungen
            </h2>
            <div className="space-y-2">
              {events.map(e => (
                <div key={e.id} className="flex items-center justify-between p-3 rounded-lg border border-gray-100 hover:bg-gray-50 cursor-pointer transition-colors"
                  onClick={() => setSelectedEvent(e.id)} data-testid={`event-row-${e.id}`}>
                  <div>
                    <p className="text-sm font-medium text-gray-900">{e.name}</p>
                    <p className="text-[10px] text-gray-400">{e.start_date || ""}</p>
                  </div>
                  <div className="flex items-center gap-4 text-[10px]">
                    <span className="text-emerald-600">{e.deposits_paid || 0} Kaut. bezahlt</span>
                    <span className="text-amber-600">{e.deposits_pending || 0} offen</span>
                    <span className="font-semibold text-gray-700">{fmt(e.total_received)}</span>
                    <ChevronDown className="w-3 h-3 text-gray-400 -rotate-90" />
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Transaction List */}
        <div className="bg-white border border-gray-200 rounded-xl p-5" data-testid="transactions-list">
          <h2 className="text-sm font-semibold text-gray-900 mb-3 flex items-center gap-2">
            <CreditCard className="w-4 h-4 text-fuchsia-500" /> Transaktionen ({txs.length})
          </h2>
          {txs.length === 0 ? (
            <p className="text-center text-gray-400 text-sm py-8">Keine Transaktionen vorhanden</p>
          ) : (
            <div className="overflow-x-auto -mx-5 px-5">
              <table className="w-full text-xs min-w-[700px]">
                <thead>
                  <tr className="border-b border-gray-100 text-gray-400 uppercase text-[10px]">
                    <th className="text-left py-2 font-medium">Datum</th>
                    <th className="text-left py-2 font-medium">Typ</th>
                    <th className="text-left py-2 font-medium">Schausteller</th>
                    <th className="text-left py-2 font-medium">Details</th>
                    <th className="text-right py-2 font-medium">Betrag</th>
                    <th className="text-center py-2 font-medium">Status</th>
                    <th className="text-right py-2 font-medium">Aktion</th>
                  </tr>
                </thead>
                <tbody>
                  {txs.map(tx => {
                    const badge = STATUS_BADGE[tx.payment_status] || STATUS_BADGE.pending;
                    return (
                      <tr key={tx.id} className="border-b border-gray-50 hover:bg-gray-50" data-testid={`tx-${tx.id}`}>
                        <td className="py-2.5 text-gray-600">{tx.created_at ? new Date(tx.created_at).toLocaleDateString("de-DE") : "–"}</td>
                        <td className="py-2.5">
                          <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${tx.type === "deposit" ? "bg-purple-100 text-purple-700" : "bg-blue-100 text-blue-700"}`}>
                            {tx.type === "deposit" ? "Kaution" : "Rechnung"}
                          </span>
                        </td>
                        <td className="py-2.5 text-gray-900 font-medium">{tx.schausteller_name || "–"}</td>
                        <td className="py-2.5 text-gray-500">
                          {tx.type === "deposit" ? `${tx.connection_type || ""} · ${tx.event_name || ""}` : tx.invoice_number || "–"}
                        </td>
                        <td className="py-2.5 text-right font-mono font-semibold text-gray-900">{fmt(tx.amount)}</td>
                        <td className="py-2.5 text-center">
                          <span className={`px-2 py-0.5 rounded-full text-[10px] font-medium ${badge.cls}`}>{badge.label}</span>
                        </td>
                        <td className="py-2.5 text-right">
                          {tx.payment_status === "pending" && (
                            <Button size="sm" variant="ghost" onClick={() => handleSendLink(tx)}
                              disabled={sendingLink === tx.id} className="text-fuchsia-600 text-[10px] h-6 px-2"
                              data-testid={`send-link-${tx.id}`}>
                              <Send className="w-3 h-3 mr-1" /> {sendingLink === tx.id ? "..." : "Link senden"}
                            </Button>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
