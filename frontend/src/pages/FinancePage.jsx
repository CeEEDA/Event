import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import api from "../lib/api";
import { Logo } from "../components/Logo";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import {
  ArrowLeft, Search, Download, FileText, Send, ChevronRight,
  TrendingUp, Receipt, CheckCircle, Clock, AlertTriangle,
  CircleDollarSign, Ban, ArrowUpDown, ArrowUp, ArrowDown, RefreshCw,
  CreditCard, Wallet, TrendingDown, Printer, Bell,
} from "lucide-react";
import { toast } from "sonner";

const PAYMENT_STATUS = {
  bezahlt: { label: "Bezahlt", color: "text-emerald-700", bg: "bg-emerald-50", icon: CheckCircle },
  offen: { label: "Offen", color: "text-amber-700", bg: "bg-amber-50", icon: Clock },
  faellig: { label: "Fällig", color: "text-orange-700", bg: "bg-orange-50", icon: AlertTriangle },
  ueberfaellig: { label: "Mahnung", color: "text-red-700", bg: "bg-red-50", icon: Ban },
  erstellt: { label: "Erstellt", color: "text-gray-500", bg: "bg-gray-50", icon: FileText },
};

export default function FinancePage() {
  const { user, isAdmin } = useAuth();
  const navigate = useNavigate();
  const [invoices, setInvoices] = useState([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(null);
  const [filter, setFilter] = useState("alle");
  const [sortKey, setSortKey] = useState("invoice_date");
  const [sortDir, setSortDir] = useState("desc"); // newest first by default
  const [repairing, setRepairing] = useState(false);

  const canAccess = isAdmin || user?.permissions?.can_billing;

  const [finance, setFinance] = useState(null);
  const loadFinance = useCallback(async () => {
    try {
      const r = await api.get("/payments/finance-summary");
      setFinance(r.data);
    } catch { /* silent */ }
  }, []);

  useEffect(() => {
    if (!canAccess) return;
    loadFinance();
  }, [canAccess, loadFinance]);

  const repairStripePaid = async () => {
    if (!window.confirm("Stripe-Zahlungen mit der Rechnungsliste abgleichen?\nFindet Rechnungen, die bei Stripe bezahlt wurden, hier aber noch als 'Fällig' stehen.")) return;
    setRepairing(true);
    try {
      const { data } = await api.post("/payments/repair-stripe-paid-invoices");
      const total = data.repaired_count || 0;
      if (total === 0) {
        toast.info("Alle Stripe-Zahlungen sind bereits korrekt zugeordnet.");
      } else {
        const all = [...(data.repaired || []), ...(data.pulled_from_stripe || [])];
        const numbers = all.map(r => r.invoice_number).filter(Boolean).join(", ");
        toast.success(`${total} Rechnung(en) als bezahlt markiert: ${numbers}`);
        loadInvoices();
        loadFinance();
      }
      if ((data.skipped || []).length > 0) {
        console.warn("[Stripe-Repair] Skipped:", data.skipped);
      }
    } catch (e) {
      toast.error(e.response?.data?.detail || "Fehler beim Stripe-Abgleich");
    } finally {
      setRepairing(false);
    }
  };

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

  const sendReminder = async (inv) => {
    if (inv.reminder2_sent_at) {
      toast.info("2. Mahnung wurde bereits versendet - hoehere Stufen bitte manuell / anwaltlich.");
      return;
    }
    const stufe = inv.reminder_sent_at ? "2. Mahnung" : "1. Mahnung";
    if (!window.confirm(`${stufe} fuer Rechnung ${inv.invoice_number} an ${inv.schausteller_email || "Kunde"} senden?`)) return;
    try {
      setSending(inv.id);
      const res = await api.post(`/kirmes/invoices/${inv.id}/send-reminder`);
      const msg = res?.data?.message || `${stufe} versendet`;
      if (res?.data?.email_sent === false) {
        toast.warning(msg);
      } else {
        toast.success(`${stufe} versendet`);
      }
      loadInvoices();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Fehler beim Versenden der Mahnung");
    } finally {
      setSending(null);
    }
  };

  const togglePayment = async (inv) => {
    const newStatus = inv.payment_status === "bezahlt" ? "offen" : "bezahlt";
    const label = newStatus === "bezahlt" ? "als bezahlt markieren" : "auf offen setzen";
    if (!window.confirm(`${inv.invoice_number} ${label}?`)) return;
    try {
      await api.put(`/kirmes/invoices/${inv.id}/payment-status`, { payment_status: newStatus });
      toast.success(`${inv.invoice_number}: ${newStatus === "bezahlt" ? "Bezahlt" : "Offen"}`);
      loadInvoices();
    } catch {
      toast.error("Fehler beim Aktualisieren");
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
  const paidCount = invoices.filter(i => i.payment_status === "bezahlt").length;
  const paidAmount = invoices.filter(i => i.payment_status === "bezahlt").reduce((s, i) => s + (i.brutto || 0), 0);
  const openCount = invoices.filter(i => ["offen", "faellig", "ueberfaellig"].includes(i.payment_status)).length;
  const openAmount = invoices.filter(i => ["offen", "faellig", "ueberfaellig"].includes(i.payment_status)).reduce((s, i) => s + (i.brutto || 0), 0);
  const overdueCount = invoices.filter(i => i.payment_status === "ueberfaellig").length;

  const filtered = filter === "alle" ? invoices
    : filter === "bezahlt" ? invoices.filter(i => i.payment_status === "bezahlt")
    : filter === "offen" ? invoices.filter(i => ["offen", "faellig", "ueberfaellig"].includes(i.payment_status))
    : filter === "ueberfaellig" ? invoices.filter(i => i.payment_status === "ueberfaellig")
    : invoices;

  // Sorting
  const PAYMENT_STATUS_ORDER = { ueberfaellig: 0, faellig: 1, offen: 2, erstellt: 3, bezahlt: 4 };
  const parseGermanDate = (d) => {
    if (!d) return 0;
    // "DD.MM.YYYY" -> timestamp; fallback: Date.parse
    const m = String(d).match(/^(\d{2})\.(\d{2})\.(\d{4})/);
    if (m) return new Date(`${m[3]}-${m[2]}-${m[1]}`).getTime();
    const t = Date.parse(d);
    return Number.isFinite(t) ? t : 0;
  };
  const getSortValue = (inv, key) => {
    switch (key) {
      case "invoice_number": return (inv.invoice_number || "").toString();
      case "schausteller_kundennummer": return (inv.schausteller_kundennummer || "").toString();
      case "schausteller_firma": return (inv.schausteller_firma || inv.schausteller_name || "").toLowerCase();
      case "event_name": return (inv.event_name || "").toLowerCase();
      case "invoice_date": return parseGermanDate(inv.invoice_date);
      case "netto": return Number(inv.netto) || 0;
      case "brutto": return Number(inv.brutto) || 0;
      case "payment_status": return PAYMENT_STATUS_ORDER[inv.payment_status] ?? 99;
      default: return 0;
    }
  };
  const sorted = [...filtered].sort((a, b) => {
    const va = getSortValue(a, sortKey);
    const vb = getSortValue(b, sortKey);
    let cmp;
    if (typeof va === "number" && typeof vb === "number") cmp = va - vb;
    else cmp = String(va).localeCompare(String(vb), "de", { numeric: true });
    return sortDir === "asc" ? cmp : -cmp;
  });

  const toggleSort = (key) => {
    if (sortKey === key) setSortDir(d => d === "asc" ? "desc" : "asc");
    else { setSortKey(key); setSortDir(key === "invoice_date" || key === "netto" || key === "brutto" ? "desc" : "asc"); }
  };

  const SortIcon = ({ col }) => {
    if (sortKey !== col) return <ArrowUpDown className="w-3 h-3 inline-block ml-1 opacity-40" />;
    return sortDir === "asc"
      ? <ArrowUp className="w-3 h-3 inline-block ml-1 text-fuchsia-600" />
      : <ArrowDown className="w-3 h-3 inline-block ml-1 text-fuchsia-600" />;
  };

  // ─── Drucken ────────────────────────────────────────────────────
  const filterLabelMap = {
    alle: "Alle Rechnungen",
    bezahlt: "Bezahlt",
    offen: "Offene Posten",
    ueberfaellig: "Mahnungen (ueberfaellig)",
  };
  const handlePrint = () => {
    if (!sorted.length) {
      toast.info("Keine Rechnungen zum Drucken.");
      return;
    }
    const escapeHtml = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    }[c]));
    const fmtEur = (n) => (Number(n) || 0).toLocaleString("de-DE", { minimumFractionDigits: 2 });
    const nowStr = new Date().toLocaleString("de-DE", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" });
    const filterLabel = filterLabelMap[filter] || "Alle Rechnungen";
    const sumNetto = sorted.reduce((s, i) => s + (Number(i.netto) || 0), 0);
    const sumBrutto = sorted.reduce((s, i) => s + (Number(i.brutto) || 0), 0);

    const rowsHtml = sorted.map((inv) => {
      const status = PAYMENT_STATUS[inv.payment_status]?.label || "-";
      const mahn = [
        inv.reminder_sent_at ? `1. Mahn. ${new Date(inv.reminder_sent_at).toLocaleDateString("de-DE")}` : "",
        inv.reminder2_sent_at ? `2. Mahn. ${new Date(inv.reminder2_sent_at).toLocaleDateString("de-DE")}` : "",
      ].filter(Boolean).join(" · ");
      return `
        <tr>
          <td class="mono">${escapeHtml(inv.invoice_number || "-")}</td>
          <td class="mono">${escapeHtml(inv.schausteller_kundennummer || "-")}</td>
          <td>${escapeHtml(inv.schausteller_firma || inv.schausteller_name || "-")}
            ${inv.schausteller_firma && inv.schausteller_name ? `<div class="sub">${escapeHtml(inv.schausteller_name)}</div>` : ""}
          </td>
          <td>${escapeHtml(inv.event_name || "-")}</td>
          <td>${escapeHtml(inv.invoice_date || "-")}${inv.days_since_invoice > 14 && inv.payment_status !== "bezahlt" ? `<div class="sub red">${inv.days_since_invoice} Tage</div>` : ""}</td>
          <td class="num">${fmtEur(inv.netto)}&nbsp;&euro;</td>
          <td class="num">${fmtEur(inv.brutto)}&nbsp;&euro;</td>
          <td>${escapeHtml(status)}${mahn ? `<div class="sub red">${escapeHtml(mahn)}</div>` : ""}</td>
        </tr>`;
    }).join("");

    const html = `<!doctype html>
<html lang="de"><head>
<meta charset="utf-8">
<title>Ausgangsrechnungen · ${escapeHtml(filterLabel)} · ${escapeHtml(nowStr)}</title>
<style>
  @page { size: A4 landscape; margin: 12mm; }
  * { box-sizing: border-box; }
  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif; color: #111; font-size: 10pt; margin: 0; padding: 0; }
  header { display: flex; justify-content: space-between; align-items: flex-end; margin-bottom: 10px; border-bottom: 2px solid #111; padding-bottom: 6px; }
  header h1 { font-size: 16pt; margin: 0 0 2px 0; }
  header .meta { font-size: 9pt; color: #555; text-align: right; }
  .summary { display: flex; gap: 20px; margin: 8px 0 12px 0; font-size: 10pt; }
  .summary .item { border: 1px solid #ddd; padding: 4px 10px; border-radius: 4px; }
  .summary .item b { display: block; font-size: 12pt; color: #111; }
  table { width: 100%; border-collapse: collapse; font-size: 9pt; }
  thead { background: #f3f3f3; }
  th, td { border-bottom: 1px solid #ddd; padding: 4px 6px; text-align: left; vertical-align: top; }
  th { font-weight: 600; text-transform: uppercase; font-size: 8pt; color: #555; }
  td.mono { font-family: "Courier New", monospace; }
  td.num, th.num { text-align: right; font-family: "Courier New", monospace; white-space: nowrap; }
  .sub { font-size: 8pt; color: #888; }
  .sub.red { color: #b00; }
  tfoot td { font-weight: 700; border-top: 2px solid #111; background: #f9f9f9; }
  footer { margin-top: 12px; font-size: 8pt; color: #888; text-align: center; }
  @media print { .no-print { display: none; } }
</style>
</head><body>
  <header>
    <div>
      <h1>Ausgangsrechnungen &ndash; ${escapeHtml(filterLabel)}</h1>
      <div class="meta">Eventenergie Deutschland GmbH &amp; Co. KG</div>
    </div>
    <div class="meta">
      Druckdatum: ${escapeHtml(nowStr)}<br>
      ${search ? `Suche: &bdquo;${escapeHtml(search)}&ldquo;<br>` : ""}
      ${sorted.length} Eintr&auml;ge
    </div>
  </header>
  <div class="summary">
    <div class="item"><span>Anzahl</span><b>${sorted.length}</b></div>
    <div class="item"><span>Summe Netto</span><b>${fmtEur(sumNetto)}&nbsp;&euro;</b></div>
    <div class="item"><span>Summe Brutto</span><b>${fmtEur(sumBrutto)}&nbsp;&euro;</b></div>
  </div>
  <table>
    <thead><tr>
      <th>Re.-Nr.</th><th>Kd.-Nr.</th><th>Kunde</th><th>Event</th>
      <th>Datum</th><th class="num">Netto</th><th class="num">Brutto</th><th>Zahlung</th>
    </tr></thead>
    <tbody>${rowsHtml}</tbody>
    <tfoot><tr>
      <td colspan="5">Gesamt (${sorted.length} Eintr&auml;ge)</td>
      <td class="num">${fmtEur(sumNetto)}&nbsp;&euro;</td>
      <td class="num">${fmtEur(sumBrutto)}&nbsp;&euro;</td>
      <td></td>
    </tr></tfoot>
  </table>
  <footer>Erstellt am ${escapeHtml(nowStr)} &middot; Eventenergie Deutschland</footer>
  <script>window.addEventListener("load", function () { setTimeout(function () { window.focus(); window.print(); }, 250); });</script>
</body></html>`;

    const win = window.open("", "_blank", "width=1100,height=800");
    if (!win) {
      toast.error("Popup wurde blockiert. Bitte Popups fuer diese Seite erlauben.");
      return;
    }
    win.document.open();
    win.document.write(html);
    win.document.close();
  };

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col" data-testid="finance-page">
      <header className="bg-white border-b border-gray-200 px-4 py-3 sticky top-0 z-20">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Button variant="ghost" size="icon" onClick={() => navigate("/verwaltung")} className="h-8 w-8" data-testid="back-btn">
              <ArrowLeft className="w-4 h-4" />
            </Button>
            <div className="h-5 w-px bg-gray-200" />
            <Receipt className="w-5 h-5 text-emerald-600" />
            <h1 className="text-base font-semibold text-gray-900">Ausgangsrechnungen</h1>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={handlePrint}
              disabled={loading || sorted.length === 0}
              className="text-xs h-8"
              data-testid="print-invoices-btn"
              title="Aktuelle Liste drucken"
            >
              <Printer className="w-3.5 h-3.5 mr-1.5" />
              Drucken
            </Button>
            {isAdmin && (
              <Button
                variant="outline"
                size="sm"
                onClick={repairStripePaid}
                disabled={repairing}
                className="text-xs h-8"
                data-testid="repair-stripe-btn"
              >
                <RefreshCw className={`w-3.5 h-3.5 mr-1.5 ${repairing ? "animate-spin" : ""}`} />
                Stripe abgleichen
              </Button>
            )}
            <Logo size="small" />
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 py-6 w-full space-y-6">
        {/* Stripe-Finanzuebersicht */}
        {finance && (
          <div className="bg-gradient-to-br from-fuchsia-50 via-white to-emerald-50 border border-fuchsia-100 rounded-xl p-5" data-testid="stripe-finance-panel">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <CreditCard className="w-5 h-5 text-fuchsia-600" />
                <h2 className="text-sm font-semibold text-gray-900">Stripe & Offene Posten</h2>
              </div>
              <button
                onClick={loadFinance}
                className="text-[11px] text-gray-500 hover:text-fuchsia-600 flex items-center gap-1"
                title="Aktualisieren"
                data-testid="finance-refresh-btn"
              >
                <RefreshCw className="w-3 h-3" /> Aktualisieren
              </button>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <div className="bg-white/70 backdrop-blur-sm border border-emerald-100 rounded-lg p-3" data-testid="stripe-income-card">
                <div className="flex items-center gap-1.5 mb-1">
                  <Wallet className="w-3.5 h-3.5 text-emerald-600" />
                  <span className="text-[11px] text-gray-500 uppercase tracking-wide">Stripe-Eingang</span>
                </div>
                <p className="text-xl font-bold text-emerald-700 font-mono">
                  {finance.stripe_income_net.toLocaleString("de-DE", { minimumFractionDigits: 2 })} &euro;
                </p>
                {finance.stripe_refunds_total > 0 && (
                  <p className="text-[10px] text-gray-500 mt-0.5">
                    Brutto {finance.stripe_income_gross.toLocaleString("de-DE", { minimumFractionDigits: 2 })} &euro; · <span className="text-rose-600">-{finance.stripe_refunds_total.toLocaleString("de-DE", { minimumFractionDigits: 2 })} &euro; Refunds</span>
                  </p>
                )}
                <div className="flex gap-2 mt-1.5 text-[10px] text-gray-500 flex-wrap">
                  {finance.by_type?.deposit && (
                    <span title="Kautionen"><b>{finance.by_type.deposit.count}</b> Kaut. {finance.by_type.deposit.amount.toLocaleString("de-DE", { minimumFractionDigits: 2 })}&euro;</span>
                  )}
                  {finance.by_type?.invoice && (
                    <span title="Rechnungen"><b>{finance.by_type.invoice.count}</b> Rechn. {finance.by_type.invoice.amount.toLocaleString("de-DE", { minimumFractionDigits: 2 })}&euro;</span>
                  )}
                </div>
              </div>

              <div className="bg-white/70 backdrop-blur-sm border border-amber-100 rounded-lg p-3" data-testid="open-invoices-card">
                <div className="flex items-center gap-1.5 mb-1">
                  <Clock className="w-3.5 h-3.5 text-amber-600" />
                  <span className="text-[11px] text-gray-500 uppercase tracking-wide">Offen (Rechnungen)</span>
                </div>
                <p className="text-xl font-bold text-amber-700 font-mono">
                  {finance.open_invoices_amount.toLocaleString("de-DE", { minimumFractionDigits: 2 })} &euro;
                </p>
                <p className="text-[10px] text-gray-500 mt-0.5">
                  {finance.open_invoices_count} Rechnung(en)
                </p>
                {finance.open_after_deposit !== finance.open_invoices_amount && (
                  <p className="text-[10px] text-amber-600 mt-1" title="Rechnungsbetrag abzueglich bereits gezahlter Kautionen">
                    nach Kaution: <b>{finance.open_after_deposit.toLocaleString("de-DE", { minimumFractionDigits: 2 })} &euro;</b>
                  </p>
                )}
              </div>

              <div className="bg-white/70 backdrop-blur-sm border border-red-100 rounded-lg p-3" data-testid="overdue-card">
                <div className="flex items-center gap-1.5 mb-1">
                  <AlertTriangle className="w-3.5 h-3.5 text-red-600" />
                  <span className="text-[11px] text-gray-500 uppercase tracking-wide">Überfällig</span>
                </div>
                <p className="text-xl font-bold text-red-700 font-mono">
                  {finance.overdue_amount.toLocaleString("de-DE", { minimumFractionDigits: 2 })} &euro;
                </p>
                <p className="text-[10px] text-gray-500 mt-0.5">
                  {finance.overdue_count} Mahnung(en)
                </p>
              </div>

              <div className={`bg-white/70 backdrop-blur-sm border rounded-lg p-3 ${finance.failed_refunds_count > 0 ? "border-rose-200" : "border-gray-200"}`} data-testid="failed-refunds-card">
                <div className="flex items-center gap-1.5 mb-1">
                  <TrendingDown className={`w-3.5 h-3.5 ${finance.failed_refunds_count > 0 ? "text-rose-600" : "text-gray-400"}`} />
                  <span className="text-[11px] text-gray-500 uppercase tracking-wide">Refund-Fehler</span>
                </div>
                <p className={`text-xl font-bold font-mono ${finance.failed_refunds_count > 0 ? "text-rose-700" : "text-gray-400"}`}>
                  {finance.failed_refunds_amount.toLocaleString("de-DE", { minimumFractionDigits: 2 })} &euro;
                </p>
                <p className="text-[10px] text-gray-500 mt-0.5">
                  {finance.failed_refunds_count} hängend
                </p>
              </div>
            </div>

            {finance.by_month && finance.by_month.length > 1 && (
              <details className="mt-4 group">
                <summary className="text-[11px] text-gray-500 cursor-pointer hover:text-fuchsia-600 select-none">
                  Verlauf (letzte {finance.by_month.length} Monate) ▾
                </summary>
                <div className="mt-2 overflow-x-auto">
                  <table className="w-full text-[11px]">
                    <thead className="text-gray-500 uppercase">
                      <tr>
                        <th className="text-left py-1 pr-3">Monat</th>
                        <th className="text-right py-1 pr-3">Eingang</th>
                        <th className="text-right py-1 pr-3">Refunds</th>
                        <th className="text-right py-1 pr-3">Netto</th>
                        <th className="text-right py-1"># TX</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                      {finance.by_month.map(m => (
                        <tr key={m.month}>
                          <td className="py-1 pr-3 font-mono text-gray-700">{m.month}</td>
                          <td className="py-1 pr-3 text-right font-mono text-emerald-700">{m.income.toLocaleString("de-DE", { minimumFractionDigits: 2 })}</td>
                          <td className="py-1 pr-3 text-right font-mono text-rose-600">{m.refunds > 0 ? `-${m.refunds.toLocaleString("de-DE", { minimumFractionDigits: 2 })}` : "-"}</td>
                          <td className="py-1 pr-3 text-right font-mono font-semibold text-gray-900">{m.net.toLocaleString("de-DE", { minimumFractionDigits: 2 })}</td>
                          <td className="py-1 text-right text-gray-500">{m.count}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </details>
            )}
          </div>
        )}

        {/* Summary Cards */}
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          <button onClick={() => setFilter("alle")} className={`bg-white border rounded-lg p-4 text-left transition ${filter === "alle" ? "border-fuchsia-400 ring-1 ring-fuchsia-200" : "border-gray-200 hover:border-gray-300"}`} data-testid="stat-total">
            <div className="flex items-center gap-2 mb-1">
              <FileText className="w-4 h-4 text-gray-400" />
              <span className="text-xs text-gray-500">Rechnungen</span>
            </div>
            <p className="text-2xl font-bold text-gray-900">{invoices.length}</p>
          </button>
          <button onClick={() => setFilter("alle")} className={`bg-white border rounded-lg p-4 text-left transition ${filter === "alle" ? "border-fuchsia-400 ring-1 ring-fuchsia-200" : "border-gray-200 hover:border-gray-300"}`} data-testid="stat-brutto">
            <div className="flex items-center gap-2 mb-1">
              <TrendingUp className="w-4 h-4 text-emerald-500" />
              <span className="text-xs text-gray-500">Brutto gesamt</span>
            </div>
            <p className="text-2xl font-bold text-emerald-600">{totalBrutto.toLocaleString("de-DE", { minimumFractionDigits: 2 })} &euro;</p>
          </button>
          <button onClick={() => setFilter("bezahlt")} className={`bg-white border rounded-lg p-4 text-left transition ${filter === "bezahlt" ? "border-emerald-400 ring-1 ring-emerald-200" : "border-gray-200 hover:border-gray-300"}`} data-testid="stat-paid">
            <div className="flex items-center gap-2 mb-1">
              <CheckCircle className="w-4 h-4 text-emerald-500" />
              <span className="text-xs text-gray-500">Bezahlt</span>
            </div>
            <p className="text-2xl font-bold text-emerald-600">{paidCount}</p>
            <p className="text-xs text-emerald-500 mt-0.5">{paidAmount.toLocaleString("de-DE", { minimumFractionDigits: 2 })} &euro;</p>
          </button>
          <button onClick={() => setFilter("offen")} className={`bg-white border rounded-lg p-4 text-left transition ${filter === "offen" ? "border-amber-400 ring-1 ring-amber-200" : "border-gray-200 hover:border-gray-300"}`} data-testid="stat-open">
            <div className="flex items-center gap-2 mb-1">
              <Clock className="w-4 h-4 text-amber-500" />
              <span className="text-xs text-gray-500">Offen</span>
            </div>
            <p className="text-2xl font-bold text-amber-600">{openCount}</p>
            <p className="text-xs text-amber-500 mt-0.5">{openAmount.toLocaleString("de-DE", { minimumFractionDigits: 2 })} &euro;</p>
          </button>
          <button onClick={() => setFilter("ueberfaellig")} className={`bg-white border rounded-lg p-4 text-left transition ${filter === "ueberfaellig" ? "border-red-400 ring-1 ring-red-200" : "border-gray-200 hover:border-gray-300"}`} data-testid="stat-overdue">
            <div className="flex items-center gap-2 mb-1">
              <AlertTriangle className="w-4 h-4 text-red-500" />
              <span className="text-xs text-gray-500">Mahnung</span>
            </div>
            <p className="text-2xl font-bold text-red-600">{overdueCount}</p>
          </button>
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
                  <th className="px-4 py-3 text-left cursor-pointer select-none hover:text-fuchsia-700 transition-colors" onClick={() => toggleSort("invoice_number")} data-testid="sort-invoice-number">Re.-Nr.<SortIcon col="invoice_number" /></th>
                  <th className="px-4 py-3 text-left cursor-pointer select-none hover:text-fuchsia-700 transition-colors" onClick={() => toggleSort("schausteller_kundennummer")} data-testid="sort-customer-number">Kd.-Nr.<SortIcon col="schausteller_kundennummer" /></th>
                  <th className="px-4 py-3 text-left cursor-pointer select-none hover:text-fuchsia-700 transition-colors" onClick={() => toggleSort("schausteller_firma")} data-testid="sort-customer">Kunde<SortIcon col="schausteller_firma" /></th>
                  <th className="px-4 py-3 text-left hidden md:table-cell cursor-pointer select-none hover:text-fuchsia-700 transition-colors" onClick={() => toggleSort("event_name")} data-testid="sort-event">Event<SortIcon col="event_name" /></th>
                  <th className="px-4 py-3 text-left hidden sm:table-cell cursor-pointer select-none hover:text-fuchsia-700 transition-colors" onClick={() => toggleSort("invoice_date")} data-testid="sort-date">Datum<SortIcon col="invoice_date" /></th>
                  <th className="px-4 py-3 text-right hidden sm:table-cell cursor-pointer select-none hover:text-fuchsia-700 transition-colors" onClick={() => toggleSort("netto")} data-testid="sort-netto">Netto<SortIcon col="netto" /></th>
                  <th className="px-4 py-3 text-right cursor-pointer select-none hover:text-fuchsia-700 transition-colors" onClick={() => toggleSort("brutto")} data-testid="sort-brutto">Brutto<SortIcon col="brutto" /></th>
                  <th className="px-4 py-3 text-center cursor-pointer select-none hover:text-fuchsia-700 transition-colors" onClick={() => toggleSort("payment_status")} data-testid="sort-payment">Zahlung<SortIcon col="payment_status" /></th>
                  <th className="px-4 py-3 text-right">Aktionen</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {loading ? (
                  <tr><td colSpan={9} className="px-4 py-8 text-center text-gray-500">Laden...</td></tr>
                ) : sorted.length === 0 ? (
                  <tr><td colSpan={9} className="px-4 py-8 text-center text-gray-500">{search ? "Keine Rechnungen gefunden" : "Noch keine Rechnungen vorhanden"}</td></tr>
                ) : sorted.map(inv => {
                  const ps = PAYMENT_STATUS[inv.payment_status] || PAYMENT_STATUS.erstellt;
                  const Icon = ps.icon;
                  return (
                    <tr key={inv.id} className="hover:bg-gray-50" data-testid={`inv-row-${inv.id}`}>
                      <td className="px-4 py-3">
                        <span className="font-mono text-sm font-semibold text-gray-900" data-testid={`inv-nr-${inv.id}`}>{inv.invoice_number}</span>
                      </td>
                      <td className="px-4 py-3">
                        <span className="font-mono text-xs text-fuchsia-600 bg-fuchsia-50 px-1.5 py-0.5 rounded">{inv.schausteller_kundennummer || "\u2013"}</span>
                      </td>
                      <td className="px-4 py-3">
                        <div>
                          <p className="text-sm font-medium text-gray-900">{inv.schausteller_firma}</p>
                          <p className="text-xs text-gray-500">{inv.schausteller_name}</p>
                        </div>
                      </td>
                      <td className="px-4 py-3 hidden md:table-cell text-sm text-gray-600">{inv.event_name}</td>
                      <td className="px-4 py-3 hidden sm:table-cell">
                        <span className="text-sm text-gray-500">{inv.invoice_date}</span>
                        {inv.days_since_invoice > 14 && inv.payment_status !== "bezahlt" && (
                          <span className="block text-[10px] text-red-500">{inv.days_since_invoice} Tage</span>
                        )}
                      </td>
                      <td className="px-4 py-3 hidden sm:table-cell text-sm text-right font-mono text-gray-600">{inv.netto?.toLocaleString("de-DE", { minimumFractionDigits: 2 })} &euro;</td>
                      <td className="px-4 py-3 text-sm text-right font-mono font-semibold text-gray-900">{inv.brutto?.toLocaleString("de-DE", { minimumFractionDigits: 2 })} &euro;</td>
                      <td className="px-4 py-3 text-center">
                        <button
                          onClick={() => togglePayment(inv)}
                          className={`inline-flex items-center gap-1 text-xs ${ps.color} ${ps.bg} px-2 py-1 rounded-full cursor-pointer hover:opacity-80 transition`}
                          title={inv.payment_status === "bezahlt" ? "Auf offen setzen" : "Als bezahlt markieren"}
                          data-testid={`payment-toggle-${inv.id}`}
                        >
                          <Icon className="w-3 h-3" /> {ps.label}
                        </button>
                        {inv.reminder_sent_at && (
                          <p className="text-[10px] text-red-500 mt-0.5">
                            1. Mahnung {new Date(inv.reminder_sent_at).toLocaleDateString("de-DE")}
                          </p>
                        )}
                        {inv.reminder2_sent_at && (
                          <p className="text-[10px] text-red-700 mt-0.5 font-semibold">
                            2. Mahnung {new Date(inv.reminder2_sent_at).toLocaleDateString("de-DE")}
                          </p>
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
                          {inv.payment_status !== "bezahlt" && (
                            <Button
                              variant="ghost"
                              size="icon"
                              className={`h-8 w-8 ${inv.reminder2_sent_at ? "text-gray-300" : inv.reminder_sent_at ? "text-red-600 hover:text-red-700" : "text-amber-600 hover:text-amber-700"}`}
                              onClick={() => sendReminder(inv)}
                              disabled={sending === inv.id || !!inv.reminder2_sent_at}
                              title={inv.reminder2_sent_at ? "2. Mahnung bereits versendet" : inv.reminder_sent_at ? "2. Mahnung senden" : "1. Mahnung senden"}
                              data-testid={`send-reminder-${inv.id}`}
                            >
                              <Bell className="w-4 h-4" />
                            </Button>
                          )}
                          <Button variant="ghost" size="icon" className="h-8 w-8 text-gray-500 hover:text-fuchsia-600" onClick={() => navigate(`/admin/schausteller/${inv.schausteller_id || ""}`)} title="Kunde anzeigen" data-testid={`view-sch-${inv.id}`}>
                            <ChevronRight className="w-4 h-4" />
                          </Button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
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
