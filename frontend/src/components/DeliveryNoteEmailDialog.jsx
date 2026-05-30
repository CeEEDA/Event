import { useState, useEffect } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "./ui/dialog";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import { Send, Loader2, CheckCircle2, Mail, FileText } from "lucide-react";
import api from "../lib/api";
import { toast } from "sonner";

/**
 * Lieferschein per E-Mail versenden.
 *
 * Layout:
 *  - Oben: Empfohlene Kunden-E-Mail(s) aus EpiRent als 1-Klick-Buttons.
 *  - Darunter: Manueller Eingabefeld + Versenden-Button (frei waehlbare Adresse).
 *  - Falls bereits versendet: Versandhistorie als ausklappbare details.
 */
export default function DeliveryNoteEmailDialog({ open, onOpenChange, orderPk, ls, onSent }) {
  const [manualEmail, setManualEmail] = useState("");
  const [sending, setSending] = useState(false);
  const [emails, setEmails] = useState({ primary: "", invoice: "", all: [], customer_name: "" });
  const [loadingEmails, setLoadingEmails] = useState(false);

  useEffect(() => {
    if (!open || !orderPk) return;
    setLoadingEmails(true);
    api.get(`/orders/epirent/${orderPk}/customer-emails`)
      .then(r => setEmails(r.data || { primary: "", invoice: "", all: [] }))
      .catch(e => console.debug("customer-emails fetch failed", e))
      .finally(() => setLoadingEmails(false));
    setManualEmail(ls?.last_email_to || "");
  }, [open, orderPk, ls?.last_email_to]);

  const sendCount = (ls?.email_log || []).length;
  const lastSent = ls?.last_email_at;
  const lastTo = ls?.last_email_to || "";

  const doSend = async (to) => {
    const target = (to || "").trim();
    if (!target || !target.includes("@")) {
      toast.error("Bitte eine gültige E-Mail eingeben");
      return;
    }
    setSending(true);
    try {
      await api.post(`/orders/epirent/${orderPk}/delivery-notes/${ls.id}/email`, { to_email: target });
      toast.success(`Lieferschein ${ls.delivery_note_no} an ${target} versendet`);
      onOpenChange(false);
      onSent && onSent();
    } catch (err) {
      toast.error(`Versand fehlgeschlagen: ${err?.response?.data?.detail || err.message}`);
    } finally {
      setSending(false);
    }
  };

  const quickEmails = [];
  if (emails.primary) {
    quickEmails.push({ label: "Kunde", email: emails.primary, primary: true });
  }
  if (emails.invoice && emails.invoice !== emails.primary) {
    quickEmails.push({ label: "Rechnung", email: emails.invoice, primary: false });
  }
  // Letzter Versand auch als Quick-Action, falls anders als die anderen
  if (lastTo && !quickEmails.find(q => q.email === lastTo)) {
    quickEmails.push({ label: "Zuletzt verwendet", email: lastTo, primary: false });
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md" data-testid="ls-email-dialog">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-base">
            <Mail className="w-4 h-4 text-violet-600" />
            Lieferschein per E-Mail senden
            <span className="text-xs text-gray-400 font-mono ml-auto">{ls?.delivery_note_no}</span>
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-3 py-1">
          {/* Quick-Send-Buttons fuer Kunden-Mails */}
          {loadingEmails ? (
            <div className="py-3 text-center text-xs text-gray-400">
              <Loader2 className="w-4 h-4 inline animate-spin mr-1" /> Kunden-E-Mail wird geladen...
            </div>
          ) : quickEmails.length > 0 ? (
            <div>
              <Label className="text-xs text-gray-500">Empfohlen aus EpiRent</Label>
              <div className="space-y-1.5 mt-1">
                {quickEmails.map((q, i) => (
                  <div key={i} className="flex items-center gap-2 bg-violet-50/60 border border-violet-200/70 rounded-lg px-3 py-2" data-testid={`quick-email-row-${i}`}>
                    <div className="flex-1 min-w-0">
                      <div className="text-[10px] uppercase tracking-wide text-violet-500 font-semibold">{q.label}</div>
                      <div className="text-sm text-gray-800 truncate">{q.email}</div>
                    </div>
                    <Button
                      size="sm"
                      onClick={() => doSend(q.email)}
                      disabled={sending}
                      className="bg-violet-600 hover:bg-violet-700 text-white h-8 text-xs shrink-0"
                      data-testid={`quick-send-${i}`}
                    >
                      {sending ? <Loader2 className="w-3 h-3 animate-spin" /> : <Send className="w-3 h-3 mr-1" />}
                      Senden
                    </Button>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div className="bg-amber-50 border border-amber-200 text-amber-700 text-xs rounded-lg px-3 py-2 flex items-start gap-2">
              <FileText className="w-3.5 h-3.5 mt-0.5 shrink-0" />
              <span>Keine Kunden-E-Mail in EpiRent hinterlegt. Bitte manuell eingeben.</span>
            </div>
          )}

          {/* Manuelle Eingabe */}
          <div className="pt-2 border-t">
            <Label className="text-xs text-gray-500">Andere E-Mail-Adresse</Label>
            <div className="flex gap-2 mt-1">
              <Input
                type="email"
                value={manualEmail}
                onChange={(e) => setManualEmail(e.target.value)}
                placeholder="manuelle.adresse@kunde.de"
                className="text-sm"
                data-testid="ls-email-input"
                onKeyDown={(e) => e.key === "Enter" && doSend(manualEmail)}
              />
              <Button
                size="sm"
                onClick={() => doSend(manualEmail)}
                disabled={sending || !manualEmail}
                variant="outline"
                className="border-violet-300 text-violet-700 hover:bg-violet-50 shrink-0"
                data-testid="ls-email-send-manual-btn"
              >
                {sending ? <Loader2 className="w-3 h-3 animate-spin" /> : <Send className="w-3 h-3 mr-1" />}
                Senden
              </Button>
            </div>
          </div>

          {/* Versand-Historie */}
          {sendCount > 0 && (
            <div className="bg-emerald-50 border border-emerald-200 rounded-lg p-2.5 text-xs">
              <div className="flex items-center gap-2 text-emerald-700 font-medium">
                <CheckCircle2 className="w-3.5 h-3.5" />
                Bereits {sendCount === 1 ? "1× versendet" : `${sendCount}× versendet`}
                {lastSent && <span className="text-emerald-600/80 font-normal ml-auto">{new Date(lastSent).toLocaleDateString("de-DE")}</span>}
              </div>
              {ls?.email_log?.length > 0 && (
                <details className="mt-1">
                  <summary className="cursor-pointer text-emerald-600 hover:text-emerald-700 text-[11px]">Versand-Historie anzeigen</summary>
                  <ul className="mt-1 space-y-0.5 pl-3 text-emerald-700/80 text-[11px]">
                    {ls.email_log.slice().reverse().map((e, i) => (
                      <li key={i}>{new Date(e.sent_at).toLocaleString("de-DE")} → {e.to}</li>
                    ))}
                  </ul>
                </details>
              )}
            </div>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={sending}>Schließen</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
