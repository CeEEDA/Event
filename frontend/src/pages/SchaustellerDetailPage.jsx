import { useState, useEffect, useCallback } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Logo } from "../components/Logo";
import api, { getErrorMsg } from "../lib/api";
import { toast } from "sonner";
import { Button } from "../components/ui/button";
import {
  ArrowLeft, Tent, MapPin, CalendarDays, Zap, Mail, Phone, Building2,
  FileText, Receipt, ChevronRight, Download, Send,
} from "lucide-react";

const PAYMENT_LABELS = {
  ausstehend: "Ausstehend", reserviert: "Reserviert", bezahlt: "Bezahlt", erstattet: "Erstattet",
};
const PAYMENT_COLORS = {
  ausstehend: "text-amber-600 bg-amber-50", reserviert: "text-blue-600 bg-blue-50",
  bezahlt: "text-emerald-600 bg-emerald-50", erstattet: "text-gray-500 bg-gray-100",
};

export default function SchaustellerDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [sch, setSch] = useState(null);
  const [loading, setLoading] = useState(true);
  const [sendingInvoice, setSendingInvoice] = useState(null);

  const load = useCallback(async () => {
    try {
      const r = await api.get(`/kirmes/schausteller/${id}`);
      setSch(r.data);
    } catch {
      toast.error("Schausteller nicht gefunden");
      navigate("/admin");
    } finally { setLoading(false); }
  }, [id, navigate]);

  useEffect(() => { load(); }, [load]);

  const handleDownloadInvoice = async (invoiceId, invoiceNumber) => {
    try {
      const response = await fetch(`${process.env.REACT_APP_BACKEND_URL}/api/kirmes/invoices/${invoiceId}/pdf`, {
        headers: { Authorization: `Bearer ${localStorage.getItem("token")}` },
      });
      if (!response.ok) throw new Error("Fehler");
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${invoiceNumber}.pdf`;
      a.click();
      window.URL.revokeObjectURL(url);
    } catch { toast.error("PDF konnte nicht heruntergeladen werden"); }
  };

  const handleSendInvoice = async (invoiceId) => {
    setSendingInvoice(invoiceId);
    try {
      const r = await api.post(`/kirmes/invoices/${invoiceId}/send`);
      toast.success(r.data.message);
      load();
    } catch (err) {
      toast.error(getErrorMsg(err, "Fehler beim Versenden"));
    } finally { setSendingInvoice(null); }
  };

  useEffect(() => { load(); }, [load]);

  if (loading) return <div className="min-h-screen bg-gray-50 flex items-center justify-center text-gray-400">Laden...</div>;
  if (!sch) return null;

  const signups = sch.signups || [];

  return (
    <div className="min-h-screen bg-gray-50" data-testid="schausteller-detail-page">
      <header className="sticky top-0 z-10 bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Button variant="ghost" size="sm" onClick={() => navigate("/admin")} className="text-gray-600 hover:text-fuchsia-600" data-testid="back-btn">
              <ArrowLeft className="w-4 h-4 mr-1" /> Zurück
            </Button>
            <div className="h-5 w-px bg-gray-200" />
            <Tent className="w-5 h-5 text-amber-600" />
            <h1 className="text-base font-semibold text-gray-900">{sch.firma}</h1>
            {sch.kauf_auf_rechnung && <span className="text-[10px] bg-amber-100 text-amber-700 px-2 py-0.5 rounded-full font-medium">Kauf auf Rechnung</span>}
          </div>
          <Logo size="small" />
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 py-6 space-y-6">
        {/* Contact Info Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="bg-white border border-gray-200 rounded-xl p-5">
            <h2 className="text-sm font-semibold text-gray-900 mb-4 flex items-center gap-2">
              <Building2 className="w-4 h-4 text-fuchsia-500" /> Kontaktdaten
            </h2>
            <div className="grid grid-cols-2 gap-x-8 gap-y-3 text-sm">
              <div>
                <p className="text-[10px] text-gray-400 uppercase tracking-wider mb-0.5">Firma</p>
                <p className="font-medium text-gray-900">{sch.firma}</p>
              </div>
              <div>
                <p className="text-[10px] text-gray-400 uppercase tracking-wider mb-0.5">Name</p>
                <p className="text-gray-700">{sch.name}</p>
              </div>
              <div className="col-span-2">
                <p className="text-[10px] text-gray-400 uppercase tracking-wider mb-0.5">Anschrift</p>
                <p className="text-gray-700">{sch.strasse || "–"}, {sch.plz || ""} {sch.ort || ""}</p>
              </div>
              <div>
                <p className="text-[10px] text-gray-400 uppercase tracking-wider mb-0.5">Steuernummer</p>
                <p className="font-mono text-gray-700">{sch.steuernummer || "–"}</p>
              </div>
            </div>
          </div>

          <div className="bg-white border border-gray-200 rounded-xl p-5">
            <h2 className="text-sm font-semibold text-gray-900 mb-4 flex items-center gap-2">
              <Mail className="w-4 h-4 text-fuchsia-500" /> Kommunikation
            </h2>
            <div className="space-y-3 text-sm">
              <div className="flex items-center gap-3">
                <Mail className="w-4 h-4 text-gray-400 flex-shrink-0" />
                <div>
                  <p className="text-[10px] text-gray-400">E-Mail</p>
                  <p className="text-gray-700">{sch.email}</p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <Receipt className="w-4 h-4 text-gray-400 flex-shrink-0" />
                <div>
                  <p className="text-[10px] text-gray-400">Rechnungs-E-Mail</p>
                  <p className="text-gray-700">{sch.rechnungs_email || sch.email}</p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <Phone className="w-4 h-4 text-gray-400 flex-shrink-0" />
                <div>
                  <p className="text-[10px] text-gray-400">Telefon</p>
                  <p className="text-gray-700">{sch.telefon || "–"}</p>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Veranstaltungs-Historie */}
        <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
          <div className="px-5 py-4 border-b border-gray-100">
            <h2 className="text-sm font-semibold text-gray-900 flex items-center gap-2">
              <CalendarDays className="w-4 h-4 text-fuchsia-500" /> Veranstaltungs-Historie ({signups.length})
            </h2>
          </div>
          {signups.length === 0 ? (
            <div className="px-5 py-12 text-center text-gray-400 text-sm">Noch keine Veranstaltungen besucht</div>
          ) : (
            <div className="divide-y divide-gray-100">
              {signups.map(s => (
                <div
                  key={s.id}
                  className="px-5 py-4 flex items-center gap-4 hover:bg-gray-50 cursor-pointer transition-colors"
                  onClick={() => navigate(`/kirmes/${s.event_id}`)}
                  data-testid={`history-${s.id}`}
                >
                  <div className="w-10 h-10 rounded-lg bg-fuchsia-50 flex items-center justify-center flex-shrink-0">
                    <Tent className="w-5 h-5 text-fuchsia-600" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-gray-900">{s.event_name || "Veranstaltung"}</p>
                    <div className="flex flex-wrap gap-3 mt-1 text-xs text-gray-500">
                      <span className="flex items-center gap-1"><Tent className="w-3 h-3" /> {s.fahrgeschaeft || "–"}</span>
                      <span className="flex items-center gap-1"><MapPin className="w-3 h-3" /> Platz {s.platznummer}</span>
                      <span className="inline-flex items-center gap-1 bg-fuchsia-50 text-fuchsia-700 px-1.5 py-0.5 rounded"><Zap className="w-3 h-3" /> {s.connection_type}</span>
                      {s.kwh_used != null && <span className="font-mono">{s.kwh_used.toFixed(2)} kWh</span>}
                    </div>
                  </div>
                  <div className="text-right flex-shrink-0">
                    <p className="text-sm font-mono font-medium text-gray-900">{(s.price || 0).toFixed(2)} EUR</p>
                    <span className={`inline-block mt-1 text-[10px] font-medium px-2 py-0.5 rounded-full ${PAYMENT_COLORS[s.payment_status] || "text-gray-500 bg-gray-100"}`}>
                      {PAYMENT_LABELS[s.payment_status] || s.payment_status}
                    </span>
                  </div>
                  <ChevronRight className="w-4 h-4 text-gray-300 flex-shrink-0" />
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Rechnungen */}
        <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
          <div className="px-5 py-4 border-b border-gray-100">
            <h2 className="text-sm font-semibold text-gray-900 flex items-center gap-2">
              <FileText className="w-4 h-4 text-fuchsia-500" /> Rechnungen ({(sch.invoices || []).length})
            </h2>
          </div>
          {(sch.invoices || []).length === 0 ? (
            <div className="px-5 py-12 text-center">
              <FileText className="w-10 h-10 text-gray-200 mx-auto mb-3" />
              <p className="text-sm text-gray-400">Noch keine Rechnungen vorhanden</p>
            </div>
          ) : (
            <div className="divide-y divide-gray-100">
              {(sch.invoices || []).map(inv => (
                <div key={inv.id} className="px-5 py-4 flex items-center gap-4" data-testid={`invoice-${inv.id}`}>
                  <div className="w-10 h-10 rounded-lg bg-emerald-50 flex items-center justify-center flex-shrink-0">
                    <Receipt className="w-5 h-5 text-emerald-600" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-semibold text-gray-900">{inv.invoice_number}</p>
                    <div className="flex flex-wrap gap-3 mt-1 text-xs text-gray-500">
                      <span>{inv.event_name}</span>
                      <span>{inv.invoice_date}</span>
                      {inv.sent_to && <span className="text-emerald-600">Gesendet an {inv.sent_to}</span>}
                    </div>
                  </div>
                  <div className="text-right flex-shrink-0 mr-2">
                    <p className="text-sm font-mono font-semibold text-gray-900">{(inv.brutto || 0).toFixed(2)} EUR</p>
                    <span className={`inline-block mt-1 text-[10px] font-medium px-2 py-0.5 rounded-full ${
                      inv.status === "versendet" ? "text-emerald-600 bg-emerald-50" : "text-gray-500 bg-gray-100"
                    }`}>{inv.status}</span>
                  </div>
                  <div className="flex items-center gap-1 flex-shrink-0">
                    <button
                      onClick={() => handleDownloadInvoice(inv.id, inv.invoice_number)}
                      className="p-2 text-gray-400 hover:text-emerald-600 transition-colors"
                      title="PDF herunterladen"
                      data-testid={`download-inv-${inv.id}`}
                    >
                      <Download className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() => handleSendInvoice(inv.id)}
                      disabled={sendingInvoice === inv.id}
                      className="p-2 text-gray-400 hover:text-blue-600 transition-colors disabled:opacity-50"
                      title="Rechnung per E-Mail senden"
                      data-testid={`send-inv-${inv.id}`}
                    >
                      <Send className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
