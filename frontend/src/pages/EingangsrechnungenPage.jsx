import { useState, useEffect, useCallback, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import api from "../lib/api";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import {
  ArrowLeft, Search, FileText, CheckCircle, AlertTriangle, Clock,
  Receipt, X, Save, Euro, Landmark, Ban, CreditCard, Repeat,
  Wifi, WifiOff, ShieldAlert,
} from "lucide-react";
import { toast } from "sonner";

const STATUS_META = {
  overdue:    { label: "Überfällig",       cls: "bg-red-50 text-red-700 border-red-200",         icon: AlertTriangle, row: "border-l-4 border-l-red-500" },
  open:       { label: "Offen",            cls: "bg-amber-50 text-amber-700 border-amber-200",   icon: Clock,         row: "border-l-4 border-l-amber-400" },
  paid:       { label: "Bezahlt",          cls: "bg-emerald-50 text-emerald-700 border-emerald-200", icon: CheckCircle, row: "border-l-4 border-l-emerald-500" },
  creditcard: { label: "Kreditkarte",      cls: "bg-indigo-50 text-indigo-700 border-indigo-200", icon: CreditCard,    row: "border-l-4 border-l-indigo-400" },
  sepa:       { label: "SEPA-Lastschrift", cls: "bg-sky-50 text-sky-700 border-sky-200",         icon: Repeat,        row: "border-l-4 border-l-sky-400" },
};

const fmtEUR = (n) => new Intl.NumberFormat("de-DE", { style: "currency", currency: "EUR" }).format(Number(n || 0));
const fmtDate = (s) => {
  if (!s) return "—";
  try { return new Date(s).toLocaleDateString("de-DE"); } catch { return s; }
};

export default function EingangsrechnungenPage() {
  const navigate = useNavigate();
  const { user, isAdmin } = useAuth();
  const canAccess = isAdmin || user?.permissions?.can_billing;

  const [rows, setRows] = useState([]);
  const [summary, setSummary] = useState(null);
  const [bankStatus, setBankStatus] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("aktiv");
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState(null);
  const [previewBlobUrl, setPreviewBlobUrl] = useState(null);
  const [editDue, setEditDue] = useState("");
  const [editNotes, setEditNotes] = useState("");
  const [saving, setSaving] = useState(false);
  const [marking, setMarking] = useState(false);
  const [matching, setMatching] = useState(false);
  const [reanalyzing, setReanalyzing] = useState(false);
  const [checkedIds, setCheckedIds] = useState(new Set());
  const [bulking, setBulking] = useState(false);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      const token = localStorage.getItem("token");
      const [{ data }, statusRes] = await Promise.all([
        api.get("/incoming-invoices", { params: { token } }),
        api.get("/incoming-invoices/bank-status", { params: { token } }).catch(() => ({ data: { banks: [] } })),
      ]);
      setRows(data.invoices || []);
      setSummary(data.summary || null);
      setBankStatus(statusRes.data?.banks || []);
      setCheckedIds(new Set());
    } catch (e) {
      toast.error(e.response?.data?.detail || "Fehler beim Laden");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { if (canAccess) load(); }, [canAccess, load]);

  // PDF/Image preview blob laden
  useEffect(() => {
    if (!selected?.id) { setPreviewBlobUrl(null); return; }
    const ct = selected.content_type || "";
    if (ct !== "application/pdf" && !ct.startsWith("image/")) { setPreviewBlobUrl(null); return; }
    let objectUrl = null;
    let cancelled = false;
    api.get(`/documents/${selected.id}/file`, { responseType: "blob" })
      .then(resp => {
        if (cancelled) return;
        objectUrl = URL.createObjectURL(resp.data);
        setPreviewBlobUrl(objectUrl);
      })
      .catch(() => { if (!cancelled) setPreviewBlobUrl(null); });
    return () => { cancelled = true; if (objectUrl) URL.revokeObjectURL(objectUrl); };
  }, [selected?.id, selected?.content_type]);

  useEffect(() => {
    setEditDue(selected?.due_date || "");
    setEditNotes(selected?.notes || "");
  }, [selected?.id]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    // Für "Aktiv": frisch bezahlt (letzte 2 Tage) bleibt sichtbar, danach ab ins Archiv
    const now = Date.now();
    const twoDaysMs = 2 * 24 * 60 * 60 * 1000;
    const recentlyPaid = (r) => {
      if (r.status !== "paid" || !r.paid_at) return false;
      const t = new Date(r.paid_at).getTime();
      return isFinite(t) && (now - t) < twoDaysMs;
    };
    return rows.filter(r => {
      // "aktiv" = overdue + open + (paid < 2 Tage; keine CC/SEPA)
      // "archiv" = ALLE bezahlten Rechnungen
      // "creditcard" = Kreditkarten-Zahlungen
      // "sepa" = SEPA-Lastschriften
      if (filter === "aktiv") {
        if (r.status === "creditcard" || r.status === "sepa") return false;
        if (r.status === "paid" && !recentlyPaid(r)) return false;
      } else if (filter === "archiv") {
        if (r.status !== "paid") return false;
      } else if (filter === "creditcard") {
        if (r.status !== "creditcard") return false;
      } else if (filter === "sepa") {
        if (r.status !== "sepa") return false;
      } else if (["overdue", "open", "paid"].includes(filter) && r.status !== filter) {
        return false;
      }
      if (!q) return true;
      return [r.sender, r.invoice_number, r.filename, r.notes].some(v => (v || "").toLowerCase().includes(q));
    });
  }, [rows, filter, search]);

  const runReanalyzeLegacy = async () => {
    const includeAlreadyAnalyzed = window.confirm(
      "Alt-Dokumente durch aktuelle OCR-Heuristik neu klassifizieren?\n\n" +
      "OK  = auch bereits gescannte Rechnungen einbeziehen (empfohlen nach Heuristik-Update).\n" +
      "Abbrechen = weiter ohne diese Frage (nur neue/nicht analysierte Docs)."
    );
    // Zweiter Dialog: Bestaetigung dass wir starten
    if (!window.confirm(
      (includeAlreadyAnalyzed
        ? "ALLE Rechnungseingaenge (auch bereits heuristisch analysierte) werden neu gescannt.\n\n"
        : "Nur Alt-Dokumente ohne aktuelle Heuristik-Analyse werden neu gescannt.\n\n") +
      "Der Scan aktualisiert Absender, Betrag und Klassifizierung.\n" +
      "Dokumente die von 'Ausgang' zu 'Eingang' wechseln (oder umgekehrt) werden in den passenden Monat-Ordner verschoben.\n\n" +
      "Zuerst wird ein DRY-RUN (Vorschau) ausgeführt, danach die Übernahme. Fortfahren?"
    )) return;
    setReanalyzing(true);
    try {
      const token = localStorage.getItem("token");
      // 1. Dry-Run
      const dry = await api.post("/incoming-invoices/reanalyze-legacy", null, {
        params: { token, dry_run: true, limit: 500, force: includeAlreadyAnalyzed }, timeout: 300000
      });
      const preview = dry.data;
      const commit = window.confirm(
        `DRY-RUN Ergebnis:\n` +
        `• ${preview.scanned} Dokumente gescannt\n` +
        `• ${preview.would_move_count} würden verschoben\n` +
        `• ${preview.errors} Fehler beim Lesen\n\n` +
        `Jetzt tatsächlich anwenden?`
      );
      if (!commit) {
        toast("Dry-Run abgeschlossen (keine Änderung)");
        return;
      }
      // 2. Übernahme
      const real = await api.post("/incoming-invoices/reanalyze-legacy", null, {
        params: { token, dry_run: false, limit: 500, force: includeAlreadyAnalyzed }, timeout: 600000
      });
      const r = real.data;
      toast.success(
        `Reanalyse fertig: ${r.metadata_updated} aktualisiert, ` +
        `${r.moved_to_eingang} → Eingang, ${r.moved_to_ausgang} → Ausgang, ${r.errors} Fehler`
      );
      await load();
    } catch (e) {
      toast.error("Fehler bei Reanalyse: " + (e.response?.data?.detail || e.message));
    } finally {
      setReanalyzing(false);
    }
  };

  const runAutoMatch = async () => {
    // Frage 1: Umfang (Zeitraum + auch bereits bezahlte einbeziehen)
    const full = window.confirm(
      "FinTS-Abgleich starten?\n\n" +
      "OK   = Voll-Rescan (365 Tage) inkl. bereits bezahlter Rechnungen ohne Buchungs-Referenz\n" +
      "Abbrechen = Standard-Rescan (60 Tage, nur offene Rechnungen)"
    );
    // Frage 2: Bestaetigung
    if (!window.confirm(
      full
        ? "VOLL-RESCAN starten? Das kann bei vielen Rechnungen ein paar Minuten dauern."
        : "Standard-Abgleich der letzten 60 Tage starten?"
    )) return;
    setMatching(true);
    try {
      const token = localStorage.getItem("token");
      const { data } = await api.post("/incoming-invoices/fints/auto-match", null, {
        params: {
          token,
          days_back: full ? 365 : 60,
          include_paid: full,
        },
        timeout: 300000,
      });
      if (data.ok === false) {
        toast.error(`FinTS-Fehler: ${data.error || "Unbekannt"}`);
        return;
      }
      const parts = [];
      parts.push(`${data.checked} Buchungen geprüft`);
      if (data.auto_marked) parts.push(`${data.auto_marked} auto-bezahlt`);
      if (data.admin_tasks) parts.push(`${data.admin_tasks} Betrag-Mismatch`);
      if (data.ambiguous) parts.push(`${data.ambiguous} mehrdeutig`);
      toast.success(parts.join(" • "));
      await load();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Fehler beim FinTS-Abgleich");
    } finally {
      setMatching(false);
    }
  };

  const markNotInvoice = async (row) => {
    if (!row) return;
    if (!window.confirm(`"${row.filename}" als KEINE Eingangsrechnung markieren?\n\nDokument wird aus der Liste entfernt. Es bleibt im Rechnungseingang-Ordner und kann im Dokumentenmanagement in den richtigen Ordner verschoben werden.`)) return;
    try {
      const token = localStorage.getItem("token");
      await api.post(`/incoming-invoices/${row.id}/not-invoice`, null, { params: { token } });
      toast.success("Als keine Rechnung markiert – aus der Liste entfernt");
      setSelected(null);
      await load();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Fehler");
    }
  };

  const markPaymentMethod = async (row, kind /* "creditcard" | "sepa" */) => {
    if (!row) return;
    const label = kind === "creditcard" ? "Kreditkarte" : "SEPA-Lastschrift";
    const sender = row.sender || "";
    const remember = sender
      ? window.confirm(`Rechnung "${row.invoice_number || row.filename}" als ${label} markieren?\n\nSoll ich mir "${sender}" merken, damit KÜNFTIGE Rechnungen desselben Absenders automatisch ebenfalls als ${label} erkannt werden?\n\nOK = merken (empfohlen)\nAbbrechen = nur diese eine Rechnung`)
      : false;
    try {
      const token = localStorage.getItem("token");
      const endpoint = kind === "creditcard" ? "mark-creditcard" : "mark-sepa";
      await api.post(`/incoming-invoices/${row.id}/${endpoint}`, null, {
        params: { token, remember_sender: remember },
      });
      toast.success(remember
        ? `Als ${label} markiert – "${sender}" wird künftig auto-erkannt`
        : `Als ${label} markiert`);
      setSelected(null);
      await load();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Fehler");
    }
  };


  const markPaid = async (row) => {
    if (!row) return;
    if (!window.confirm(`Rechnung "${row.invoice_number || row.filename}" als bezahlt markieren?\n\nHinweis: Dieser Status ist FINAL und kann nur direkt in der Datenbank geändert werden.`)) return;
    setMarking(true);
    try {
      const token = localStorage.getItem("token");
      await api.post(`/incoming-invoices/${row.id}/mark-paid`, null, { params: { token } });
      toast.success("Als bezahlt markiert");
      await load();
      setSelected(s => s?.id === row.id ? { ...s, status: "paid", paid: true } : s);
    } catch (e) {
      toast.error(e.response?.data?.detail || "Fehler");
    } finally {
      setMarking(false);
    }
  };

  const toggleCheck = (id) => {
    setCheckedIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

  const toggleCheckAllVisible = () => {
    setCheckedIds(prev => {
      // Nur unbezahlte, sichtbare Rechnungen im aktuellen Filter erfassbar
      const eligible = filtered.filter(r => r.status === "open" || r.status === "overdue").map(r => r.id);
      if (eligible.every(id => prev.has(id))) {
        return new Set();
      }
      return new Set(eligible);
    });
  };

  const bulkMarkPaid = async () => {
    const ids = Array.from(checkedIds).filter(id =>
      rows.some(r => r.id === id && (r.status === "open" || r.status === "overdue")));
    if (!ids.length) {
      toast("Keine offenen Rechnungen ausgewählt");
      return;
    }
    if (!window.confirm(`${ids.length} Rechnung(en) als bezahlt markieren?\n\nHinweis: Dieser Status ist FINAL.`)) return;
    setBulking(true);
    try {
      const token = localStorage.getItem("token");
      const { data } = await api.post("/incoming-invoices/bulk-mark-paid", { ids }, { params: { token } });
      toast.success(`${data.updated || 0} von ${data.requested || ids.length} als bezahlt markiert`);
      setCheckedIds(new Set());
      await load();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Fehler beim Bulk-Markieren");
    } finally {
      setBulking(false);
    }
  };

  const saveMeta = async () => {
    if (!selected) return;
    setSaving(true);
    try {
      const token = localStorage.getItem("token");
      await api.patch(`/incoming-invoices/${selected.id}`, null, {
        params: { token, due_date: editDue || "", notes: editNotes || "" }
      });
      toast.success("Gespeichert");
      await load();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Fehler");
    } finally {
      setSaving(false);
    }
  };

  if (!canAccess) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <Receipt className="w-12 h-12 text-gray-300 mx-auto mb-3" />
          <p className="text-gray-600">Keine Berechtigung für Rechnungswesen.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50" data-testid="eingangsrechnungen-page">
      <header className="sticky top-0 z-20 bg-white border-b border-gray-200">
        <div className="max-w-[1600px] mx-auto px-4 py-3 flex items-center gap-3">
          <Button variant="ghost" size="sm" onClick={() => navigate("/verwaltung")} className="text-gray-600 hover:text-fuchsia-600" data-testid="back-btn">
            <ArrowLeft className="w-4 h-4 mr-1" /> Zurück
          </Button>
          <div className="h-5 w-px bg-gray-200" />
          <Receipt className="w-5 h-5 text-fuchsia-600" />
          <h1 className="text-base font-semibold text-gray-900">Eingangsrechnungen</h1>
          <div className="ml-auto flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={runAutoMatch} disabled={matching} data-testid="fints-match-btn">
              <Landmark className="w-4 h-4 mr-1" /> {matching ? "Sparkasse prüft…" : "FinTS-Abgleich"}
            </Button>
            <Button variant="outline" size="sm" onClick={runReanalyzeLegacy} disabled={reanalyzing} data-testid="reanalyze-legacy-btn">
              <Repeat className="w-4 h-4 mr-1" /> {reanalyzing ? "Reanalyse läuft…" : "Alt-Docs neu klassifizieren"}
            </Button>
            <Button variant="outline" size="sm" onClick={load} disabled={loading} data-testid="reload-btn">
              {loading ? "Lädt…" : "Neu laden"}
            </Button>
          </div>
        </div>
      </header>

      {/* Bank Status Line */}
      {bankStatus.length > 0 && (
        <div className="max-w-[1600px] mx-auto px-4 pt-4">
          <div className="bg-white border border-gray-200 rounded-lg px-3 py-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs" data-testid="bank-status-bar">
            <span className="text-gray-500 font-medium uppercase tracking-wide">Banken:</span>
            {bankStatus.map(b => {
              const active = b.enabled && b.has_state && (b.sca_renewal_in_days ?? 999) > 0;
              const warn = b.enabled && b.has_state && (b.sca_renewal_in_days ?? 999) <= 7;
              return (
                <div key={b.key} className="inline-flex items-center gap-1.5" data-testid={`bank-status-${b.key}`}>
                  {!b.enabled ? (
                    <WifiOff className="w-3.5 h-3.5 text-gray-400" />
                  ) : warn ? (
                    <ShieldAlert className="w-3.5 h-3.5 text-amber-500" />
                  ) : active ? (
                    <Wifi className="w-3.5 h-3.5 text-emerald-500" />
                  ) : (
                    <WifiOff className="w-3.5 h-3.5 text-red-500" />
                  )}
                  <span className="font-medium text-gray-800">{b.name}</span>
                  {!b.enabled ? (
                    <span className="text-gray-400">deaktiviert</span>
                  ) : !b.has_state ? (
                    <span className="text-red-600">noch keine pushTAN-Anmeldung</span>
                  ) : (
                    <span className="text-gray-500">
                      Sync {b.last_check_at ? new Date(b.last_check_at).toLocaleString("de-DE", {day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit"}) : "—"}
                      {b.sca_renewal_in_days !== null && b.sca_renewal_in_days !== undefined && (
                        <span className={warn ? "text-amber-600 ml-1" : "ml-1"}>
                          • SCA erneuert in {b.sca_renewal_in_days} Tg.
                        </span>
                      )}
                    </span>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Summary Cards */}
      {summary && (
        <div className="max-w-[1600px] mx-auto px-4 pt-4">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <SummaryCard label="Überfällig" count={summary.overdue_count} amount={summary.overdue_amount} tone="red" active={filter === "overdue"} onClick={() => setFilter("overdue")} testid="sum-overdue" />
            <SummaryCard label="Offen" count={summary.open_count} amount={summary.open_amount} tone="amber" active={filter === "open"} onClick={() => setFilter("open")} testid="sum-open" />
            <SummaryCard label="Bezahlt (Archiv)" count={summary.paid_count} amount={summary.paid_amount} tone="emerald" active={filter === "archiv" || filter === "paid"} onClick={() => setFilter("archiv")} testid="sum-paid" />
          </div>
        </div>
      )}

      <main className="max-w-[1600px] mx-auto px-4 py-4 grid grid-cols-1 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)] gap-4">
        {/* Liste */}
        <section className="bg-white rounded-xl border border-gray-200 flex flex-col min-h-[70vh]">
          <div className="p-3 border-b border-gray-200 flex flex-wrap items-center gap-2">
            <div className="relative flex-1 min-w-[200px]">
              <Search className="w-4 h-4 text-gray-400 absolute left-2.5 top-1/2 -translate-y-1/2" />
              <Input
                value={search}
                onChange={e => setSearch(e.target.value)}
                placeholder="Suche Absender, Rechnungsnr., Datei…"
                className="pl-8"
                data-testid="search-input"
              />
            </div>
            <div className="flex items-center gap-1">
              {[
                { k: "aktiv", label: "Aktiv" },
                { k: "overdue", label: "Überfällig" },
                { k: "open", label: "Offen" },
                { k: "archiv", label: "Archiv" },
                { k: "creditcard", label: "Kreditkarte" },
                { k: "sepa", label: "SEPA" },
              ].map(({ k, label }) => (
                <button
                  key={k}
                  onClick={() => setFilter(k)}
                  className={`px-2.5 py-1 rounded-md text-xs font-medium border ${filter === k ? "bg-gray-900 text-white border-gray-900" : "bg-white text-gray-700 border-gray-200 hover:border-gray-400"}`}
                  data-testid={`filter-${k}-btn`}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>

          {/* Bulk Action Bar */}
          {(filter === "aktiv" || filter === "overdue" || filter === "open") && filtered.some(r => r.status === "open" || r.status === "overdue") && (
            <div className="px-3 py-2 border-b border-gray-200 bg-gray-50 flex items-center gap-2 text-xs" data-testid="bulk-action-bar">
              <label className="inline-flex items-center gap-1.5 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={
                    filtered.filter(r => r.status === "open" || r.status === "overdue").length > 0 &&
                    filtered.filter(r => r.status === "open" || r.status === "overdue").every(r => checkedIds.has(r.id))
                  }
                  onChange={toggleCheckAllVisible}
                  className="rounded border-gray-300"
                  data-testid="bulk-check-all"
                />
                <span className="text-gray-700">Alle offenen wählen</span>
              </label>
              <span className="text-gray-400">•</span>
              <span className="text-gray-600" data-testid="bulk-selected-count">
                {checkedIds.size} ausgewählt
              </span>
              <div className="ml-auto flex items-center gap-2">
                {checkedIds.size > 0 && (
                  <>
                    <span className="text-gray-600">
                      Summe: {fmtEUR(
                        rows.filter(r => checkedIds.has(r.id) && (r.status === "open" || r.status === "overdue"))
                            .reduce((s, r) => s + Number(r.amount || 0), 0)
                      )}
                    </span>
                    <Button size="sm" variant="ghost" onClick={() => setCheckedIds(new Set())} data-testid="bulk-clear-btn">
                      Zurücksetzen
                    </Button>
                    <Button size="sm" onClick={bulkMarkPaid} disabled={bulking}
                            className="bg-emerald-600 hover:bg-emerald-700 text-white" data-testid="bulk-mark-paid-btn">
                      <CheckCircle className="w-3.5 h-3.5 mr-1" />
                      {bulking ? "Markiere…" : `${checkedIds.size} als bezahlt markieren`}
                    </Button>
                  </>
                )}
              </div>
            </div>
          )}

          <div className="flex-1 overflow-auto">
            {loading && (
              <div className="p-8 text-center text-gray-500">Lädt Eingangsrechnungen…</div>
            )}
            {!loading && filtered.length === 0 && (
              <div className="p-10 text-center text-gray-500">
                <FileText className="w-10 h-10 text-gray-300 mx-auto mb-2" />
                Keine Rechnungen gefunden.
              </div>
            )}
            <ul>
              {filtered.map(r => {
                const meta = STATUS_META[r.status] || STATUS_META.open;
                const Icon = meta.icon;
                const active = selected?.id === r.id;
                const isCheckable = r.status === "open" || r.status === "overdue";
                return (
                  <li key={r.id} className={`flex items-stretch border-b border-gray-100 ${meta.row} ${active ? "bg-fuchsia-50/40" : "hover:bg-gray-50"}`}>
                    {isCheckable && (
                      <label
                        onClick={(e) => e.stopPropagation()}
                        className="flex items-center px-3 cursor-pointer"
                        data-testid={`row-check-wrap-${r.id}`}
                      >
                        <input
                          type="checkbox"
                          checked={checkedIds.has(r.id)}
                          onChange={() => toggleCheck(r.id)}
                          className="rounded border-gray-300"
                          data-testid={`row-check-${r.id}`}
                        />
                      </label>
                    )}
                    <button
                      onClick={() => setSelected(r)}
                      className="flex-1 text-left px-4 py-3 flex gap-3"
                      data-testid={`invoice-row-${r.id}`}
                    >
                      <Icon className={`w-4 h-4 mt-0.5 flex-shrink-0 ${
                        r.status === "overdue"    ? "text-red-500" :
                        r.status === "paid"       ? "text-emerald-500" :
                        r.status === "creditcard" ? "text-indigo-500" :
                        r.status === "sepa"       ? "text-sky-500" :
                        "text-amber-500"
                      }`} />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-baseline gap-2 flex-wrap">
                          <span className="font-medium text-gray-900 truncate">{r.sender || r.filename || "—"}</span>
                          {r.invoice_number && <span className="text-xs text-gray-500">#{r.invoice_number}</span>}
                        </div>
                        <div className="text-xs text-gray-500 mt-0.5 flex flex-wrap gap-x-3 gap-y-0.5">
                          <span>Rechn.: {fmtDate(r.invoice_date)}</span>
                          <span>Fällig: {fmtDate(r.due_date)}</span>
                          {r.status === "paid" && r.paid_at && (
                            <span className="text-emerald-700 font-medium">
                              Bezahlt am {fmtDate(r.paid_at)}
                            </span>
                          )}
                        </div>
                      </div>
                      <div className="text-right flex-shrink-0">
                        <div className="font-semibold text-gray-900">{fmtEUR(r.amount)}</div>
                        <span className={`inline-block mt-1 text-[10px] font-medium px-1.5 py-0.5 rounded border ${meta.cls}`}>{meta.label}</span>
                      </div>
                    </button>
                  </li>
                );
              })}
            </ul>
          </div>
        </section>

        {/* Preview + Detail */}
        <section className="bg-white rounded-xl border border-gray-200 flex flex-col min-h-[70vh]">
          {!selected ? (
            <div className="flex-1 flex items-center justify-center text-gray-400">
              <div className="text-center">
                <FileText className="w-12 h-12 mx-auto mb-2 text-gray-300" />
                Rechnung wählen, um Vorschau und Details anzuzeigen.
              </div>
            </div>
          ) : (
            <>
              <div className="p-3 border-b border-gray-200 flex items-start gap-3">
                <div className="flex-1 min-w-0">
                  <div className="font-semibold text-gray-900 truncate" data-testid="detail-sender">{selected.sender || selected.filename}</div>
                  <div className="text-xs text-gray-500 truncate">{selected.filename}{selected.invoice_number ? ` • #${selected.invoice_number}` : ""}</div>
                </div>
                <button onClick={() => setSelected(null)} className="text-gray-400 hover:text-gray-700" data-testid="detail-close-btn">
                  <X className="w-4 h-4" />
                </button>
              </div>

              {/* Meta / Actions */}
              <div className="p-3 border-b border-gray-200 grid grid-cols-2 gap-3 text-sm">
                <div>
                  <div className="text-xs text-gray-500">Betrag</div>
                  <div className="font-semibold text-gray-900 flex items-center gap-1"><Euro className="w-3.5 h-3.5" /> {fmtEUR(selected.amount)}</div>
                </div>
                <div>
                  <div className="text-xs text-gray-500">Status</div>
                  <div>
                    <span className={`inline-block text-xs font-medium px-2 py-0.5 rounded border ${(STATUS_META[selected.status] || STATUS_META.open).cls}`} data-testid="detail-status">
                      {(STATUS_META[selected.status] || STATUS_META.open).label}
                    </span>
                  </div>
                </div>
                <div>
                  <div className="text-xs text-gray-500">Rechnungsdatum</div>
                  <div className="text-gray-800">{fmtDate(selected.invoice_date)}</div>
                </div>
                <div>
                  <div className="text-xs text-gray-500">Fälligkeit</div>
                  <Input
                    type="date"
                    value={editDue || ""}
                    onChange={e => setEditDue(e.target.value)}
                    className="h-8"
                    data-testid="detail-due-input"
                  />
                  {selected.payment_term_days && (
                    <div className="text-[10px] text-gray-500 mt-0.5" data-testid="detail-payment-terms">
                      Zahlungsziel: {selected.payment_term_days} Tage
                      {selected.payment_terms ? ` (${selected.payment_terms.slice(0, 40).trim()}…)` : ""}
                    </div>
                  )}
                </div>
                <div className="col-span-2">
                  <div className="text-xs text-gray-500">Notiz</div>
                  <Input
                    value={editNotes}
                    onChange={e => setEditNotes(e.target.value)}
                    placeholder="Optionale Notiz…"
                    className="h-8"
                    data-testid="detail-notes-input"
                  />
                </div>
                {selected.iban && (
                  <div className="col-span-2">
                    <div className="text-xs text-gray-500">IBAN (aus Rechnung)</div>
                    <div className="font-mono text-xs text-gray-800">{selected.iban}</div>
                  </div>
                )}
                {selected.paid_source && (
                  <div className="col-span-2 text-xs text-gray-500">
                    Bezahlt-Quelle: <span className="text-gray-700">{selected.paid_source}</span>
                  </div>
                )}
              </div>

              <div className="p-3 border-b border-gray-200 flex flex-wrap gap-2">
                <Button size="sm" variant="outline" onClick={saveMeta} disabled={saving} data-testid="save-meta-btn">
                  <Save className="w-4 h-4 mr-1" /> {saving ? "Speichere…" : "Änderungen speichern"}
                </Button>
                {selected.status !== "paid" && selected.status !== "creditcard" && selected.status !== "sepa" ? (
                  <Button size="sm" onClick={() => markPaid(selected)} disabled={marking} className="bg-emerald-600 hover:bg-emerald-700 text-white" data-testid="mark-paid-btn">
                    <CheckCircle className="w-4 h-4 mr-1" /> {marking ? "Speichere…" : "Als bezahlt markieren"}
                  </Button>
                ) : selected.status === "paid" ? (
                  <span className="text-xs text-emerald-700 self-center inline-flex items-center gap-1">
                    <CheckCircle className="w-3.5 h-3.5" /> Bezahlt {selected.paid_at ? `am ${fmtDate(selected.paid_at)}` : ""}
                  </span>
                ) : selected.status === "creditcard" ? (
                  <span className="text-xs text-indigo-700 self-center inline-flex items-center gap-1">
                    <CreditCard className="w-3.5 h-3.5" /> Kreditkarte {selected.paid_by_creditcard_at ? `seit ${fmtDate(selected.paid_by_creditcard_at)}` : ""}
                  </span>
                ) : (
                  <span className="text-xs text-sky-700 self-center inline-flex items-center gap-1">
                    <Repeat className="w-3.5 h-3.5" /> SEPA-Lastschrift {selected.paid_by_sepa_at ? `seit ${fmtDate(selected.paid_by_sepa_at)}` : ""}
                  </span>
                )}
                {selected.status !== "creditcard" && selected.status !== "paid" && (
                  <Button size="sm" variant="outline" onClick={() => markPaymentMethod(selected, "creditcard")} className="text-indigo-700 border-indigo-200 hover:bg-indigo-50" data-testid="mark-creditcard-btn">
                    <CreditCard className="w-4 h-4 mr-1" /> Kreditkarte
                  </Button>
                )}
                {selected.status !== "sepa" && selected.status !== "paid" && (
                  <Button size="sm" variant="outline" onClick={() => markPaymentMethod(selected, "sepa")} className="text-sky-700 border-sky-200 hover:bg-sky-50" data-testid="mark-sepa-btn">
                    <Repeat className="w-4 h-4 mr-1" /> SEPA
                  </Button>
                )}
                <Button size="sm" variant="outline" onClick={() => markNotInvoice(selected)} className="ml-auto text-red-700 border-red-200 hover:bg-red-50" data-testid="mark-not-invoice-btn">
                  <Ban className="w-4 h-4 mr-1" /> Keine Rechnung
                </Button>
              </div>

              {/* Preview */}
              <div className="flex-1 bg-gray-100 overflow-auto">
                {selected.content_type === "application/pdf" && previewBlobUrl && (
                  <object
                    data={previewBlobUrl}
                    type="application/pdf"
                    className="w-full h-full min-h-[500px]"
                    aria-label="PDF Preview"
                    data-testid="pdf-preview"
                  >
                    <iframe src={previewBlobUrl} title="PDF" className="w-full h-full min-h-[500px]" />
                  </object>
                )}
                {selected.content_type?.startsWith("image/") && previewBlobUrl && (
                  <img src={previewBlobUrl} alt="" className="w-full" data-testid="image-preview" />
                )}
                {!previewBlobUrl && (
                  <div className="p-8 text-center text-gray-400">Keine Vorschau verfügbar.</div>
                )}
              </div>
            </>
          )}
        </section>
      </main>
    </div>
  );
}

function SummaryCard({ label, count, amount, tone, active, onClick, testid }) {
  const tones = {
    red: "border-red-200 bg-red-50 text-red-700 hover:border-red-400",
    amber: "border-amber-200 bg-amber-50 text-amber-700 hover:border-amber-400",
    emerald: "border-emerald-200 bg-emerald-50 text-emerald-700 hover:border-emerald-400",
  };
  const activeRing = active ? "ring-2 ring-gray-900 ring-offset-1" : "";
  return (
    <button
      type="button"
      onClick={onClick}
      className={`text-left rounded-xl border p-4 transition ${tones[tone]} ${activeRing}`}
      data-testid={testid}
    >
      <div className="text-xs font-medium uppercase tracking-wide">{label}</div>
      <div className="mt-1 flex items-baseline gap-2">
        <div className="text-2xl font-bold">{fmtEUR(amount)}</div>
        <div className="text-xs opacity-80">({count})</div>
      </div>
    </button>
  );
}
