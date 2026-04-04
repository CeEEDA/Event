import { useState } from "react";
import { toast } from "sonner";
import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import { Label } from "../../components/ui/label";
import { LogIn, UserPlus, ArrowRight } from "lucide-react";
import { PasswordInput, api } from "./constants";

export function AuthStep({ onLogin, onRegister, onForgotPassword, saving }) {
  const [authMode, setAuthMode] = useState("login");
  const [loginEmail, setLoginEmail] = useState("");
  const [loginPassword, setLoginPassword] = useState("");
  const [regForm, setRegForm] = useState({
    firma: "", vorname: "", name: "", strasse: "", plz: "", ort: "",
    steuernummer: "", email: "", telefon: "", rechnungs_email: "",
  });

  return (
    <div className="bg-white border border-gray-200 rounded-xl p-6" data-testid="auth-step">
      <div className="text-center mb-6">
        <h1 className="text-xl font-bold text-gray-900 mb-1">Schausteller-Anmeldung</h1>
        <p className="text-sm text-gray-500">Registrieren Sie sich einmalig oder melden Sie sich an</p>
      </div>
      <div className="flex gap-2 mb-6">
        <button onClick={() => setAuthMode("login")} className={`flex-1 py-2 rounded-lg text-sm font-medium transition-colors ${authMode === "login" ? "bg-fuchsia-600 text-white" : "bg-gray-100 text-gray-600"}`} data-testid="auth-login-tab">
          <LogIn className="w-4 h-4 inline mr-1" /> Anmelden
        </button>
        <button onClick={() => setAuthMode("register")} className={`flex-1 py-2 rounded-lg text-sm font-medium transition-colors ${authMode === "register" ? "bg-fuchsia-600 text-white" : "bg-gray-100 text-gray-600"}`} data-testid="auth-register-tab">
          <UserPlus className="w-4 h-4 inline mr-1" /> Registrieren
        </button>
      </div>
      {authMode === "login" ? (
        <div className="space-y-4" data-testid="login-form">
          <div><Label className="text-gray-700 text-sm">E-Mail</Label><Input type="email" value={loginEmail} onChange={e => setLoginEmail(e.target.value)} placeholder="Ihre registrierte E-Mail" className="mt-1" data-testid="login-email" /></div>
          <div><Label className="text-gray-700 text-sm">Passwort</Label><PasswordInput value={loginPassword} onChange={e => setLoginPassword(e.target.value)} placeholder="Ihr Passwort" testId="login-password" /></div>
          <Button onClick={() => onLogin(loginEmail, loginPassword)} disabled={saving} className="w-full bg-fuchsia-600 hover:bg-fuchsia-700 text-white" data-testid="login-btn">
            {saving ? "Wird geprüft..." : "Anmelden"} <ArrowRight className="w-4 h-4 ml-1" />
          </Button>
          <button onClick={() => onForgotPassword(loginEmail)} className="w-full text-center text-xs text-gray-400 hover:text-fuchsia-600 underline mt-1" data-testid="forgot-password-link">
            Passwort vergessen?
          </button>
        </div>
      ) : (
        <div className="space-y-3" data-testid="register-form">
          <div className="grid grid-cols-2 gap-3">
            <div><Label className="text-gray-700 text-sm">Vorname</Label><Input value={regForm.vorname} onChange={e => setRegForm(f => ({ ...f, vorname: e.target.value }))} className="mt-1" data-testid="reg-vorname" /></div>
            <div><Label className="text-gray-700 text-sm">Name *</Label><Input value={regForm.name} onChange={e => setRegForm(f => ({ ...f, name: e.target.value }))} className="mt-1" data-testid="reg-name" /></div>
          </div>
          <div><Label className="text-gray-700 text-sm">Firma</Label><Input value={regForm.firma} onChange={e => setRegForm(f => ({ ...f, firma: e.target.value }))} className="mt-1" data-testid="reg-firma" /></div>
          <div><Label className="text-gray-700 text-sm">Straße</Label><Input value={regForm.strasse} onChange={e => setRegForm(f => ({ ...f, strasse: e.target.value }))} className="mt-1" data-testid="reg-strasse" /></div>
          <div className="grid grid-cols-3 gap-3">
            <div><Label className="text-gray-700 text-sm">PLZ</Label><Input value={regForm.plz} onChange={e => setRegForm(f => ({ ...f, plz: e.target.value }))} className="mt-1" data-testid="reg-plz" /></div>
            <div className="col-span-2"><Label className="text-gray-700 text-sm">Ort</Label><Input value={regForm.ort} onChange={e => setRegForm(f => ({ ...f, ort: e.target.value }))} className="mt-1" data-testid="reg-ort" /></div>
          </div>
          <div><Label className="text-gray-700 text-sm">Steuernummer</Label><Input value={regForm.steuernummer} onChange={e => setRegForm(f => ({ ...f, steuernummer: e.target.value }))} className="mt-1" data-testid="reg-steuernummer" /></div>
          <div><Label className="text-gray-700 text-sm">E-Mail *</Label><Input type="email" value={regForm.email} onChange={e => setRegForm(f => ({ ...f, email: e.target.value }))} className="mt-1" data-testid="reg-email" /></div>
          <div><Label className="text-gray-700 text-sm">Telefon</Label><Input value={regForm.telefon} onChange={e => setRegForm(f => ({ ...f, telefon: e.target.value }))} className="mt-1" data-testid="reg-telefon" /></div>
          <div><Label className="text-gray-700 text-sm">Rechnungs-E-Mail</Label><Input type="email" value={regForm.rechnungs_email} onChange={e => setRegForm(f => ({ ...f, rechnungs_email: e.target.value }))} placeholder="Falls abweichend von E-Mail" className="mt-1" data-testid="reg-rechnungs-email" /></div>
          <Button onClick={() => onRegister(regForm)} disabled={saving} className="w-full bg-fuchsia-600 hover:bg-fuchsia-700 text-white mt-2" data-testid="register-btn">
            {saving ? "Wird registriert..." : "Registrieren"} <ArrowRight className="w-4 h-4 ml-1" />
          </Button>
        </div>
      )}
    </div>
  );
}
