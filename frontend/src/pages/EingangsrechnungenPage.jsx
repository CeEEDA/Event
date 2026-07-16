import { useState, useEffect, useCallback, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import api from "../lib/api";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import {
  ArrowLeft, Search, FileText, CheckCircle, AlertTriangle, Clock,
  Receipt, X, Save, Euro, Landmark,
} from "lucide-react";
import { toast } from "sonner";

const STATUS_META = {
  overdue: { label: "Überfällig", cls: "bg-red-50 text-red-700 border-red-200", icon: AlertTriangle, row: "border-l-4 border-l-red-500" },
  open:    { label: "Offen",      cls: "bg-amber-50 text-amber-700 border-amber-200", icon: Clock, row: "border-l-4 border-l-amber-400" },
  paid:    { label: "Bezahlt",    cls: "bg-emerald-50 text-emerald-700 border-emerald-200", icon: CheckCircle, row: "border-l-4 border-l-emerald-500" },
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
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("alle");
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState(null);
  const [previewBlobUrl, setPreviewBlobUrl] = useState(null);
  const [editDue, setEditDue] = useState("");
  const [editNotes, setEditNotes] = useState("");
  const [saving, setSaving] = useState(false);
  const [marking, setMarking] = useState(false);
  const [matching, setMatching] = useState(false);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      const token = localStorage.getItem("token");
      const { data } = await api.get("/incoming-invoices", { params: { token } });
      setRows(data.invoices || []);
      setSummary(data.summary || null);
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
    return rows.filter(r => {
      if (filter !== "alle" && r.status !== filter) return false;
      if (!q) return true;
      return [r.sender, r.invoice_number, r.filename, r.notes].some(v => (v || "").toLowerCase().includes(q));
    });
  }, [rows, filter, search]);

  const runAutoMatch = async () => {
    if (!window.confirm("FinTS-Abgleich starten?\n\nZieht Sparkassen-Buchungen der letzten 60 Tage und ordnet sie automatisch offenen Eingangsrechnungen zu.\n\nHinweis: Bei Erstanmeldung ist eine pushTAN-Bestätigung nötig.")) return;
    setMatching(true);
    try {
      const token = localStorage.getItem("token");
      const { data } = await api.post("/incoming-invoices/fints/auto-match", null, {
        params: { token, days_back: 60 }, timeout: 180000,
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
            <Button variant="outline" size="sm" onClick={load} disabled={loading} data-testid="reload-btn">
              {loading ? "Lädt…" : "Neu laden"}
            </Button>
          </div>
        </div>
      </header>

      {/* Summary Cards */}
      {summary && (
        <div className="max-w-[1600px] mx-auto px-4 pt-4">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <SummaryCard label="Überfällig" count={summary.overdue_count} amount={summary.overdue_amount} tone="red" testid="sum-overdue" />
            <SummaryCard label="Offen" count={summary.open_count} amount={summary.open_amount} tone="amber" testid="sum-open" />
            <SummaryCard label="Bezahlt" count={summary.paid_count} amount={summary.paid_amount} tone="emerald" testid="sum-paid" />
          </div>
        </div>
      )}

      <main className="max-w-[1600px] mx-auto px-4 py-4 grid grid-cols-1 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] gap-4">
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
              {["alle", "overdue", "open", "paid"].map(k => (
                <button
                  key={k}
                  onClick={() => setFilter(k)}
                  className={`px-2.5 py-1 rounded-md text-xs font-medium border ${filter === k ? "bg-gray-900 text-white border-gray-900" : "bg-white text-gray-700 border-gray-200 hover:border-gray-400"}`}
                  data-testid={`filter-${k}-btn`}
                >
                  {k === "alle" ? "Alle" : STATUS_META[k].label}
                </button>
              ))}
            </div>
          </div>

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
                return (
                  <li key={r.id}>
                    <button
                      onClick={() => setSelected(r)}
                      className={`w-full text-left px-4 py-3 border-b border-gray-100 hover:bg-gray-50 flex gap-3 ${meta.row} ${active ? "bg-fuchsia-50/40" : ""}`}
                      data-testid={`invoice-row-${r.id}`}
                    >
                      <Icon className={`w-4 h-4 mt-0.5 flex-shrink-0 ${r.status === "overdue" ? "text-red-500" : r.status === "paid" ? "text-emerald-500" : "text-amber-500"}`} />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-baseline gap-2 flex-wrap">
                          <span className="font-medium text-gray-900 truncate">{r.sender || r.filename || "—"}</span>
                          {r.invoice_number && <span className="text-xs text-gray-500">#{r.invoice_number}</span>}
                        </div>
                        <div className="text-xs text-gray-500 mt-0.5 flex flex-wrap gap-x-3 gap-y-0.5">
                          <span>Rechn.: {fmtDate(r.invoice_date)}</span>
                          <span>Fällig: {fmtDate(r.due_date)}</span>
                          {r.paid_at && <span>Bezahlt: {fmtDate(r.paid_at)}</span>}
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
                {selected.status !== "paid" ? (
                  <Button size="sm" onClick={() => markPaid(selected)} disabled={marking} className="bg-emerald-600 hover:bg-emerald-700 text-white" data-testid="mark-paid-btn">
                    <CheckCircle className="w-4 h-4 mr-1" /> {marking ? "Speichere…" : "Als bezahlt markieren"}
                  </Button>
                ) : (
                  <span className="text-xs text-emerald-700 self-center inline-flex items-center gap-1">
                    <CheckCircle className="w-3.5 h-3.5" /> Bezahlt {selected.paid_at ? `am ${fmtDate(selected.paid_at)}` : ""}
                  </span>
                )}
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

function SummaryCard({ label, count, amount, tone, testid }) {
  const tones = {
    red: "border-red-200 bg-red-50 text-red-700",
    amber: "border-amber-200 bg-amber-50 text-amber-700",
    emerald: "border-emerald-200 bg-emerald-50 text-emerald-700",
  };
  return (
    <div className={`rounded-xl border p-4 ${tones[tone]}`} data-testid={testid}>
      <div className="text-xs font-medium uppercase tracking-wide">{label}</div>
      <div className="mt-1 flex items-baseline gap-2">
        <div className="text-2xl font-bold">{fmtEUR(amount)}</div>
        <div className="text-xs opacity-80">({count})</div>
      </div>
    </div>
  );
}
