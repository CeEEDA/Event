/**
 * Password-Reset-Modal aus AdminPage.js extrahiert.
 * Erlaubt Admin/Verwaltung das Setzen eines neuen Passworts oder das
 * Generieren eines 24h-gueltigen Reset-Links (per Mail oder Copy).
 */
import { KeyRound, Link2, Mail, Copy } from "lucide-react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "../ui/dialog";
import { Input } from "../ui/input";
import { Button } from "../ui/button";

export default function PasswordResetModal({
  open,
  onOpenChange,
  target,
  newPassword,
  setNewPassword,
  resetLink,
  onSetPassword,
  onGenerateResetLink,
  onSendResetEmail,
  onCopyLink,
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="bg-white max-w-md" data-testid="password-modal">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-gray-900">
            <KeyRound className="w-5 h-5 text-fuchsia-600" />
            Passwort verwalten
          </DialogTitle>
        </DialogHeader>

        {target && (
          <div className="space-y-5">
            <div className="bg-gray-50 rounded-lg p-3">
              <p className="text-sm text-gray-500">Benutzer</p>
              <p className="font-medium text-gray-900">{target.name} ({target.email})</p>
            </div>

            {/* Set new password */}
            <div className="space-y-3">
              <h4 className="text-sm font-semibold text-gray-700">Neues Passwort setzen</h4>
              <div className="flex gap-2">
                <Input
                  type="text"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  placeholder="Neues Passwort (min. 6 Zeichen)"
                  className="border-gray-300 flex-1"
                  data-testid="admin-new-password-input"
                />
                <Button
                  onClick={onSetPassword}
                  disabled={!newPassword || newPassword.length < 6}
                  className="bg-fuchsia-600 hover:bg-fuchsia-700 text-white"
                  data-testid="admin-set-password-btn"
                >
                  Setzen
                </Button>
              </div>
            </div>

            <div className="border-t border-gray-200" />

            {/* Generate reset link */}
            <div className="space-y-3">
              <h4 className="text-sm font-semibold text-gray-700">Reset-Link erstellen</h4>
              <p className="text-xs text-gray-500">
                Erstellt einen einmaligen Link, mit dem der Benutzer sein Passwort selbst zurücksetzen kann.
              </p>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  onClick={onGenerateResetLink}
                  className="flex-1 border-gray-300"
                  data-testid="admin-generate-reset-link-btn"
                >
                  <Link2 className="w-4 h-4 mr-2" />
                  Link generieren
                </Button>
                <Button
                  onClick={onSendResetEmail}
                  className="flex-1 bg-fuchsia-600 hover:bg-fuchsia-700 text-white"
                  data-testid="admin-send-reset-email-btn"
                >
                  <Mail className="w-4 h-4 mr-2" />
                  Per E-Mail senden
                </Button>
              </div>

              {resetLink && (
                <div className="bg-fuchsia-50 border border-fuchsia-200 rounded-lg p-3 space-y-2">
                  <p className="text-xs font-medium text-fuchsia-700">Reset-Link (24h gültig):</p>
                  <div className="flex items-center gap-2">
                    <code className="text-xs text-fuchsia-600 break-all flex-1">{resetLink}</code>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8 flex-shrink-0"
                      onClick={() => onCopyLink(resetLink)}
                      data-testid="copy-reset-link-btn"
                    >
                      <Copy className="w-4 h-4" />
                    </Button>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
