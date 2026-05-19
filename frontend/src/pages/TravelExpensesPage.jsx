import { useState, useEffect, useRef, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import api from "../lib/api";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Textarea } from "../components/ui/textarea";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "../components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { toast } from "sonner";
import { ArrowLeft, Plane, Plus, FileDown, Paperclip, X, Trash2, Check, AlertCircle, MapPin, Calendar, Clock } from "lucide-react";

const STATUS_BADGES = {
  submitted: { label: "Eingereicht", cls: "bg-amber-100 text-amber-700" },
  approved:  { label: "Genehmigt",   cls: "bg-emerald-100 text-emerald-700" },
  rejected:  { label: "Abgelehnt",   cls: "bg-red-100 text-red-700" },
};

const emptyTrip = {
  trip_purpose: "",
  country_code: "DE",
  departure_at: "",
  arrival_at: "",
  km_private: 0,
  breakfasts_provided: 0,
  lunches_provided: 0,
  dinners_provided: 0,
  accommodation_cost: 0,
  other_expenses: 0,
  other_expenses_note: "",
  notes: "",
};

export default function TravelExpensesPage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const token = localStorage.getItem("token");

  const [trips, setTrips] = useState([]);
  const [countries, setCountries] = useState([]);
  const [loading, setLoading] = useState(true);

  // Dialog state
  const [showNew, setShowNew] = useState(false);
  const [trip, setTrip] = useState(emptyTrip);
  const [preview, setPreview] = useState(null);
  const [previewing, setPreviewing] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [receipts, setReceipts] = useState([]);
  const fileRef = useRef(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [tx, cx] = await Promise.all([
        api.get(`/employee/travel-expenses/mine?token=${token}`),
        api.get(`/employee/travel-expenses/countries?token=${token}`),
      ]);
      setTrips(tx.data || []);
      setCountries(cx.data?.countries || []);
    } catch (e) {
      toast.error(e.response?.data?.detail || "Fehler beim Laden");
    }
    setLoading(false);
  }, [token]);

  useEffect(() => { load(); }, [load]);

  // Live preview – debounced
  useEffect(() => {
    if (!trip.trip_purpose || !trip.departure_at || !trip.arrival_at) {
      setPreview(null);
      return;
    }
    const timer = setTimeout(async () => {
      setPreviewing(true);
      try {
        const res = await api.post(`/employee/travel-expenses/preview?token=${token}`, trip);
        setPreview(res.data);
      } catch (e) {
        setPreview({ error: e.response?.data?.detail || "Berechnung fehlgeschlagen" });
      }
      setPreviewing(false);
    }, 350);
    return () => clearTimeout(timer);
  }, [trip, token]);

  const onPickFiles = (files) => {
    const arr = Array.from(files || []).slice(0, 6 - receipts.length);
    setReceipts(prev => [...prev, ...arr]);
    if (fileRef.current) fileRef.current.value = "";
  };

  const submit = async () => {
    if (!trip.trip_purpose.trim()) { toast.error("Reisezweck angeben"); return; }
    if (!trip.departure_at || !trip.arrival_at) { toast.error("Reisebeginn und -ende angeben"); return; }
    setSubmitting(true);
    try {
      const fd = new FormData();
      Object.entries(trip).forEach(([k, v]) => fd.append(k, v ?? ""));
      receipts.forEach(f => fd.append("receipts", f));
      await api.post(`/employee/travel-expenses/?token=${token}`, fd, {
        headers: { "Content-Type": "multipart/form-data" }
      });
      toast.success("Reise eingereicht");
      setShowNew(false);
      setTrip(emptyTrip);
      setPreview(null);
      setReceipts([]);
      load();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Fehler beim Speichern");
    }
    setSubmitting(false);
  };

  const deleteTrip = async (id) => {
    if (!confirm("Reise wirklich löschen?")) return;
    try {
      await api.delete(`/employee/travel-expenses/${id}?token=${token}`);
      toast.success("Gelöscht");
      load();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Fehler");
    }
  };

  const downloadPdf = (id) => {
    const url = `${process.env.REACT_APP_BACKEND_URL}/api/employee/travel-expenses/${id}/pdf?token=${token}`;
    window.open(url, "_blank");
  };

  // Group trips by month
  const groupedByMonth = trips.reduce((acc, t) => {
    const m = t.month || (t.departure_at || "").slice(0, 7);
    (acc[m] = acc[m] || []).push(t);
    return acc;
  }, {});
  const months = Object.keys(groupedByMonth).sort().reverse();

  return (
    <div className="min-h-screen bg-gray-50" data-testid="travel-expenses-page">
      <header className="sticky top-0 z-10 bg-white border-b border-gray-200">
        <div className="max-w-4xl mx-auto px-4 py-3 flex items-center gap-3">
          <Button variant="ghost" size="sm" onClick={() => navigate("/mitarbeiter-daten")} className="text-gray-600 hover:text-fuchsia-600" data-testid="back-btn">
            <ArrowLeft className="w-4 h-4 mr-1" /> Zurück
          </Button>
          <div className="h-5 w-px bg-gray-200" />
          <Plane className="w-5 h-5 text-cyan-600" />
          <h1 className="text-base font-semibold text-gray-900">Reisekosten</h1>
          {user?.name && <span className="text-sm text-gray-400 ml-auto hidden sm:block">{user.name}</span>}
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-4 py-6 space-y-6">
        <div className="flex items-center justify-between">
          <p className="text-sm text-gray-500">
            Verpflegungsmehraufwand nach §9 EStG, KM-Pauschale 0,30 €/km, steuerfrei für die Lohnabrechnung.
          </p>
          <Button onClick={() => setShowNew(true)} className="bg-cyan-600 hover:bg-cyan-700" data-testid="new-trip-btn">
            <Plus className="w-4 h-4 mr-1" /> Neue Reise
          </Button>
        </div>

        {loading ? (
          <div className="text-center py-12 text-gray-400 text-sm">Lade Reisen...</div>
        ) : trips.length === 0 ? (
          <div className="bg-white rounded-xl border border-gray-200 p-12 text-center">
            <Plane className="w-10 h-10 text-gray-300 mx-auto mb-3" />
            <p className="text-sm text-gray-500">Noch keine Reisen erfasst.</p>
            <Button onClick={() => setShowNew(true)} variant="outline" size="sm" className="mt-3">
              <Plus className="w-3.5 h-3.5 mr-1" /> Erste Reise erfassen
            </Button>
          </div>
        ) : months.map(m => {
          const items = groupedByMonth[m];
          const sum = items.reduce((s, t) => s + (t.computed?.total_eur || 0), 0);
          const approvedSum = items
            .filter(t => t.status === "approved")
            .reduce((s, t) => s + (t.computed?.total_eur || 0), 0);
          const [y, mn] = m.split("-");
          const monthLabel = new Date(parseInt(y), parseInt(mn) - 1).toLocaleDateString("de-DE", { month: "long", year: "numeric" });
          return (
            <div key={m} className="bg-white rounded-xl border border-gray-200 overflow-hidden" data-testid={`month-${m}`}>
              <div className="px-4 py-2.5 bg-gray-50 border-b border-gray-100 flex items-center justify-between">
                <h3 className="text-sm font-semibold text-gray-800 capitalize">{monthLabel}</h3>
                <div className="text-right">
                  <span className="text-xs text-gray-400 mr-2">{items.length} {items.length === 1 ? "Reise" : "Reisen"}</span>
                  <span className="text-sm font-bold text-gray-900">{sum.toFixed(2)} €</span>
                  {approvedSum !== sum && (
                    <span className="text-[10px] text-emerald-600 ml-1">({approvedSum.toFixed(2)} € genehmigt)</span>
                  )}
                </div>
              </div>
              <div className="divide-y divide-gray-100">
                {items.map(t => {
                  const c = t.computed || {};
                  const b = STATUS_BADGES[t.status] || STATUS_BADGES.submitted;
                  const dep = new Date(t.departure_at);
                  const arr = new Date(t.arrival_at);
                  return (
                    <div key={t.id} className="px-4 py-3 hover:bg-gray-50 flex items-center gap-4" data-testid={`trip-${t.id}`}>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <p className="font-medium text-sm text-gray-900 truncate">{t.trip_purpose}</p>
                          <span className={`text-[10px] font-semibold uppercase px-1.5 py-0.5 rounded ${b.cls}`}>{b.label}</span>
                        </div>
                        <div className="flex flex-wrap gap-x-4 gap-y-0.5 text-xs text-gray-500">
                          <span className="flex items-center gap-1"><MapPin className="w-3 h-3" />{c.country_name || t.country_code}</span>
                          <span className="flex items-center gap-1"><Calendar className="w-3 h-3" />{dep.toLocaleDateString("de-DE")} – {arr.toLocaleDateString("de-DE")}</span>
                          <span className="flex items-center gap-1"><Clock className="w-3 h-3" />{(c.total_hours || 0).toFixed(1)}h</span>
                          {(c.km || 0) > 0 && <span>{c.km} km</span>}
                          {(t.receipts || []).length > 0 && <span className="flex items-center gap-1"><Paperclip className="w-3 h-3" />{t.receipts.length} Beleg{t.receipts.length !== 1 ? "e" : ""}</span>}
                        </div>
                        {t.rejection_reason && (
                          <p className="text-[11px] text-red-600 mt-1 flex items-center gap-1">
                            <AlertCircle className="w-3 h-3" /> Ablehnung: {t.rejection_reason}
                          </p>
                        )}
                      </div>
                      <div className="text-right shrink-0">
                        <p className="text-base font-bold text-gray-900">{(c.total_eur || 0).toFixed(2)} €</p>
                        <p className="text-[10px] text-gray-400">
                          VMA {(c.per_diem_net || 0).toFixed(0)}€ + KM {(c.km_eur || 0).toFixed(0)}€
                        </p>
                      </div>
                      <div className="flex gap-1">
                        <button onClick={() => downloadPdf(t.id)} className="p-1.5 text-gray-400 hover:text-cyan-600 rounded" title="PDF herunterladen" data-testid={`pdf-${t.id}`}>
                          <FileDown className="w-4 h-4" />
                        </button>
                        {t.status === "submitted" && (
                          <button onClick={() => deleteTrip(t.id)} className="p-1.5 text-gray-400 hover:text-red-500 rounded" title="Löschen" data-testid={`del-${t.id}`}>
                            <Trash2 className="w-4 h-4" />
                          </button>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          );
        })}
      </main>

      {/* New Trip Dialog */}
      <Dialog open={showNew} onOpenChange={setShowNew}>
        <DialogContent className="sm:max-w-2xl max-h-[92vh] overflow-y-auto" data-testid="new-trip-dialog">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Plane className="w-5 h-5 text-cyan-600" /> Neue Reise erfassen
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-4 pt-2">
            <div>
              <label className="text-xs text-gray-500 mb-1 block">Reisezweck / Projekt *</label>
              <Input value={trip.trip_purpose} onChange={e => setTrip(p => ({...p, trip_purpose: e.target.value}))}
                placeholder="z.B. Kirmes Frankfurt – Aufbau" data-testid="trip-purpose" />
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="text-xs text-gray-500 mb-1 block">Land</label>
                <Select value={trip.country_code} onValueChange={v => setTrip(p => ({...p, country_code: v}))}>
                  <SelectTrigger data-testid="country-select"><SelectValue /></SelectTrigger>
                  <SelectContent className="max-h-[300px]">
                    {countries.map(c => (
                      <SelectItem key={c.code} value={c.code}>
                        {c.name} ({c.full.toFixed(0)} / {c.partial.toFixed(0)} €)
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <label className="text-xs text-gray-500 mb-1 block">Gefahrene km (Privat-Kfz)</label>
                <Input type="number" min="0" step="1" value={trip.km_private}
                  onChange={e => setTrip(p => ({...p, km_private: parseFloat(e.target.value || 0)}))}
                  data-testid="trip-km" />
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="text-xs text-gray-500 mb-1 block">Reisebeginn *</label>
                <Input type="datetime-local" value={trip.departure_at}
                  onChange={e => setTrip(p => ({...p, departure_at: e.target.value}))} data-testid="trip-dep" />
              </div>
              <div>
                <label className="text-xs text-gray-500 mb-1 block">Reiseende *</label>
                <Input type="datetime-local" value={trip.arrival_at}
                  onChange={e => setTrip(p => ({...p, arrival_at: e.target.value}))} data-testid="trip-arr" />
              </div>
            </div>

            <div>
              <p className="text-xs text-gray-500 mb-2">Gestellte Mahlzeiten (Anzahl über gesamte Reise)</p>
              <div className="grid grid-cols-3 gap-3">
                {[
                  {k: "breakfasts_provided", lbl: "Frühstücke (−20%)"},
                  {k: "lunches_provided",    lbl: "Mittagessen (−40%)"},
                  {k: "dinners_provided",    lbl: "Abendessen (−40%)"},
                ].map(f => (
                  <div key={f.k}>
                    <label className="text-[11px] text-gray-500 mb-1 block">{f.lbl}</label>
                    <Input type="number" min="0" step="1" value={trip[f.k]}
                      onChange={e => setTrip(p => ({...p, [f.k]: parseInt(e.target.value || 0)}))}
                      data-testid={`meal-${f.k}`} />
                  </div>
                ))}
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="text-xs text-gray-500 mb-1 block">Übernachtungskosten (€, gegen Beleg)</label>
                <Input type="number" min="0" step="0.01" value={trip.accommodation_cost}
                  onChange={e => setTrip(p => ({...p, accommodation_cost: parseFloat(e.target.value || 0)}))}
                  data-testid="trip-acc" />
              </div>
              <div>
                <label className="text-xs text-gray-500 mb-1 block">Sonstige Kosten (€)</label>
                <Input type="number" min="0" step="0.01" value={trip.other_expenses}
                  onChange={e => setTrip(p => ({...p, other_expenses: parseFloat(e.target.value || 0)}))}
                  data-testid="trip-other" />
              </div>
            </div>

            {trip.other_expenses > 0 && (
              <div>
                <label className="text-xs text-gray-500 mb-1 block">Beschreibung sonstige Kosten</label>
                <Input value={trip.other_expenses_note}
                  onChange={e => setTrip(p => ({...p, other_expenses_note: e.target.value}))}
                  placeholder="z.B. Parkgebühr, Maut" data-testid="trip-other-note" />
              </div>
            )}

            <div>
              <label className="text-xs text-gray-500 mb-1 block">Belege ({receipts.length}/6, max 10 MB pro Datei)</label>
              <input ref={fileRef} type="file" multiple className="hidden"
                accept=".pdf,image/*"
                onChange={e => onPickFiles(e.target.files)} data-testid="trip-files" />
              <div
                onClick={() => receipts.length < 6 && fileRef.current?.click()}
                onDragOver={e => e.preventDefault()}
                onDrop={e => { e.preventDefault(); onPickFiles(e.dataTransfer.files); }}
                className={`border-2 border-dashed rounded-lg p-3 text-center text-xs ${receipts.length >= 6 ? "border-gray-200 bg-gray-50 text-gray-400" : "border-cyan-300 bg-cyan-50/30 text-cyan-700 cursor-pointer hover:bg-cyan-50"}`}
              >
                <Paperclip className="w-4 h-4 mx-auto mb-1" />
                {receipts.length >= 6 ? "Max. 6 Belege erreicht" : "Belege hier ablegen oder klicken (PDF, JPG, PNG)"}
              </div>
              {receipts.length > 0 && (
                <div className="mt-2 space-y-1">
                  {receipts.map((f, i) => (
                    <div key={i} className="flex items-center gap-2 text-xs bg-gray-50 px-2 py-1 rounded">
                      <Paperclip className="w-3 h-3 text-gray-400" />
                      <span className="flex-1 truncate">{f.name}</span>
                      <span className="text-gray-400">{(f.size / 1024).toFixed(0)} KB</span>
                      <button onClick={() => setReceipts(prev => prev.filter((_, j) => j !== i))} className="text-gray-400 hover:text-red-500">
                        <X className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div>
              <label className="text-xs text-gray-500 mb-1 block">Notizen (optional)</label>
              <Textarea rows={2} value={trip.notes}
                onChange={e => setTrip(p => ({...p, notes: e.target.value}))}
                placeholder="Anmerkungen für die Buchhaltung..." data-testid="trip-notes" />
            </div>

            {/* Live Preview */}
            <div className="bg-gradient-to-br from-cyan-50 to-emerald-50 rounded-xl p-4 border border-cyan-200" data-testid="trip-preview">
              <div className="flex items-center justify-between mb-2">
                <p className="text-xs font-semibold text-cyan-700 uppercase">Berechnung (Live)</p>
                {previewing && <span className="text-[10px] text-gray-400">aktualisiert...</span>}
              </div>
              {preview?.error ? (
                <p className="text-sm text-red-600">{preview.error}</p>
              ) : !preview ? (
                <p className="text-xs text-gray-500">Trag Zweck, Beginn und Ende ein für Live-Berechnung...</p>
              ) : (
                <div className="space-y-1 text-sm">
                  <div className="flex justify-between text-gray-700">
                    <span>VMA: {preview.full_days}×{preview.full_rate}€ + {preview.partial_days}×{preview.partial_rate}€</span>
                    <span className="font-medium">{preview.per_diem_gross.toFixed(2)} €</span>
                  </div>
                  {preview.meal_deduction > 0 && (
                    <div className="flex justify-between text-red-600 text-xs">
                      <span>− Mahlzeiten-Kürzung</span>
                      <span>−{preview.meal_deduction.toFixed(2)} €</span>
                    </div>
                  )}
                  <div className="flex justify-between text-gray-700">
                    <span>KM-Pauschale ({preview.km} km × 0,30 €)</span>
                    <span className="font-medium">{preview.km_eur.toFixed(2)} €</span>
                  </div>
                  {preview.accommodation_eur > 0 && (
                    <div className="flex justify-between text-gray-700">
                      <span>Übernachtung</span>
                      <span className="font-medium">{preview.accommodation_eur.toFixed(2)} €</span>
                    </div>
                  )}
                  {preview.other_eur > 0 && (
                    <div className="flex justify-between text-gray-700">
                      <span>Sonstige Kosten</span>
                      <span className="font-medium">{preview.other_eur.toFixed(2)} €</span>
                    </div>
                  )}
                  <div className="flex justify-between border-t border-cyan-200 pt-1.5 mt-1.5">
                    <span className="font-bold text-gray-900">GESAMT (steuerfrei)</span>
                    <span className="font-bold text-emerald-700 text-lg">{preview.total_eur.toFixed(2)} €</span>
                  </div>
                </div>
              )}
            </div>

            <Button onClick={submit} disabled={submitting || !preview || preview?.error}
              className="w-full bg-cyan-600 hover:bg-cyan-700" data-testid="submit-trip-btn">
              <Check className="w-4 h-4 mr-1" /> {submitting ? "Wird eingereicht..." : "Reise einreichen"}
            </Button>
            <p className="text-[10px] text-gray-400 text-center">
              Nach Einreichung prüft die Verwaltung die Reise. Erst nach Freigabe wird sie in die Lohnabrechnung übernommen.
            </p>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
