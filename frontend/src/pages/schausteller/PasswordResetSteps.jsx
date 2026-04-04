import { useState } from "react";
import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import { Label } from "../../components/ui/label";
import { ArrowRight, KeyRound, Check } from "lucide-react";
import { PasswordInput, PASSWORD_RULES, isPasswordValid } from "./constants";

export function ResetRequestStep({ onSendCode, onBack, saving, initialEmail }) {
  const [resetEmail, setResetEmail] = useState(initialEmail || "");
  return (
    <div className="bg-white border border-gray-200 rounded-xl p-6" data-testid="reset-request-step">
      <div className="text-center mb-6">
        <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-amber-100 flex items-center justify-center"><KeyRound className="w-8 h-8 text-amber-600" /></div>
        <h2 className="text-xl font-bold text-gray-900 mb-1">Passwort zurücksetzen</h2>
        <p className="text-sm text-gray-500">Geben Sie Ihre E-Mail-Adresse ein. Sie erhalten einen Code zum Zurücksetzen.</p>
      </div>
      <div className="space-y-4">
        <div><Label className="text-gray-700 text-sm">E-Mail</Label><Input type="email" value={resetEmail} onChange={e => setResetEmail(e.target.value)} placeholder="Ihre registrierte E-Mail" className="mt-1" data-testid="reset-email" /></div>
        <Button onClick={() => onSendCode(resetEmail)} disabled={saving} className="w-full bg-fuchsia-600 hover:bg-fuchsia-700 text-white" data-testid="reset-send-code-btn">
          {saving ? "Wird gesendet..." : "Code senden"} <ArrowRight className="w-4 h-4 ml-1" />
        </Button>
        <button onClick={onBack} className="w-full text-center text-xs text-gray-400 hover:text-fuchsia-600 underline" data-testid="reset-back-btn">Zurück zur Anmeldung</button>
      </div>
    </div>
  );
}

export function ResetConfirmStep({ email, onConfirm, onBack, saving }) {
  const [resetCode, setResetCode] = useState("");
  const [resetPassword, setResetPassword] = useState("");
  const [resetPasswordConfirm, setResetPasswordConfirm] = useState("");
  return (
    <div className="bg-white border border-gray-200 rounded-xl p-6" data-testid="reset-confirm-step">
      <div className="text-center mb-6">
        <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-amber-100 flex items-center justify-center"><KeyRound className="w-8 h-8 text-amber-600" /></div>
        <h2 className="text-xl font-bold text-gray-900 mb-1">Neues Passwort festlegen</h2>
        <p className="text-sm text-gray-500">Geben Sie den Code aus Ihrer E-Mail und ein neues Passwort ein.</p>
      </div>
      <div className="space-y-4">
        <div><Label className="text-gray-700 text-sm">Code</Label><Input value={resetCode} onChange={e => setResetCode(e.target.value)} placeholder="6-stelliger Code" maxLength={6} className="mt-1 font-mono tracking-widest text-center text-lg" data-testid="reset-code" /></div>
        <div><Label className="text-gray-700 text-sm">Neues Passwort</Label><PasswordInput value={resetPassword} onChange={e => setResetPassword(e.target.value)} placeholder="Min. 8 Zeichen" testId="reset-password" /></div>
        {resetPassword && (
          <div className="space-y-1" data-testid="reset-password-rules">
            {PASSWORD_RULES.map((r, i) => (
              <div key={i} className={`flex items-center gap-2 text-xs ${r.re.test(resetPassword) ? "text-emerald-600" : "text-gray-400"}`}>
                <Check className={`w-3 h-3 ${r.re.test(resetPassword) ? "opacity-100" : "opacity-30"}`} /><span>{r.label}</span>
              </div>
            ))}
          </div>
        )}
        <div><Label className="text-gray-700 text-sm">Passwort wiederholen</Label><PasswordInput value={resetPasswordConfirm} onChange={e => setResetPasswordConfirm(e.target.value)} placeholder="Passwort bestätigen" testId="reset-password-confirm" /></div>
        <Button onClick={() => onConfirm(email, resetCode, resetPassword, resetPasswordConfirm)} disabled={saving || !isPasswordValid(resetPassword)} className="w-full bg-fuchsia-600 hover:bg-fuchsia-700 text-white" data-testid="reset-confirm-btn">
          {saving ? "Wird gespeichert..." : "Passwort ändern"} <ArrowRight className="w-4 h-4 ml-1" />
        </Button>
        <button onClick={onBack} className="w-full text-center text-xs text-gray-400 hover:text-fuchsia-600 underline" data-testid="reset-back-btn-2">Zurück zur Anmeldung</button>
      </div>
    </div>
  );
}
