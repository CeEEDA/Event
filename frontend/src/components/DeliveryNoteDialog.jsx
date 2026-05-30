import { useState, useEffect, useRef } from "react";
import SignatureCanvas from "react-signature-canvas";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "./ui/dialog";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import { Textarea } from "./ui/textarea";
import { Loader2, Plus, Trash2, FileText, MapPin } from "lucide-react";
import api from "../lib/api";
import { toast } from "sonner";

/**
 * Dialog zum Anlegen eines neuen Lieferscheins.
 * Lädt Vorbefüllung via /delivery-notes/prefill, erlaubt Bearbeitung der
 * Positionen (Menge/Bemerkung), zwei Signatur-Pads (Lieferant/Empfänger),
 * Ort der Übergabe und Hinweis. POSTet /delivery-notes -> generiert PDF.
 */
export default function DeliveryNoteDialog({ open, onOpenChange, orderPk, onCreated }) {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [prefill, setPrefill] = useState(null);
  const [positions, setPositions] = useState([]);
  const [notes, setNotes] = useState("");
  const [signedLocation, setSignedLocation] = useState("");
  const sigSenderRef = useRef(null);
  const sigReceiverRef = useRef(null);

  useEffect(() => {
    if (!open || !orderPk) return;
    setLoading(true);
    api.get(`/orders/epirent/${orderPk}/delivery-notes/prefill`)
      .then(r => {
        setPrefill(r.data);
        setPositions((r.data.positions || []).map(p => ({ ...p })));
        setNotes("");
        setSignedLocation(r.data.delivery_address?.city || "");
      })
      .catch(e => toast.error(`Vorbefüllung fehlgeschlagen: ${e?.response?.data?.detail || e.message}`))
      .finally(() => setLoading(false));
  }, [open, orderPk]);

  const addPosition = () => {
    setPositions(p => [...p, {
      pos: String(p.length + 1), title: "", amount: 1, unit: "", remark: "",
    }]);
  };
  const removePosition = (idx) => {
    setPositions(p => p.filter((_, i) => i !== idx));
  };
  const updatePos = (idx, key, val) => {
    setPositions(p => p.map((row, i) => i === idx ? { ...row, [key]: val } : row));
  };

  const handleSubmit = async () => {
    if (positions.length === 0) {
      toast.error("Mindestens eine Position erforderlich");
      return;
    }
    const empty = positions.find(p => !p.title || String(p.title).trim() === "");
    if (empty) {
      toast.error("Alle Positionen brauchen eine Bezeichnung");
      return;
    }

    const sigSender = sigSenderRef.current && !sigSenderRef.current.isEmpty()
      ? sigSenderRef.current.toDataURL("image/png") : null;
    const sigReceiver = sigReceiverRef.current && !sigReceiverRef.current.isEmpty()
      ? sigReceiverRef.current.toDataURL("image/png") : null;

    setSaving(true);
    try {
      const body = {
        positions: positions.map(p => ({
          pos: String(p.pos || ""),
          title: String(p.title || ""),
          amount: Number(p.amount) || 0,
          unit: String(p.unit || ""),
          remark: String(p.remark || ""),
        })),
        notes_override: notes || null,
        signature_sender_b64: sigSender,
        signature_receiver_b64: sigReceiver,
        signed_at_location: signedLocation || null,
      };
      const r = await api.post(`/orders/epirent/${orderPk}/delivery-notes`, body);
      toast.success(`Lieferschein ${r.data.delivery_note_no} erstellt`);

      // Direkt PDF runterladen
      const token = localStorage.getItem("token");
      const pdfResp = await fetch(
        `${process.env.REACT_APP_BACKEND_URL}/api/orders/epirent/${orderPk}/delivery-notes/${r.data.id}/pdf`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      if (pdfResp.ok) {
        const blob = await pdfResp.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `Lieferschein_${r.data.delivery_note_no}.pdf`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
      }

      onOpenChange(false);
      onCreated && onCreated(r.data);
    } catch (e) {
      toast.error(`Lieferschein-Fehler: ${e?.response?.data?.detail || e.message}`);
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-4xl max-h-[90vh] flex flex-col p-0" data-testid="delivery-note-dialog">
        <DialogHeader className="px-5 pt-5 pb-3 border-b">
          <DialogTitle className="flex items-center gap-2 text-base">
            <FileText className="w-4 h-4 text-violet-600" />
            Lieferschein anlegen
            {prefill && <span className="text-xs text-gray-400 font-mono">Nr. {prefill.suggested_delivery_note_no}</span>}
          </DialogTitle>
        </DialogHeader>

        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4">
          {loading ? (
            <div className="py-12 text-center text-gray-400"><Loader2 className="w-6 h-6 mx-auto animate-spin" /></div>
          ) : prefill ? (
            <>
              {/* Auftrag & Empfänger */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="bg-gray-50 rounded-lg p-3 border border-gray-100">
                  <div className="text-xs text-gray-500 mb-1">Auftrag</div>
                  <div className="text-sm font-semibold text-gray-900">{prefill.order_no_fmt}</div>
                  <div className="text-xs text-gray-600 mt-0.5">{prefill.event}</div>
                  {(prefill.event_start || prefill.event_end) && (
                    <div className="text-xs text-gray-500 mt-1">Event: {prefill.event_start} – {prefill.event_end}</div>
                  )}
                </div>
                <div className="bg-gray-50 rounded-lg p-3 border border-gray-100">
                  <div className="text-xs text-gray-500 mb-1">Lieferadresse</div>
                  <div className="text-sm font-semibold text-gray-900">{prefill.delivery_address?.name}</div>
                  <div className="text-xs text-gray-700">
                    {prefill.delivery_address?.street}<br/>
                    {prefill.delivery_address?.postal_code} {prefill.delivery_address?.city}
                  </div>
                </div>
              </div>

              {/* Positionen */}
              <div className="bg-white rounded-lg border border-gray-200">
                <div className="px-3 py-2 border-b border-gray-100 flex items-center justify-between">
                  <h3 className="text-sm font-semibold text-gray-700">Positionen</h3>
                  <Button size="sm" variant="outline" onClick={addPosition} className="h-7 text-xs" data-testid="add-position-btn">
                    <Plus className="w-3 h-3 mr-1" /> Position hinzufügen
                  </Button>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-violet-50/50 text-xs text-gray-600">
                      <tr>
                        <th className="text-left px-3 py-2 w-16">Pos.</th>
                        <th className="text-left px-3 py-2">Bezeichnung</th>
                        <th className="text-right px-3 py-2 w-24">Menge</th>
                        <th className="text-left px-3 py-2 w-24">Einheit</th>
                        <th className="text-left px-3 py-2">Bemerkung</th>
                        <th className="w-8"></th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                      {positions.map((p, i) => (
                        <tr key={i} data-testid={`position-row-${i}`}>
                          <td className="px-3 py-1">
                            <Input value={p.pos} onChange={e => updatePos(i, "pos", e.target.value)} className="h-8 text-xs" data-testid={`pos-no-${i}`} />
                          </td>
                          <td className="px-3 py-1">
                            <Input value={p.title} onChange={e => updatePos(i, "title", e.target.value)} className="h-8 text-xs font-medium" data-testid={`pos-title-${i}`} />
                          </td>
                          <td className="px-3 py-1">
                            <Input type="number" min="0" step="0.5" value={p.amount} onChange={e => updatePos(i, "amount", e.target.value)} className="h-8 text-xs text-right" data-testid={`pos-amount-${i}`} />
                          </td>
                          <td className="px-3 py-1">
                            <Input value={p.unit} onChange={e => updatePos(i, "unit", e.target.value)} className="h-8 text-xs" placeholder="Stk." data-testid={`pos-unit-${i}`} />
                          </td>
                          <td className="px-3 py-1">
                            <Input value={p.remark} onChange={e => updatePos(i, "remark", e.target.value)} className="h-8 text-xs" placeholder="optional" data-testid={`pos-remark-${i}`} />
                          </td>
                          <td className="px-1">
                            <button onClick={() => removePosition(i)} className="p-1 text-gray-300 hover:text-red-500" title="Position löschen" data-testid={`pos-remove-${i}`}>
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          </td>
                        </tr>
                      ))}
                      {positions.length === 0 && (
                        <tr><td colSpan={6} className="px-3 py-6 text-center text-xs text-gray-400">Keine Positionen — klicke "Position hinzufügen"</td></tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Hinweis */}
              <div>
                <Label className="text-xs text-gray-500">Hinweis (optional)</Label>
                <Textarea
                  value={notes}
                  onChange={e => setNotes(e.target.value)}
                  placeholder={prefill.notes || "z.B. Lieferung auf Baustelle, Treffen an Tor 3..."}
                  className="mt-1 text-sm"
                  rows={2}
                  data-testid="ls-notes-input"
                />
              </div>

              {/* Ort der Unterschrift */}
              <div>
                <Label className="text-xs text-gray-500 flex items-center gap-1">
                  <MapPin className="w-3 h-3" /> Ort der Übergabe
                </Label>
                <Input
                  value={signedLocation}
                  onChange={e => setSignedLocation(e.target.value)}
                  placeholder="z.B. Andernach"
                  className="mt-1 max-w-sm text-sm"
                  data-testid="signed-location-input"
                />
              </div>

              {/* Unterschriften */}
              <div className="bg-white rounded-lg border border-gray-200 p-3">
                <h3 className="text-sm font-semibold text-gray-700 mb-3">Unterschriften</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <div className="flex items-center justify-between mb-1">
                      <Label className="text-xs text-gray-500">Lieferant</Label>
                      <button onClick={() => sigSenderRef.current?.clear()} className="text-[10px] text-gray-400 hover:text-red-500" data-testid="clear-sig-sender">Löschen</button>
                    </div>
                    <div className="border rounded-lg bg-white touch-none">
                      <SignatureCanvas ref={sigSenderRef} penColor="#1a1a2e" canvasProps={{ className: "w-full h-32", "data-testid": "sig-sender-canvas" }} />
                    </div>
                  </div>
                  <div>
                    <div className="flex items-center justify-between mb-1">
                      <Label className="text-xs text-gray-500">Empfänger</Label>
                      <button onClick={() => sigReceiverRef.current?.clear()} className="text-[10px] text-gray-400 hover:text-red-500" data-testid="clear-sig-receiver">Löschen</button>
                    </div>
                    <div className="border rounded-lg bg-white touch-none">
                      <SignatureCanvas ref={sigReceiverRef} penColor="#1a1a2e" canvasProps={{ className: "w-full h-32", "data-testid": "sig-receiver-canvas" }} />
                    </div>
                  </div>
                </div>
                <p className="text-[10px] text-gray-400 mt-2">Unterschriften sind optional. Falls nicht ausgefüllt, erscheint nur die Linie im PDF.</p>
              </div>
            </>
          ) : (
            <div className="py-8 text-center text-gray-400 text-sm">Keine Vorbefüllung verfügbar</div>
          )}
        </div>

        <DialogFooter className="px-5 py-3 border-t bg-gray-50">
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={saving} data-testid="cancel-ls-btn">Abbrechen</Button>
          <Button
            onClick={handleSubmit}
            disabled={loading || saving || !prefill}
            className="bg-violet-600 hover:bg-violet-700 text-white"
            data-testid="generate-ls-btn"
          >
            {saving ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <FileText className="w-4 h-4 mr-2" />}
            Lieferschein generieren
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
