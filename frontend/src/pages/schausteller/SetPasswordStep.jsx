import { useState } from "react";
import { Button } from "../../components/ui/button";
import { Label } from "../../components/ui/label";
import { ArrowRight, KeyRound, Check } from "lucide-react";
import { PasswordInput, PASSWORD_RULES, isPasswordValid } from "./constants";

export function SetPasswordStep({ onSetPassword, saving }) {
  const [newPassword, setNewPassword] = useState("");
  const [newPasswordConfirm, setNewPasswordConfirm] = useState("");
  return (
    <div className="bg-white border border-gray-200 rounded-xl p-6" data-testid="setpw-step">
      <div className="text-center mb-6">
        <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-fuchsia-100 flex items-center justify-center"><KeyRound className="w-8 h-8 text-fuchsia-600" /></div>
        <h2 className="text-xl font-bold text-gray-900 mb-1">Passwort festlegen</h2>
        <p className="text-sm text-gray-500">Legen Sie ein sicheres Passwort für Ihr Konto fest.</p>
      </div>
      <div className="space-y-4">
        <div><Label className="text-gray-700 text-sm">Neues Passwort</Label><PasswordInput value={newPassword} onChange={e => setNewPassword(e.target.value)} placeholder="Min. 8 Zeichen, Groß-/Kleinbuchstaben, Ziffer, Sonderzeichen" testId="setpw-password" /></div>
        {newPassword && (
          <div className="space-y-1" data-testid="password-rules">
            {PASSWORD_RULES.map((r, i) => (
              <div key={i} className={`flex items-center gap-2 text-xs ${r.re.test(newPassword) ? "text-emerald-600" : "text-gray-400"}`}>
                <Check className={`w-3 h-3 ${r.re.test(newPassword) ? "opacity-100" : "opacity-30"}`} /><span>{r.label}</span>
              </div>
            ))}
          </div>
        )}
        <div><Label className="text-gray-700 text-sm">Passwort wiederholen</Label><PasswordInput value={newPasswordConfirm} onChange={e => setNewPasswordConfirm(e.target.value)} placeholder="Passwort bestätigen" testId="setpw-confirm" /></div>
        <Button onClick={() => onSetPassword(newPassword, newPasswordConfirm)} disabled={saving || !isPasswordValid(newPassword)} className="w-full bg-fuchsia-600 hover:bg-fuchsia-700 text-white" data-testid="setpw-btn">
          {saving ? "Wird gespeichert..." : "Passwort setzen"} <ArrowRight className="w-4 h-4 ml-1" />
        </Button>
      </div>
    </div>
  );
}
