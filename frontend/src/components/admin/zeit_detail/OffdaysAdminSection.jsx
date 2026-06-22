/**
 * Offdays-Sektion fuer AdminZeitDetailPage.
 * Zeigt fuer EINEN Mitarbeiter:
 *  - Aktuellen Saldo
 *  - Buchungs-Historie
 *  - +/- Manuelle Korrektur
 *
 * Der Mitarbeiter selbst sieht NUR seine eigene Page unter
 * /mitarbeiter-daten/offdays - dort gibt es weder eine User-Liste noch
 * Korrektur-Buttons. Diese Sektion ist ausschliesslich der Admin-Pfad.
 */
import { useState, useEffect, useCallback } from "react";
import api from "../../../lib/api";
import { toast } from "sonner";
import { Button } from "../../ui/button";
import { Input } from "../../ui/input";
import { Textarea } from "../../ui/textarea";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "../../ui/dialog";
import { CalendarCheck2, Trees, PlusCircle, MinusCircle, Sun, Calendar, Pencil, Sparkles } from "lucide-react";

const SOURCE_ICONS = { clock_in: Sun, shift_assignment: Calendar, manual: Pencil };
const SOURCE_LABELS = { clock_in: "Stempelzeit", shift_assignment: "Einsatzplanung", manual: "Manuell" };

// Formatiert "2026-06-29" als "So 29.06.2026" - so erkennt der Admin sofort
// ob es ein Sonntag/Feiertag war (passt zum Auto-Akkrual?).
function fmtRefDate(iso) {
  if (!iso) return "-";
  try {
    const d = new Date(iso + "T00:00:00");
    const weekday = d.toLocaleDateString("de-DE", { weekday: "short", timeZone: "Europe/Berlin" });
    const date = d.toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit", year: "numeric", timeZone: "Europe/Berlin" });
    return `${weekday} ${date}`;
  } catch {
    return iso;
  }
}

export default function OffdaysAdminSection({ userId, token, userName }) {
  const [data, setData] = useState({ balance: 0, entries: [] });
  const [loading, setLoading] = useState(true);
  const [adjustOpen, setAdjustOpen] = useState(false);
  const [adjustForm, setAdjustForm] = useState({ delta: 1, note: "", ref_date: new Date().toISOString().slice(0,10) });
  const [submitting, setSubmitting] = useState(false);

  const load = useCallback(async () => {
    if (!userId) return;
    setLoading(true);
    try {
      const r = await api.get(`/employee/offdays/user/${userId}?token=${token}`);
      setData(r.data || { balance: 0, entries: [] });
    } catch {
      // 403 wenn user keine Verwaltung-Berechtigung hat - dann ueberhaupt
      // nichts anzeigen.
    }
    setLoading(false);
  }, [userId, token]);

  useEffect(() => { load(); }, [load]);

  const openAdjust = (sign) => {
    setAdjustForm({ delta: sign, note: "", ref_date: new Date().toISOString().slice(0,10) });
    setAdjustOpen(true);
  };

  const submitAdjust = async () => {
    const d = parseInt(adjustForm.delta);
    if (!d || isNaN(d)) { toast.error("Bitte gültige Zahl eingeben (z.B. +1, -2)"); return; }
    if (!adjustForm.ref_date) { toast.error("Bitte Datum wählen"); return; }
    setSubmitting(true);
    try {
      const r = await api.post(`/employee/offdays/adjust?token=${token}`, {
        user_id: userId, delta: d, note: adjustForm.note, ref_date: adjustForm.ref_date,
      });
      toast.success(`Saldo: ${r.data?.new_balance ?? "?"}`);
      setAdjustOpen(false);
      load();
    } catch (e) { toast.error(e.response?.data?.detail || "Fehler"); }
    setSubmitting(false);
  };

  return (
    <div className="bg-white rounded-xl border border-violet-200 p-4" data-testid="offdays-admin-section">
      <div className="flex items-center gap-2 mb-3">
        <CalendarCheck2 className="w-4 h-4 text-violet-600" />
        <p className="text-[10px] font-semibold text-violet-600 uppercase tracking-wider">Offdays / Ausgleichstage</p>
        <span className="text-[10px] text-gray-400 ml-auto">Auto: Sonntag/Feiertag-Stempelung · Verbrauch: Einsatzplanung</span>
      </div>

      <div className="flex items-center gap-4 mb-4 p-4 bg-gradient-to-br from-violet-50 to-fuchsia-50 rounded-lg">
        <div className="w-12 h-12 rounded-xl bg-white flex items-center justify-center shadow-sm">
          <Trees className="w-6 h-6 text-violet-600" />
        </div>
        <div className="flex-1">
          <p className="text-[10px] uppercase tracking-wider text-violet-700/70 font-medium">Aktueller Saldo</p>
          <p className="text-3xl font-bold text-gray-900 font-mono" data-testid="offday-balance">{data.balance}</p>
        </div>
        <div className="flex gap-2">
          <Button size="sm" onClick={() => openAdjust(1)} className="bg-emerald-600 hover:bg-emerald-700" data-testid="offday-plus">
            <PlusCircle className="w-3.5 h-3.5 mr-1" /> Gutschreiben
          </Button>
          <Button size="sm" onClick={() => openAdjust(-1)} variant="outline" className="border-rose-300 text-rose-600 hover:bg-rose-50" data-testid="offday-minus">
            <MinusCircle className="w-3.5 h-3.5 mr-1" /> Abziehen
          </Button>
        </div>
      </div>

      {loading ? (
        <p className="text-xs text-gray-400 px-4 py-3">Wird geladen ...</p>
      ) : data.entries.length === 0 ? (
        <p className="text-xs text-gray-400 px-4 py-3">Noch keine Buchungen.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead className="text-gray-500 border-b border-gray-100">
              <tr>
                <th className="text-left font-medium py-1.5 pr-2">Für Tag</th>
                <th className="text-left font-medium py-1.5 pr-2">Quelle</th>
                <th className="text-right font-medium py-1.5 pr-2">Δ</th>
                <th className="text-left font-medium py-1.5 pr-2 hidden md:table-cell">Notiz</th>
                <th className="text-left font-medium py-1.5 hidden lg:table-cell">Von</th>
              </tr>
            </thead>
            <tbody data-testid="offday-entries">
              {data.entries.map(e => {
                const Icon = SOURCE_ICONS[e.source] || Sparkles;
                const isPlus = (e.delta || 0) > 0;
                // Sonntag (Mi 6) oder Feiertag-Hint visualisieren
                const d = e.ref_date ? new Date(e.ref_date + "T00:00:00") : null;
                const isSun = d && d.getDay() === 0;
                return (
                  <tr key={e.id} className="border-b border-gray-50 last:border-0">
                    <td className={`py-1.5 pr-2 font-mono ${isSun ? "text-rose-600 font-semibold" : "text-gray-700"}`} title={e.ref_date}>
                      {fmtRefDate(e.ref_date)}
                    </td>
                    <td className="py-1.5 pr-2">
                      <span className="inline-flex items-center gap-1 text-gray-700">
                        <Icon className="w-3 h-3 text-gray-400" />
                        {e.source_label || SOURCE_LABELS[e.source] || e.source}
                      </span>
                    </td>
                    <td className={`py-1.5 pr-2 text-right font-mono font-semibold ${isPlus ? "text-emerald-600" : "text-rose-600"}`}>
                      {isPlus ? "+" : ""}{e.delta}
                    </td>
                    <td className="py-1.5 pr-2 text-gray-500 hidden md:table-cell">{e.note || ""}</td>
                    <td className="py-1.5 text-gray-400 hidden lg:table-cell">{e.created_by || ""}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      <Dialog open={adjustOpen} onOpenChange={setAdjustOpen}>
        <DialogContent className="sm:max-w-md" data-testid="offday-adjust-dialog" aria-describedby="offday-adjust-desc">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Sparkles className="w-5 h-5 text-violet-600" /> Offday-Korrektur
            </DialogTitle>
          </DialogHeader>
          <p id="offday-adjust-desc" className="sr-only">Offday-Saldo des Mitarbeiters anpassen</p>
          <div className="space-y-3 pt-2">
            <p className="text-sm text-gray-600">Mitarbeiter: <strong>{userName || "—"}</strong></p>
            <div>
              <label className="text-xs text-gray-500 mb-1 block">Für welchen Tag?</label>
              <Input type="date" value={adjustForm.ref_date} onChange={e => setAdjustForm(f => ({ ...f, ref_date: e.target.value }))} data-testid="offday-adjust-date" />
              <p className="text-[10px] text-gray-400 mt-1">Datum, für das der Offday gutgeschrieben oder abgezogen werden soll (z.B. der gearbeitete Sonntag).</p>
            </div>
            <div>
              <label className="text-xs text-gray-500 mb-1 block">Anzahl (positiv = gutschreiben, negativ = abziehen)</label>
              <Input type="number" value={adjustForm.delta} onChange={e => setAdjustForm(f => ({ ...f, delta: e.target.value }))} data-testid="offday-adjust-delta" />
            </div>
            <div>
              <label className="text-xs text-gray-500 mb-1 block">Begründung</label>
              <Textarea rows={2} value={adjustForm.note} onChange={e => setAdjustForm(f => ({ ...f, note: e.target.value }))} placeholder="z.B. Übertrag aus Excel, Korrektur..." data-testid="offday-adjust-note" />
            </div>
            <Button onClick={submitAdjust} disabled={submitting} className="w-full bg-violet-600 hover:bg-violet-700" data-testid="offday-adjust-submit">
              {submitting ? "Wird gespeichert..." : "Speichern"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
