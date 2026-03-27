import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import api from "../lib/api";
import { Logo } from "../components/Logo";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import {
  ArrowLeft, Search, Download, FileText, Send, ChevronRight,
  TrendingUp, Receipt, CheckCircle, Clock,
} from "lucide-react";

export default function FinancePage() {
  const { user, isAdmin } = useAuth();
  const navigate = useNavigate();
  const [invoices, setInvoices] = useState([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(null);

  const canAccess = isAdmin || user?.permissions?.can_billing;

  const loadInvoices = useCallback(async () => {
    try {
      setLoading(true);
      const res = await api.get("/kirmes/invoices", { params: search ? { search } : {} });
      setInvoices(res.data);
    } catch {
      /* handled by interceptor */
    } finally {
      setLoading(false);
    }
  }, [search]);

  useEffect(() => {
    if (!canAccess) return;
    const t = setTimeout(loadInvoices, 300);
    return () => clearTimeout(t);
  }, [canAccess, loadInvoices]);

  const downloadPdf = async (inv) => {
    try {
      const res = await api.get(`/kirmes/invoices/${inv.id}/pdf`, { responseType: "blob" });
      const url = URL.createObjectURL(new Blob([res.data], { type: "application/pdf" }));
      const a = document.createElement("a");
      a.href = url;
      a.download = `${inv.invoice_number}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch { /* */ }
  };

  const sendInvoice = async (inv) => {
    if (!window.confirm(`Rechnung ${inv.invoice_number} an ${inv.schausteller_email} senden?`)) return;
    try {
      setSending(inv.id);
      await api.post(`/kirmes/invoices/${inv.id}/send`);
      loadInvoices();
    } catch { /* */ } finally {
      setSending(null);
    }
  };

  if (!canAccess) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <p className="text-gray-500">Keine Berechtigung</p>
      </div>
    );
  }

  const totalNetto = invoices.reduce((s, i) => s + (i.netto || 0), 0);
  const totalBrutto = invoices.reduce((s, i) => s + (i.brutto || 0), 0);
  const sentCount = invoices.filter(i => i.sent_at).length;

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col" data-testid="finance-page">
      <header className="bg-white border-b border-gray-200 px-4 py-3 sticky top-0 z-20">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Button variant="ghost" size="icon" onClick={() => navigate("/")} className="h-8 w-8" data-testid="back-btn">
              <ArrowLeft className="w-4 h-4" />
            </Button>
            <div className="h-5 w-px bg-gray-200" />
            <Receipt className="w-5 h-5 text-emerald-600" />
            <h1 className="text-base font-semibold text-gray-900">Rechnungsverwaltung</h1>
          </div>
          <Logo size="small" />
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 py-6 w-full space-y-6">
        {/* Summary Cards */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <div className="bg-white border border-gray-200 rounded-lg p-4" data-testid="stat-total">
            <div className="flex items-center gap-2 mb-1">
              <FileText className="w-4 h-4 text-gray-400" />
              <span className="text-xs text-gray-500">Rechnungen</span>
            </div>
            <p className="text-2xl font-bold text-gray-900">{invoices.length}</p>
          </div>
          <div className="bg-white border border-gray-200 rounded-lg p-4" data-testid="stat-netto">
            <div className="flex items-center gap-2 mb-1">
              <TrendingUp className="w-4 h-4 text-gray-400" />
              <span className="text-xs text-gray-500">Netto gesamt</span>
            </div>
            <p className="text-2xl font-bold text-gray-900">{totalNetto.toLocaleString("de-DE", { minimumFractionDigits: 2 })} &euro;</p>
          </div>
          <div className="bg-white border border-gray-200 rounded-lg p-4" data-testid="stat-brutto">
            <div className="flex items-center gap-2 mb-1">
              <TrendingUp className="w-4 h-4 text-emerald-500" />
              <span className="text-xs text-gray-500">Brutto gesamt</span>
            </div>
            <p className="text-2xl font-bold text-emerald-600">{totalBrutto.toLocaleString("de-DE", { minimumFractionDigits: 2 })} &euro;</p>
          </div>
          <div className="bg-white border border-gray-200 rounded-lg p-4" data-testid="stat-sent">
            <div className="flex items-center gap-2 mb-1">
              <Send className="w-4 h-4 text-gray-400" />
              <span className="text-xs text-gray-500">Versendet</span>
            </div>
            <p className="text-2xl font-bold text-gray-900">{sentCount} / {invoices.length}</p>
          </div>
        </div>

        {/* Search */}
        <div className="relative max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <Input
            placeholder="Suche nach Rechnungsnr., Kunde, Kundennr., Event..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="pl-10 border-gray-300"
            data-testid="finance-search"
          />
        </div>

        {/* Invoice Table */}
        <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full" data-testid="invoice-table">
              <thead className="bg-gray-50 text-xs text-gray-500 uppercase">
                <tr>
                  <th className="px-4 py-3 text-left">Re.-Nr.</th>
                  <th className="px-4 py-3 text-left">Kd.-Nr.</th>
                  <th className="px-4 py-3 text-left">Kunde</th>
                  <th className="px-4 py-3 text-left hidden md:table-cell">Event</th>
                  <th className="px-4 py-3 text-left hidden sm:table-cell">Datum</th>
                  <th className="px-4 py-3 text-right hidden sm:table-cell">Netto</th>
                  <th className="px-4 py-3 text-right">Brutto</th>
                  <th className="px-4 py-3 text-center hidden md:table-cell">Status</th>
                  <th className="px-4 py-3 text-right">Aktionen</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {loading ? (
                  <tr><td colSpan={9} className="px-4 py-8 text-center text-gray-500">Laden...</td></tr>
                ) : invoices.length === 0 ? (
                  <tr><td colSpan={9} className="px-4 py-8 text-center text-gray-500">{search ? "Keine Rechnungen gefunden" : "Noch keine Rechnungen vorhanden"}</td></tr>
                ) : invoices.map(inv => (
                  <tr key={inv.id} className="hover:bg-gray-50" data-testid={`inv-row-${inv.id}`}>
                    <td className="px-4 py-3">
                      <span className="font-mono text-sm font-semibold text-gray-900" data-testid={`inv-nr-${inv.id}`}>{inv.invoice_number}</span>
                    </td>
                    <td className="px-4 py-3">
                      <span className="font-mono text-xs text-fuchsia-600 bg-fuchsia-50 px-1.5 py-0.5 rounded">{inv.schausteller_kundennummer || "–"}</span>
                    </td>
                    <td className="px-4 py-3">
                      <div>
                        <p className="text-sm font-medium text-gray-900">{inv.schausteller_firma}</p>
                        <p className="text-xs text-gray-500">{inv.schausteller_name}</p>
                      </div>
                    </td>
                    <td className="px-4 py-3 hidden md:table-cell text-sm text-gray-600">{inv.event_name}</td>
                    <td className="px-4 py-3 hidden sm:table-cell text-sm text-gray-500">{inv.invoice_date}</td>
                    <td className="px-4 py-3 hidden sm:table-cell text-sm text-right font-mono text-gray-600">{inv.netto?.toLocaleString("de-DE", { minimumFractionDigits: 2 })} &euro;</td>
                    <td className="px-4 py-3 text-sm text-right font-mono font-semibold text-gray-900">{inv.brutto?.toLocaleString("de-DE", { minimumFractionDigits: 2 })} &euro;</td>
                    <td className="px-4 py-3 hidden md:table-cell text-center">
                      {inv.sent_at ? (
                        <span className="inline-flex items-center gap-1 text-xs text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-full">
                          <CheckCircle className="w-3 h-3" /> Versendet
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 text-xs text-amber-700 bg-amber-50 px-2 py-0.5 rounded-full">
                          <Clock className="w-3 h-3" /> Erstellt
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <div className="flex items-center justify-end gap-1">
                        <Button variant="ghost" size="icon" className="h-8 w-8 text-gray-500 hover:text-fuchsia-600" onClick={() => downloadPdf(inv)} title="PDF herunterladen" data-testid={`dl-pdf-${inv.id}`}>
                          <Download className="w-4 h-4" />
                        </Button>
                        <Button variant="ghost" size="icon" className="h-8 w-8 text-gray-500 hover:text-emerald-600" onClick={() => sendInvoice(inv)} disabled={sending === inv.id} title="Per E-Mail senden" data-testid={`send-inv-${inv.id}`}>
                          <Send className="w-4 h-4" />
                        </Button>
                        <Button variant="ghost" size="icon" className="h-8 w-8 text-gray-500 hover:text-fuchsia-600" onClick={() => navigate(`/admin/schausteller/${inv.schausteller_id || ""}`)} title="Kunde anzeigen" data-testid={`view-sch-${inv.id}`}>
                          <ChevronRight className="w-4 h-4" />
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </main>

      <footer className="bg-white border-t border-gray-200 p-4 text-center text-sm text-gray-500">
        &copy; {new Date().getFullYear()} Eventenergie Deutschland GmbH & Co. KG
      </footer>
    </div>
  );
}
