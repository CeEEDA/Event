import { useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "./ui/dialog";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import { Send, Loader2, CheckCircle2, Mail } from "lucide-react";
import api from "../lib/api";
import { toast } from "sonner";

/**
 * Kleiner Dialog zum Versand eines Lieferscheins per E-Mail.
 *
 * Props:
 *  - open / onOpenChange
 *  - orderPk, ls: das Lieferschein-Dokument (mit `last_email_to`, `email_log`)
 *  - onSent: callback nach erfolgreichem Versand (zum List-Refresh)
 */
export default function DeliveryNoteEmailDialog({ open, onOpenChange, orderPk, ls, onSent }) {
  const [email, setEmail] = useState(ls?.last_email_to || "");
  const [sending, setSending] = useState(false);

  // Reset email when ls changes
  const lastTo = ls?.last_email_to || "";
  if (open && email === "" && lastTo) {
    setEmail(lastTo);
  }

  const sendCount = (ls?.email_log || []).length;
  const lastSent = ls?.last_email_at;

  const handleSend = async () => {
    const e = (email || "").trim();
    if (!e || !e.includes("@")) {
      toast.error("Bitte eine gültige E-Mail eingeben");
      return;
    }
    setSending(true);
    try {
      await api.post(`/orders/epirent/${orderPk}/delivery-notes/${ls.id}/email`, { to_email: e });
      toast.success(`Lieferschein ${ls.delivery_note_no} an ${e} versendet`);
      onOpenChange(false);
      onSent && onSent();
    } catch (err) {
      toast.error(`Versand fehlgeschlagen: ${err?.response?.data?.detail || err.message}`);
    } finally {
      setSending(false);
    }
  };

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
          <div>
            <Label className="text-xs text-gray-500">Empfänger E-Mail</Label>
            <Input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="kunde@firma.de"
              className="mt-1"
              autoFocus
              data-testid="ls-email-input"
              onKeyDown={(e) => e.key === "Enter" && handleSend()}
            />
          </div>

          {sendCount > 0 && (
            <div className="bg-emerald-50 border border-emerald-200 rounded-lg p-3 text-xs">
              <div className="flex items-center gap-2 text-emerald-700 font-medium mb-1">
                <CheckCircle2 className="w-4 h-4" />
                Bereits {sendCount === 1 ? "1× versendet" : `${sendCount}× versendet`}
              </div>
              {lastSent && (
                <div className="text-emerald-600">
                  Zuletzt: {new Date(lastSent).toLocaleString("de-DE")}
                  {lastTo && <> an <strong>{lastTo}</strong></>}
                </div>
              )}
              {ls?.email_log?.length > 1 && (
                <details className="mt-2">
                  <summary className="cursor-pointer text-emerald-600 hover:text-emerald-700">Versand-Historie anzeigen ({ls.email_log.length})</summary>
                  <ul className="mt-1 space-y-0.5 pl-3 text-emerald-700/80">
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
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={sending}>Abbrechen</Button>
          <Button
            onClick={handleSend}
            disabled={sending || !email}
            className="bg-violet-600 hover:bg-violet-700 text-white"
            data-testid="ls-email-send-btn"
          >
            {sending ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Send className="w-4 h-4 mr-2" />}
            {sendCount > 0 ? "Erneut senden" : "Versenden"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
