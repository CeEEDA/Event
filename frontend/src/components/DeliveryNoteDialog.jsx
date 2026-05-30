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
 * Strukturiert Positionen nach Kapitel (aus EpiRent) mit darunter den Artikeln.
 * Pro Artikel: Menge editierbar. Pro Gruppe: "+ Artikel zur Gruppe".
 */
export default function DeliveryNoteDialog({ open, onOpenChange, orderPk, onCreated }) {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [prefill, setPrefill] = useState(null);
  const [groups, setGroups] = useState([]);
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
        // Deep clone groups so user-edits don't mutate prefill
        setGroups((r.data.groups || []).map(g => ({
          chapter_pk: g.chapter_pk,
          chapter_pos: g.chapter_pos,
          chapter_title: g.chapter_title,
          items: (g.items || []).map(it => ({ ...it })),
        })));
        setNotes("");
        setSignedLocation(r.data.delivery_address?.city || "");
      })
      .catch(e => toast.error(`Vorbefüllung fehlgeschlagen: ${e?.response?.data?.detail || e.message}`))
      .finally(() => setLoading(false));
  }, [open, orderPk]);

  const updateItem = (gIdx, iIdx, key, val) => {
    setGroups(gs => gs.map((g, gi) => gi !== gIdx ? g : ({
      ...g,
      items: g.items.map((it, ii) => ii !== iIdx ? it : ({ ...it, [key]: val })),
    })));
  };
  const removeItem = (gIdx, iIdx) => {
    setGroups(gs => gs.map((g, gi) => gi !== gIdx ? g : ({
      ...g,
      items: g.items.filter((_, ii) => ii !== iIdx),
    })));
  };
  const addItemToGroup = (gIdx) => {
    setGroups(gs => gs.map((g, gi) => {
      if (gi !== gIdx) return g;
      // Naechste Pos-Nr basiert auf der hoechsten Pos-Nr der Artikel (Headings ignorieren)
      const articleItems = g.items.filter(it => !it.is_heading);
      const nextPos = `${g.chapter_pos}.${articleItems.length + 1}`;
      return {
        ...g,
        items: [...g.items, { pos: nextPos, title: "", amount: 1, unit: "Stk.", remark: "", product_no: "", is_heading: false }],
      };
    }));
  };
  const addHeadingToGroup = (gIdx) => {
    const title = window.prompt("Überschrift-Text eingeben:");
    if (!title) return;
    setGroups(gs => gs.map((g, gi) => gi !== gIdx ? g : ({
      ...g,
      items: [...g.items, { pos: "", title, amount: 0, unit: "", remark: "", product_no: "", is_heading: true }],
    })));
  };
  const addNewGroup = () => {
    const title = window.prompt("Name der neuen Gruppe eingeben:");
    if (!title) return;
    const nextPos = String(groups.length + 1);
    setGroups(gs => [...gs, {
      chapter_pk: null,
      chapter_pos: nextPos,
      chapter_title: title,
      items: [],
    }]);
  };
  const removeGroup = (gIdx) => {
    const g = groups[gIdx];
    const cnt = g?.items?.filter(it => !it.is_heading).length || 0;
    const msg = cnt > 0
      ? `Gruppe "${g.chapter_title}" mit ${cnt} Artikel${cnt === 1 ? "" : "n"} wirklich löschen?`
      : `Gruppe "${g.chapter_title}" wirklich löschen?`;
    if (!window.confirm(msg)) return;
    setGroups(gs => gs.filter((_, gi) => gi !== gIdx));
  };

  const handleSubmit = async () => {
    const totalItems = groups.reduce((sum, g) => sum + g.items.length, 0);
    if (totalItems === 0) {
      toast.error("Mindestens ein Artikel erforderlich");
      return;
    }
    for (const g of groups) {
      for (const it of g.items) {
        if (it.is_heading) continue;  // Headings brauchen keine Validierung
        if (!it.title || String(it.title).trim() === "") {
          toast.error(`Alle Artikel brauchen eine Bezeichnung (Gruppe: ${g.chapter_title})`);
          return;
        }
      }
    }

    const sigSender = sigSenderRef.current && !sigSenderRef.current.isEmpty()
      ? sigSenderRef.current.toDataURL("image/png") : null;
    const sigReceiver = sigReceiverRef.current && !sigReceiverRef.current.isEmpty()
      ? sigReceiverRef.current.toDataURL("image/png") : null;

    setSaving(true);
    try {
      const body = {
        groups: groups.map(g => ({
          chapter_pk: g.chapter_pk,
          chapter_pos: g.chapter_pos,
          chapter_title: g.chapter_title,
          items: g.items.map(it => ({
            pos: String(it.pos || ""),
            title: String(it.title || ""),
            amount: Number(it.amount) || 0,
            unit: String(it.unit || ""),
            remark: String(it.remark || ""),
            product_no: String(it.product_no || ""),
            is_heading: !!it.is_heading,
          })),
        })),
        notes_override: notes || null,
        signature_sender_b64: sigSender,
        signature_receiver_b64: sigReceiver,
        signed_at_location: signedLocation || null,
      };
      const r = await api.post(`/orders/epirent/${orderPk}/delivery-notes`, body);
      toast.success(`Lieferschein ${r.data.delivery_note_no} erstellt`);

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
      <DialogContent className="max-w-5xl max-h-[92vh] flex flex-col p-0" data-testid="delivery-note-dialog">
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

              {/* Gruppen + Artikel */}
              <div className="space-y-3">
                {groups.length === 0 && (
                  <div className="text-center text-sm text-gray-400 py-6">Keine Gruppen aus EpiRent</div>
                )}
                {groups.map((g, gIdx) => {
                  const articleCount = g.items.filter(it => !it.is_heading).length;
                  const headingCount = g.items.filter(it => it.is_heading).length;
                  return (
                  <div key={(g.chapter_pk || "manual") + "-" + gIdx} className="bg-white rounded-lg border border-violet-200/60" data-testid={`group-${gIdx}`}>
                    <div className="px-3 py-2 bg-violet-50/70 border-b border-violet-200/60 flex items-center justify-between rounded-t-lg">
                      <h3 className="text-sm font-bold text-violet-800 flex items-center gap-2 flex-wrap">
                        <span className="text-xs font-mono text-violet-500">{g.chapter_pos}</span>
                        {g.chapter_title}
                        <span className="text-xs font-normal text-violet-500/80">
                          ({articleCount} Artikel{headingCount > 0 ? `, ${headingCount} Überschrift${headingCount === 1 ? "" : "en"}` : ""})
                        </span>
                      </h3>
                      <div className="flex items-center gap-1">
                        <Button size="sm" variant="outline" onClick={() => addItemToGroup(gIdx)} className="h-7 text-xs border-violet-300 text-violet-700 hover:bg-violet-100" data-testid={`add-item-${gIdx}`}>
                          <Plus className="w-3 h-3 mr-1" /> Artikel
                        </Button>
                        <Button size="sm" variant="outline" onClick={() => addHeadingToGroup(gIdx)} className="h-7 text-xs border-gray-300 text-gray-600 hover:bg-gray-50" data-testid={`add-heading-${gIdx}`}>
                          <Plus className="w-3 h-3 mr-1" /> Überschrift
                        </Button>
                        <button
                          onClick={() => removeGroup(gIdx)}
                          className="p-1.5 rounded-lg text-gray-400 hover:bg-red-50 hover:text-red-500 transition-colors ml-1"
                          title="Gesamte Gruppe inkl. Artikel löschen"
                          data-testid={`remove-group-${gIdx}`}
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </div>
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead className="bg-gray-50 text-[11px] text-gray-500 uppercase tracking-wide">
                          <tr>
                            <th className="text-left px-3 py-1.5 w-20">Pos.</th>
                            <th className="text-left px-3 py-1.5 w-24">Art-Nr.</th>
                            <th className="text-left px-3 py-1.5">Bezeichnung</th>
                            <th className="text-right px-3 py-1.5 w-20">Menge</th>
                            <th className="text-left px-3 py-1.5 w-20">Einheit</th>
                            <th className="text-left px-3 py-1.5">Bemerkung</th>
                            <th className="w-8"></th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-100">
                          {g.items.map((it, iIdx) => (
                            it.is_heading ? (
                              <tr key={iIdx} className="bg-gray-50/80" data-testid={`heading-${gIdx}-${iIdx}`}>
                                <td className="px-3 py-1 text-[10px] text-gray-400 uppercase tracking-wide italic">Überschrift</td>
                                <td className="px-3 py-1" colSpan={5}>
                                  <Input value={it.title} onChange={e => updateItem(gIdx, iIdx, "title", e.target.value)} className="h-8 text-xs italic font-medium text-gray-700 bg-transparent border-dashed" data-testid={`heading-title-${gIdx}-${iIdx}`} />
                                </td>
                                <td className="px-1">
                                  <button onClick={() => removeItem(gIdx, iIdx)} className="p-1 text-gray-300 hover:text-red-500" title="Überschrift löschen" data-testid={`heading-remove-${gIdx}-${iIdx}`}>
                                    <Trash2 className="w-3.5 h-3.5" />
                                  </button>
                                </td>
                              </tr>
                            ) : (
                              <tr key={iIdx} data-testid={`item-${gIdx}-${iIdx}`}>
                                <td className="px-3 py-1">
                                  <Input value={it.pos} onChange={e => updateItem(gIdx, iIdx, "pos", e.target.value)} className="h-8 text-xs" data-testid={`item-pos-${gIdx}-${iIdx}`} />
                                </td>
                                <td className="px-3 py-1">
                                  <Input value={it.product_no || ""} onChange={e => updateItem(gIdx, iIdx, "product_no", e.target.value)} className="h-8 text-xs text-gray-500" data-testid={`item-prodno-${gIdx}-${iIdx}`} />
                                </td>
                                <td className="px-3 py-1">
                                  <Input value={it.title} onChange={e => updateItem(gIdx, iIdx, "title", e.target.value)} className="h-8 text-xs font-medium" data-testid={`item-title-${gIdx}-${iIdx}`} />
                                </td>
                                <td className="px-3 py-1">
                                  <Input type="number" min="0" step="0.5" value={it.amount} onChange={e => updateItem(gIdx, iIdx, "amount", e.target.value)} className="h-8 text-xs text-right font-semibold" data-testid={`item-amount-${gIdx}-${iIdx}`} />
                                </td>
                                <td className="px-3 py-1">
                                  <Input value={it.unit} onChange={e => updateItem(gIdx, iIdx, "unit", e.target.value)} className="h-8 text-xs" placeholder="Stk." data-testid={`item-unit-${gIdx}-${iIdx}`} />
                                </td>
                                <td className="px-3 py-1">
                                  <Input value={it.remark} onChange={e => updateItem(gIdx, iIdx, "remark", e.target.value)} className="h-8 text-xs" placeholder="optional" data-testid={`item-remark-${gIdx}-${iIdx}`} />
                                </td>
                                <td className="px-1">
                                  <button onClick={() => removeItem(gIdx, iIdx)} className="p-1 text-gray-300 hover:text-red-500" title="Artikel löschen" data-testid={`item-remove-${gIdx}-${iIdx}`}>
                                    <Trash2 className="w-3.5 h-3.5" />
                                  </button>
                                </td>
                              </tr>
                            )
                          ))}
                          {g.items.length === 0 && (
                            <tr><td colSpan={7} className="px-3 py-4 text-center text-xs text-gray-400 italic">Keine Artikel in dieser Gruppe — "Artikel" klicken</td></tr>
                          )}
                        </tbody>
                      </table>
                    </div>
                  </div>
                  );
                })}
                {/* Neue Gruppe hinzufuegen */}
                <Button variant="outline" onClick={addNewGroup} className="w-full border-dashed border-violet-300 text-violet-700 hover:bg-violet-50" data-testid="add-group-btn">
                  <Plus className="w-4 h-4 mr-2" /> Neue Gruppe hinzufügen
                </Button>
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
