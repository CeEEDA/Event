/**
 * Tankbeleg-Modal (gemeinsam genutzt)
 *
 * Wird verwendet in:
 *  - OrderDetailPage: Beleg in einem Auftrag erfassen/bearbeiten
 *  - FuelManagementPage (Tankbeleg-Verwaltung): Bestehenden Beleg admin-seitig bearbeiten
 *
 * Beim Bearbeiten (receipt vorhanden) wird PUT /api/fuel-receipts/{id}
 * gerufen; beim Erfassen POST /api/fuel-receipts (order_pk/order_name aus Props).
 */
import { useState } from "react";
import { Loader2 } from "lucide-react";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import api from "../lib/api";
import { toast } from "sonner";

export const FUEL_TYPES_OPTIONS = [
  { value: "diesel", label: "Diesel" },
  { value: "heizoel_leicht", label: "HEL schwefelarm" },
  { value: "hvo", label: "HVO" },
];

export default function FuelReceiptModal({ receipt, orderPk, orderName, onClose, onSave }) {
  const [form, setForm] = useState({
    fuel_type: receipt?.fuel_type || "diesel",
    quantity_liters: receipt?.quantity_liters || "",
    date: receipt?.date || new Date().toISOString().split("T")[0],
    time: receipt?.time || new Date().toTimeString().slice(0, 5),
    location: receipt?.location || "",
    abgabe_start: receipt?.abgabe_start || "",
    abgabe_ende: receipt?.abgabe_ende || "",
    fahrer: receipt?.fahrer || "",
    notes: receipt?.notes || "",
  });
  const [saving, setSaving] = useState(false);

  const handleSave = async () => {
    if (!form.quantity_liters) { toast.error("Bitte Menge eingeben"); return; }
    setSaving(true);
    try {
      const payload = {
        ...form,
        quantity_liters: parseFloat(form.quantity_liters),
      };
      if (receipt) {
        await api.put(`/fuel-receipts/${receipt.id}`, payload);
        toast.success("Beleg aktualisiert");
      } else {
        await api.post("/fuel-receipts", {
          ...payload,
          order_pk: orderPk,
          order_name: orderName,
        });
        toast.success("Beleg erstellt");
      }
      onSave();
    } catch (err) {
      toast.error(typeof err?.response?.data?.detail === "string" ? err.response.data.detail : "Fehler");
    } finally { setSaving(false); }
  };

  // Im Admin-Kontext (Tankbeleg-Verwaltung) ist orderName nicht immer
  // sinnvoll - dann zeigen wir Belegnr. und Kundenname.
  const headerLine = orderName
    || (receipt ? `${receipt.beleg_nr || "Beleg"} · ${receipt.customer_name || receipt.order_name || ""}` : "");

  return (
    <div className="fixed inset-0 bg-black/40 z-[10000] flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-white rounded-xl p-6 w-full max-w-md max-h-[90vh] overflow-y-auto" onClick={e => e.stopPropagation()} data-testid="fuel-receipt-modal">
        <h2 className="text-lg font-bold text-gray-900 mb-1">{receipt ? "Beleg bearbeiten" : "Neuer Tankbeleg"}</h2>
        {headerLine && <p className="text-sm text-gray-500 mb-4">{headerLine}</p>}
        <div className="space-y-3">
          <div>
            <Label className="text-sm text-gray-600">Kraftstoffart</Label>
            <select value={form.fuel_type} onChange={e => setForm(f => ({ ...f, fuel_type: e.target.value }))} className="w-full mt-1 border rounded-lg px-3 py-2 text-sm" data-testid="fuel-modal-type">
              {FUEL_TYPES_OPTIONS.map(t => (
                <option key={t.value} value={t.value}>{t.label}</option>
              ))}
            </select>
          </div>
          <div>
            <Label className="text-sm text-gray-600">Menge bei 15 C (Liter)</Label>
            <Input type="number" step="0.1" value={form.quantity_liters} onChange={e => setForm(f => ({ ...f, quantity_liters: e.target.value }))} placeholder="z.B. 183" className="mt-1" data-testid="fuel-modal-qty" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label className="text-sm text-gray-600">Abgabe-Datum</Label>
              <Input type="date" value={form.date} onChange={e => setForm(f => ({ ...f, date: e.target.value }))} className="mt-1" data-testid="fuel-modal-date" />
            </div>
            <div>
              <Label className="text-sm text-gray-600">Uhrzeit</Label>
              <Input type="time" value={form.time} onChange={e => setForm(f => ({ ...f, time: e.target.value }))} className="mt-1" data-testid="fuel-modal-time" />
            </div>
          </div>

          <p className="text-xs text-gray-400 pt-2 border-t border-gray-100 font-medium uppercase tracking-wide">Druckerdaten</p>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label className="text-sm text-gray-600">Abgabe-Start</Label>
              <Input type="time" step="1" value={form.abgabe_start} onChange={e => setForm(f => ({ ...f, abgabe_start: e.target.value }))} className="mt-1 font-mono" data-testid="fuel-modal-start" />
            </div>
            <div>
              <Label className="text-sm text-gray-600">Abgabe-Ende</Label>
              <Input type="time" step="1" value={form.abgabe_ende} onChange={e => setForm(f => ({ ...f, abgabe_ende: e.target.value }))} className="mt-1 font-mono" data-testid="fuel-modal-ende" />
            </div>
          </div>

          <p className="text-xs text-gray-400 pt-2 border-t border-gray-100 font-medium uppercase tracking-wide">Manuelle Eingabe</p>
          <div>
            <Label className="text-sm text-gray-600">Standort</Label>
            <Input value={form.location} onChange={e => setForm(f => ({ ...f, location: e.target.value }))} placeholder="z.B. Baustelle" className="mt-1" data-testid="fuel-modal-location" />
          </div>
          <div>
            <Label className="text-sm text-gray-600">Fahrer</Label>
            <Input value={form.fahrer} onChange={e => setForm(f => ({ ...f, fahrer: e.target.value }))} placeholder="z.B. Timo" className="mt-1" data-testid="fuel-modal-fahrer" />
          </div>
          <div>
            <Label className="text-sm text-gray-600">Bemerkung</Label>
            <Input value={form.notes} onChange={e => setForm(f => ({ ...f, notes: e.target.value }))} placeholder="Optional" className="mt-1" data-testid="fuel-modal-notes" />
          </div>
        </div>
        <div className="flex gap-3 mt-5">
          <Button onClick={handleSave} disabled={saving} className="flex-1 bg-amber-500 hover:bg-amber-600 text-white" data-testid="fuel-modal-save">
            {saving ? <Loader2 className="w-4 h-4 mr-1.5 animate-spin" /> : null}
            {receipt ? "Speichern" : "Erstellen"}
          </Button>
          <Button variant="outline" onClick={onClose} className="flex-1">Abbrechen</Button>
        </div>
      </div>
    </div>
  );
}
