import { useState } from "react";
import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import { Label } from "../../components/ui/label";
import { Mail, ArrowRight } from "lucide-react";

export function VerifyStep({ email, onVerify, onResend, saving }) {
  const [verifyCode, setVerifyCode] = useState("");
  return (
    <div className="bg-white border border-gray-200 rounded-xl p-6" data-testid="verify-step">
      <div className="text-center mb-6">
        <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-fuchsia-100 flex items-center justify-center"><Mail className="w-8 h-8 text-fuchsia-600" /></div>
        <h2 className="text-xl font-bold text-gray-900 mb-1">E-Mail bestätigen</h2>
        <p className="text-sm text-gray-500">Wir haben einen 6-stelligen Code an <strong>{email}</strong> gesendet.</p>
      </div>
      <div className="space-y-4">
        <div><Label className="text-gray-700 text-sm">Bestätigungscode</Label><Input type="text" maxLength={6} value={verifyCode} onChange={e => setVerifyCode(e.target.value.replace(/\D/g, "").slice(0, 6))} placeholder="000000" className="mt-1 text-center text-2xl tracking-[0.5em] font-mono" data-testid="verify-code-input" /></div>
        <Button onClick={() => onVerify(verifyCode)} disabled={saving || verifyCode.length !== 6} className="w-full bg-fuchsia-600 hover:bg-fuchsia-700 text-white" data-testid="verify-btn">
          {saving ? "Wird geprüft..." : "Bestätigen"} <ArrowRight className="w-4 h-4 ml-1" />
        </Button>
        <div className="text-center"><button onClick={onResend} className="text-sm text-fuchsia-600 hover:text-fuchsia-700 underline" data-testid="resend-code-btn">Code erneut senden</button></div>
      </div>
    </div>
  );
}
