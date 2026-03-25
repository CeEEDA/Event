import { useState, useEffect, useCallback } from "react";
import { useSearchParams } from "react-router-dom";
import { Logo } from "../components/Logo";
import { toast } from "sonner";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import {
  CalendarDays, MapPin, Zap, Check, ArrowRight, ArrowLeft, UserPlus, LogIn,
  Mail, Eye, EyeOff, FileText, Download, LayoutDashboard, Plus, LogOut, KeyRound,
} from "lucide-react";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

const PASSWORD_RULES = [
  { re: /.{8,}/, label: "Mindestens 8 Zeichen" },
  { re: /[0-9]/, label: "Mindestens eine Ziffer" },
  { re: /[A-Z]/, label: "Mindestens ein Großbuchstabe" },
  { re: /[a-z]/, label: "Mindestens ein Kleinbuchstabe" },
  { re: /[^A-Za-z0-9]/, label: "Mindestens ein Sonderzeichen" },
];

function isPasswordValid(pw) {
  return PASSWORD_RULES.every(r => r.re.test(pw));
}

const api = {
  post: (path, data) => fetch(`${BACKEND_URL}/api${path}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) }).then(async r => { const d = await r.json(); if (!r.ok) throw { response: { data: d } }; return { data: d }; }),
  get: (path) => fetch(`${BACKEND_URL}/api${path}`).then(async r => { const d = await r.json(); if (!r.ok) throw { response: { data: d } }; return { data: d }; }),
};

const PAYMENT_METHODS = [
  { value: "kreditkarte", label: "Kreditkarte" },
  { value: "paypal", label: "PayPal" },
  { value: "rechnung", label: "Auf Rechnung" },
];

const STATUS_LABELS = {
  pending_payment: { text: "Zahlung ausstehend", cls: "bg-orange-100 text-orange-700" },
  ausstehend: { text: "Ausstehend", cls: "bg-amber-100 text-amber-700" },
  bestaetigt: { text: "Bestätigt", cls: "bg-blue-100 text-blue-700" },
  abgerechnet: { text: "Abgerechnet", cls: "bg-emerald-100 text-emerald-700" },
  erstellt: { text: "Erstellt", cls: "bg-gray-100 text-gray-600" },
  versendet: { text: "Versendet", cls: "bg-blue-100 text-blue-700" },
};

function PasswordInput({ value, onChange, placeholder, testId }) {
  const [visible, setVisible] = useState(false);
  return (
    <div className="relative">
      <Input type={visible ? "text" : "password"} value={value} onChange={onChange} placeholder={placeholder} className="mt-1 pr-10" data-testid={testId} />
      <button type="button" onMouseDown={e => { e.preventDefault(); setVisible(v => !v); }} className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600" tabIndex={-1}>
        {visible ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
      </button>
    </div>
  );
}

export default function SchaustellerAnmeldungPage() {
  const [searchParams] = useSearchParams();
  const preselectedEvent = searchParams.get("event");

  // Steps: auth -> verify -> setpw -> dashboard -> event -> signup -> done
  const [step, setStep] = useState("auth");
  const [authMode, setAuthMode] = useState("register");
  const [schausteller, setSchausteller] = useState(null);
  const [events, setEvents] = useState([]);
  const [selectedEvent, setSelectedEvent] = useState(null);
  const [saving, setSaving] = useState(false);
  const [myBookings, setMyBookings] = useState({ signups: [], invoices: [] });

  const [regForm, setRegForm] = useState({
    firma: "", vorname: "", name: "", strasse: "", plz: "", ort: "",
    steuernummer: "", email: "", telefon: "", rechnungs_email: "",
  });
  const [loginEmail, setLoginEmail] = useState("");
  const [loginPassword, setLoginPassword] = useState("");
  const [resetEmail, setResetEmail] = useState("");
  const [resetCode, setResetCode] = useState("");
  const [resetPassword, setResetPassword] = useState("");
  const [resetPasswordConfirm, setResetPasswordConfirm] = useState("");
  const [verifyCode, setVerifyCode] = useState("");
  const [verifyEmail, setVerifyEmail] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [newPasswordConfirm, setNewPasswordConfirm] = useState("");
  const [signupForm, setSignupForm] = useState({
    platznummer: "", fahrgeschaeft: "", connection_type: "", payment_method: "kreditkarte",
  });
  const [lastSignupId, setLastSignupId] = useState(null);
  const [depositAmounts, setDepositAmounts] = useState({});
  const [paymentChecking, setPaymentChecking] = useState(false);

  const loadBookings = useCallback(async (schId) => {
    try { const r = await api.get(`/kirmes/public/my-bookings?schausteller_id=${schId}`); setMyBookings(r.data); } catch { /* ignore */ }
  }, []);

  const loadEvents = useCallback(async () => {
    try {
      const r = await api.get("/kirmes/public/events");
      setEvents(r.data);
      if (preselectedEvent) {
        const found = r.data.find(e => e.id === preselectedEvent);
        if (found) setSelectedEvent(found);
      }
    } catch { /* ignore */ }
  }, [preselectedEvent]);

  useEffect(() => { loadEvents(); }, [loadEvents]);

  const goToDashboard = (sch) => {
    setSchausteller(sch);
    loadBookings(sch.id);
    if (preselectedEvent && selectedEvent) { setStep("signup"); }
    else { setStep("dashboard"); }
  };

  const handleRegister = async () => {
    if (!regForm.name || !regForm.email) {
      toast.error("Bitte Name und E-Mail eingeben"); return;
    }
    setSaving(true);
    try {
      await api.post("/kirmes/public/register", regForm);
      setVerifyEmail(regForm.email);
      setVerifyCode("");
      toast.success("Bestätigungscode wurde an Ihre E-Mail gesendet!");
      setStep("verify");
    } catch (err) {
      toast.error(typeof (err?.response?.data?.detail) === "string" ? err.response.data.detail : "Fehler bei der Registrierung");
    } finally { setSaving(false); }
  };

  const handleVerify = async () => {
    if (!verifyCode || verifyCode.length !== 6) { toast.error("Bitte den 6-stelligen Code eingeben"); return; }
    setSaving(true);
    try {
      const r = await api.post("/kirmes/public/verify-email", { email: verifyEmail, code: verifyCode });
      toast.success("E-Mail bestätigt! Bitte setzen Sie jetzt Ihr Passwort.");
      setSchausteller(r.data);
      setStep("setpw");
    } catch (err) {
      toast.error(typeof (err?.response?.data?.detail) === "string" ? err.response.data.detail : "Ungültiger Code");
    } finally { setSaving(false); }
  };

  const handleSetPassword = async () => {
    if (!isPasswordValid(newPassword)) { toast.error("Passwort erfüllt nicht alle Anforderungen"); return; }
    if (newPassword !== newPasswordConfirm) { toast.error("Passwörter stimmen nicht überein"); return; }
    setSaving(true);
    try {
      const r = await api.post("/kirmes/public/set-password", { email: verifyEmail, password: newPassword });
      toast.success("Passwort gesetzt!");
      goToDashboard(r.data);
    } catch (err) {
      toast.error(typeof (err?.response?.data?.detail) === "string" ? err.response.data.detail : "Fehler");
    } finally { setSaving(false); }
  };

  const handleResendCode = async () => {
    try { await api.get(`/kirmes/public/resend-code?email=${encodeURIComponent(verifyEmail)}`); toast.success("Neuer Code wurde gesendet"); }
    catch (err) { toast.error(typeof (err?.response?.data?.detail) === "string" ? err.response.data.detail : "Fehler"); }
  };

  const handleLogin = async () => {
    if (!loginEmail || !loginPassword) { toast.error("Bitte E-Mail und Passwort eingeben"); return; }
    setSaving(true);
    try {
      const r = await api.post("/kirmes/public/login", { email: loginEmail, password: loginPassword });
      toast.success(`Willkommen zurück, ${r.data.name}!`);
      goToDashboard(r.data);
    } catch (err) {
      toast.error(typeof (err?.response?.data?.detail) === "string" ? err.response.data.detail : "Fehler bei der Anmeldung");
    } finally { setSaving(false); }
  };

  const handleSignup = async () => {
    if (!signupForm.platznummer || !signupForm.fahrgeschaeft || !signupForm.connection_type) {
      toast.error("Bitte Platznummer, Fahrgeschäft und Anschluss angeben"); return;
    }
    setSaving(true);
    try {
      const r = await api.post("/kirmes/public/signup", { event_id: selectedEvent.id, schausteller_id: schausteller.id, ...signupForm });
      const signupId = r.data?.signup_id || r.data?.id;
      setLastSignupId(signupId);

      if (r.data?.payment_status === "pending_payment") {
        toast.success("Anmeldung vorgemerkt! Bitte bezahlen Sie die Kaution.");
        setStep("payment");
      } else {
        toast.success("Anmeldung erfolgreich!");
        setStep("done");
      }
    } catch (err) {
      toast.error(typeof (err?.response?.data?.detail) === "string" ? err.response.data.detail : "Fehler bei der Anmeldung");
    } finally { setSaving(false); }
  };

  const handlePayDeposit = async () => {
    if (!lastSignupId || !selectedEvent) return;
    setSaving(true);
    try {
      const r = await api.post("/payments/checkout/deposit", {
        signup_id: lastSignupId,
        event_id: selectedEvent.id,
        origin_url: window.location.origin,
      });
      if (r.data?.url) {
        window.location.href = r.data.url;
      }
    } catch (err) {
      toast.error(typeof (err?.response?.data?.detail) === "string" ? err.response.data.detail : "Fehler bei der Zahlung");
    } finally { setSaving(false); }
  };

  const pollPaymentStatus = useCallback(async (sessionId, attempts = 0) => {
    if (attempts >= 10) { setPaymentChecking(false); return; }
    try {
      const r = await api.get(`/payments/checkout/status/${sessionId}`);
      if (r.data?.payment_status === "paid") {
        toast.success("Kaution erfolgreich bezahlt!");
        setPaymentChecking(false);
        setStep("done");
        if (schausteller) loadBookings(schausteller.id);
        return;
      }
      if (r.data?.status === "expired") {
        toast.error("Zahlungssitzung abgelaufen");
        setPaymentChecking(false);
        setStep("done");
        return;
      }
    } catch { /* ignore */ }
    setTimeout(() => pollPaymentStatus(sessionId, attempts + 1), 2000);
  }, [schausteller, loadBookings]);

  // Check for Stripe return
  useEffect(() => {
    const sessionId = searchParams.get("session_id");
    const paymentResult = searchParams.get("payment");
    if (sessionId && paymentResult === "success") {
      setPaymentChecking(true);
      setStep("payment_check");
      pollPaymentStatus(sessionId);
    } else if (paymentResult === "cancelled") {
      toast.error("Zahlung abgebrochen");
    }
  }, [searchParams, pollPaymentStatus]);

  // Load deposit amounts when event is selected
  useEffect(() => {
    if (selectedEvent) {
      api.get(`/payments/deposit-info/${selectedEvent.id}`)
        .then(r => setDepositAmounts(r.data))
        .catch(() => {});
    }
  }, [selectedEvent]);

  const handleLogout = () => { setSchausteller(null); setMyBookings({ signups: [], invoices: [] }); setStep("auth"); };

  const handleDownloadInvoice = async (invoiceId) => {
    try {
      const response = await fetch(`${BACKEND_URL}/api/kirmes/public/invoice/${invoiceId}/pdf?schausteller_id=${schausteller.id}`);
      if (!response.ok) throw new Error();
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a"); a.href = url; a.download = "Rechnung.pdf"; a.click();
      window.URL.revokeObjectURL(url);
    } catch { toast.error("PDF konnte nicht heruntergeladen werden"); }
  };

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col" data-testid="schausteller-anmeldung">
      <header className="bg-white border-b border-gray-200 p-4">
        <div className="max-w-lg mx-auto flex items-center justify-between">
          <Logo size="normal" />
          <div className="flex items-center gap-3">
            {schausteller && step !== "auth" && step !== "verify" && step !== "setpw" && (
              <>
                <span className="text-xs text-gray-500 hidden sm:inline">{schausteller.name}</span>
                <button onClick={handleLogout} className="text-gray-400 hover:text-gray-600" title="Abmelden" data-testid="logout-btn"><LogOut className="w-4 h-4" /></button>
              </>
            )}
            <p className="text-xs text-gray-400">Schausteller-Portal</p>
          </div>
        </div>
      </header>

      <main className="flex-1 flex items-start justify-center p-4 pt-8">
        <div className="w-full max-w-lg">

          {/* Auth Step */}
          {step === "auth" && (
            <div className="bg-white border border-gray-200 rounded-xl p-6" data-testid="auth-step">
              <div className="text-center mb-6">
                <h1 className="text-xl font-bold text-gray-900 mb-1">Schausteller-Anmeldung</h1>
                <p className="text-sm text-gray-500">Registrieren Sie sich einmalig oder melden Sie sich an</p>
              </div>
              <div className="flex gap-2 mb-6">
                <button onClick={() => setAuthMode("register")} className={`flex-1 py-2 rounded-lg text-sm font-medium transition-colors ${authMode === "register" ? "bg-fuchsia-600 text-white" : "bg-gray-100 text-gray-600"}`} data-testid="auth-register-tab">
                  <UserPlus className="w-4 h-4 inline mr-1" /> Registrieren
                </button>
                <button onClick={() => setAuthMode("login")} className={`flex-1 py-2 rounded-lg text-sm font-medium transition-colors ${authMode === "login" ? "bg-fuchsia-600 text-white" : "bg-gray-100 text-gray-600"}`} data-testid="auth-login-tab">
                  <LogIn className="w-4 h-4 inline mr-1" /> Anmelden
                </button>
              </div>
              {authMode === "register" ? (
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
                  <Button onClick={handleRegister} disabled={saving} className="w-full bg-fuchsia-600 hover:bg-fuchsia-700 text-white mt-2" data-testid="register-btn">
                    {saving ? "Wird registriert..." : "Registrieren"} <ArrowRight className="w-4 h-4 ml-1" />
                  </Button>
                </div>
              ) : (
                <div className="space-y-4" data-testid="login-form">
                  <div><Label className="text-gray-700 text-sm">E-Mail</Label><Input type="email" value={loginEmail} onChange={e => setLoginEmail(e.target.value)} placeholder="Ihre registrierte E-Mail" className="mt-1" data-testid="login-email" /></div>
                  <div><Label className="text-gray-700 text-sm">Passwort</Label><PasswordInput value={loginPassword} onChange={e => setLoginPassword(e.target.value)} placeholder="Ihr Passwort" testId="login-password" /></div>
                  <Button onClick={handleLogin} disabled={saving} className="w-full bg-fuchsia-600 hover:bg-fuchsia-700 text-white" data-testid="login-btn">
                    {saving ? "Wird geprüft..." : "Anmelden"} <ArrowRight className="w-4 h-4 ml-1" />
                  </Button>
                  <button onClick={() => { setResetEmail(loginEmail); setStep("reset-request"); }} className="w-full text-center text-xs text-gray-400 hover:text-fuchsia-600 underline mt-1" data-testid="forgot-password-link">
                    Passwort vergessen?
                  </button>
                </div>
              )}
            </div>
          )}

          {/* Password Reset – Request Code */}
          {step === "reset-request" && (
            <div className="bg-white border border-gray-200 rounded-xl p-6" data-testid="reset-request-step">
              <div className="text-center mb-6">
                <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-amber-100 flex items-center justify-center"><KeyRound className="w-8 h-8 text-amber-600" /></div>
                <h2 className="text-xl font-bold text-gray-900 mb-1">Passwort zurücksetzen</h2>
                <p className="text-sm text-gray-500">Geben Sie Ihre E-Mail-Adresse ein. Sie erhalten einen Code zum Zurücksetzen.</p>
              </div>
              <div className="space-y-4">
                <div><Label className="text-gray-700 text-sm">E-Mail</Label><Input type="email" value={resetEmail} onChange={e => setResetEmail(e.target.value)} placeholder="Ihre registrierte E-Mail" className="mt-1" data-testid="reset-email" /></div>
                <Button onClick={async () => {
                  if (!resetEmail) { toast.error("Bitte E-Mail eingeben"); return; }
                  setSaving(true);
                  try {
                    await api.post("/kirmes/public/request-password-reset", { email: resetEmail });
                    toast.success("Code wurde gesendet!");
                    setStep("reset-confirm");
                  } catch (err) {
                    toast.error(typeof (err?.response?.data?.detail) === "string" ? err.response.data.detail : "Fehler");
                  } finally { setSaving(false); }
                }} disabled={saving} className="w-full bg-fuchsia-600 hover:bg-fuchsia-700 text-white" data-testid="reset-send-code-btn">
                  {saving ? "Wird gesendet..." : "Code senden"} <ArrowRight className="w-4 h-4 ml-1" />
                </Button>
                <button onClick={() => setStep("auth")} className="w-full text-center text-xs text-gray-400 hover:text-fuchsia-600 underline" data-testid="reset-back-btn">Zurück zur Anmeldung</button>
              </div>
            </div>
          )}

          {/* Password Reset – Confirm Code + New Password */}
          {step === "reset-confirm" && (
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
                        <Check className={`w-3 h-3 ${r.re.test(resetPassword) ? "opacity-100" : "opacity-30"}`} />
                        <span>{r.label}</span>
                      </div>
                    ))}
                  </div>
                )}
                <div><Label className="text-gray-700 text-sm">Passwort wiederholen</Label><PasswordInput value={resetPasswordConfirm} onChange={e => setResetPasswordConfirm(e.target.value)} placeholder="Passwort bestätigen" testId="reset-password-confirm" /></div>
                <Button onClick={async () => {
                  if (!resetCode || resetCode.length < 6) { toast.error("Bitte 6-stelligen Code eingeben"); return; }
                  if (!isPasswordValid(resetPassword)) { toast.error("Passwort erfüllt nicht alle Anforderungen"); return; }
                  if (resetPassword !== resetPasswordConfirm) { toast.error("Passwörter stimmen nicht überein"); return; }
                  setSaving(true);
                  try {
                    const r = await api.post("/kirmes/public/confirm-password-reset", { email: resetEmail, code: resetCode, password: resetPassword });
                    toast.success("Passwort erfolgreich geändert!");
                    goToDashboard(r.data);
                  } catch (err) {
                    toast.error(typeof (err?.response?.data?.detail) === "string" ? err.response.data.detail : "Fehler");
                  } finally { setSaving(false); }
                }} disabled={saving || !isPasswordValid(resetPassword)} className="w-full bg-fuchsia-600 hover:bg-fuchsia-700 text-white" data-testid="reset-confirm-btn">
                  {saving ? "Wird gespeichert..." : "Passwort ändern"} <ArrowRight className="w-4 h-4 ml-1" />
                </Button>
                <button onClick={() => setStep("auth")} className="w-full text-center text-xs text-gray-400 hover:text-fuchsia-600 underline" data-testid="reset-back-btn-2">Zurück zur Anmeldung</button>
              </div>
            </div>
          )}

          {/* Verify Step */}
          {step === "verify" && (
            <div className="bg-white border border-gray-200 rounded-xl p-6" data-testid="verify-step">
              <div className="text-center mb-6">
                <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-fuchsia-100 flex items-center justify-center"><Mail className="w-8 h-8 text-fuchsia-600" /></div>
                <h2 className="text-xl font-bold text-gray-900 mb-1">E-Mail bestätigen</h2>
                <p className="text-sm text-gray-500">Wir haben einen 6-stelligen Code an <strong>{verifyEmail}</strong> gesendet.</p>
              </div>
              <div className="space-y-4">
                <div><Label className="text-gray-700 text-sm">Bestätigungscode</Label><Input type="text" maxLength={6} value={verifyCode} onChange={e => setVerifyCode(e.target.value.replace(/\D/g, "").slice(0, 6))} placeholder="000000" className="mt-1 text-center text-2xl tracking-[0.5em] font-mono" data-testid="verify-code-input" /></div>
                <Button onClick={handleVerify} disabled={saving || verifyCode.length !== 6} className="w-full bg-fuchsia-600 hover:bg-fuchsia-700 text-white" data-testid="verify-btn">
                  {saving ? "Wird geprüft..." : "Bestätigen"} <ArrowRight className="w-4 h-4 ml-1" />
                </Button>
                <div className="text-center"><button onClick={handleResendCode} className="text-sm text-fuchsia-600 hover:text-fuchsia-700 underline" data-testid="resend-code-btn">Code erneut senden</button></div>
              </div>
            </div>
          )}

          {/* Set Password Step */}
          {step === "setpw" && (
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
                        <Check className={`w-3 h-3 ${r.re.test(newPassword) ? "opacity-100" : "opacity-30"}`} />
                        <span>{r.label}</span>
                      </div>
                    ))}
                  </div>
                )}
                <div><Label className="text-gray-700 text-sm">Passwort wiederholen</Label><PasswordInput value={newPasswordConfirm} onChange={e => setNewPasswordConfirm(e.target.value)} placeholder="Passwort bestätigen" testId="setpw-confirm" /></div>
                <Button onClick={handleSetPassword} disabled={saving || !isPasswordValid(newPassword)} className="w-full bg-fuchsia-600 hover:bg-fuchsia-700 text-white" data-testid="setpw-btn">
                  {saving ? "Wird gespeichert..." : "Passwort setzen"} <ArrowRight className="w-4 h-4 ml-1" />
                </Button>
              </div>
            </div>
          )}

          {/* Dashboard */}
          {step === "dashboard" && schausteller && (
            <div data-testid="dashboard-step">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h2 className="text-lg font-bold text-gray-900">Mein Bereich</h2>
                  <p className="text-sm text-gray-500">{schausteller.firma ? `${schausteller.firma} · ` : ""}{schausteller.name}</p>
                </div>
                <Button size="sm" onClick={() => { loadEvents(); setStep("event"); }} className="bg-fuchsia-600 hover:bg-fuchsia-700 text-white" data-testid="new-booking-btn">
                  <Plus className="w-4 h-4 mr-1" /> Neue Anmeldung
                </Button>
              </div>

              <div className="bg-white border border-gray-200 rounded-xl overflow-hidden mb-4">
                <div className="px-4 py-3 bg-gray-50 border-b border-gray-200 flex items-center gap-2">
                  <LayoutDashboard className="w-4 h-4 text-fuchsia-600" />
                  <span className="text-sm font-semibold text-gray-700">Meine Buchungen ({myBookings.signups.length})</span>
                </div>
                {myBookings.signups.length === 0 ? (
                  <div className="p-6 text-center text-sm text-gray-400">Noch keine Buchungen vorhanden</div>
                ) : (
                  <div className="divide-y divide-gray-100">
                    {myBookings.signups.map(s => {
                      const st = STATUS_LABELS[s.payment_status] || STATUS_LABELS.ausstehend;
                      return (
                        <div key={s.id} className="px-4 py-3" data-testid={`booking-${s.id}`}>
                          <div className="flex items-start justify-between">
                            <div className="min-w-0 flex-1">
                              <p className="text-sm font-semibold text-gray-900">{s.event?.name || "–"}</p>
                              <div className="flex flex-wrap gap-x-3 gap-y-1 mt-1 text-xs text-gray-500">
                                {s.event?.location && <span className="flex items-center gap-1"><MapPin className="w-3 h-3" />{s.event.location}</span>}
                                {s.event?.start_date && <span className="flex items-center gap-1"><CalendarDays className="w-3 h-3" />{new Date(s.event.start_date).toLocaleDateString("de-DE")} – {new Date(s.event.end_date).toLocaleDateString("de-DE")}</span>}
                              </div>
                              <div className="flex flex-wrap gap-x-3 gap-y-1 mt-1 text-xs text-gray-500">
                                <span>Platz: <strong>{s.platznummer}</strong></span>
                                <span>{s.fahrgeschaeft}</span>
                                <span className="flex items-center gap-1"><Zap className="w-3 h-3" />{s.connection_type}</span>
                              </div>
                            </div>
                            <span className={`ml-2 px-2 py-0.5 rounded text-[10px] font-medium whitespace-nowrap ${st.cls}`}>{st.text}</span>
                          </div>
                          {s.invoice_number && <div className="mt-2 text-xs text-emerald-600 font-medium">Rechnung: {s.invoice_number}</div>}
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>

              <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
                <div className="px-4 py-3 bg-gray-50 border-b border-gray-200 flex items-center gap-2">
                  <FileText className="w-4 h-4 text-emerald-600" />
                  <span className="text-sm font-semibold text-gray-700">Meine Rechnungen ({myBookings.invoices.length})</span>
                </div>
                {myBookings.invoices.length === 0 ? (
                  <div className="p-6 text-center text-sm text-gray-400">Noch keine Rechnungen vorhanden</div>
                ) : (
                  <div className="divide-y divide-gray-100">
                    {myBookings.invoices.map(inv => {
                      const ist = STATUS_LABELS[inv.status] || { text: inv.status, cls: "bg-gray-100 text-gray-600" };
                      return (
                        <div key={inv.id} className="px-4 py-3 flex items-center justify-between" data-testid={`invoice-${inv.id}`}>
                          <div className="min-w-0 flex-1">
                            <div className="flex items-center gap-2">
                              <span className="text-sm font-semibold text-gray-900 font-mono">{inv.invoice_number}</span>
                              <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${ist.cls}`}>{ist.text}</span>
                            </div>
                            <p className="text-xs text-gray-500 mt-0.5">{inv.event_name} · {inv.invoice_date}</p>
                          </div>
                          <div className="flex items-center gap-3 ml-2">
                            <span className="text-sm font-bold text-gray-900">{inv.brutto?.toFixed(2)} EUR</span>
                            <button onClick={() => handleDownloadInvoice(inv.id)} className="p-1.5 text-emerald-500 hover:text-emerald-700 transition-colors" title="PDF herunterladen" data-testid={`dl-inv-${inv.id}`}>
                              <Download className="w-4 h-4" />
                            </button>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Select Event */}
          {step === "event" && (
            <div data-testid="event-step">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-bold text-gray-900">Veranstaltung wählen</h2>
                <button onClick={() => { loadBookings(schausteller.id); setStep("dashboard"); }} className="text-sm text-fuchsia-600 hover:text-fuchsia-700 flex items-center gap-1" data-testid="back-dashboard-btn">
                  <ArrowLeft className="w-4 h-4" /> Mein Bereich
                </button>
              </div>
              {events.length === 0 ? (
                <div className="bg-white border border-gray-200 rounded-xl p-8 text-center text-gray-400">Aktuell keine Veranstaltungen verfügbar</div>
              ) : (
                <div className="space-y-3">
                  {events.map(event => (
                    <button key={event.id} onClick={() => { setSelectedEvent(event); setStep("signup"); }} className="w-full bg-white border border-gray-200 rounded-xl p-4 text-left hover:border-fuchsia-400 transition-colors" data-testid={`select-event-${event.id}`}>
                      <h3 className="font-semibold text-gray-900 mb-1">{event.name}</h3>
                      <div className="flex flex-wrap gap-3 text-xs text-gray-500">
                        {event.location && <span className="flex items-center gap-1"><MapPin className="w-3 h-3" /> {event.location}</span>}
                        <span className="flex items-center gap-1"><CalendarDays className="w-3 h-3" />{new Date(event.start_date).toLocaleDateString("de-DE")} – {new Date(event.end_date).toLocaleDateString("de-DE")}</span>
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Signup */}
          {step === "signup" && selectedEvent && (
            <div data-testid="signup-step">
              <button onClick={() => setStep("event")} className="flex items-center gap-1 text-sm text-gray-500 hover:text-fuchsia-600 mb-4" data-testid="back-events-btn">
                <ArrowLeft className="w-4 h-4" /> Zurück zur Auswahl
              </button>
              <div className="bg-white border border-gray-200 rounded-xl p-6 space-y-5">
                <div>
                  <h2 className="text-lg font-bold text-gray-900 mb-1">{selectedEvent.name}</h2>
                  <div className="flex flex-wrap gap-3 text-xs text-gray-500">
                    {selectedEvent.location && <span className="flex items-center gap-1"><MapPin className="w-3 h-3" /> {selectedEvent.location}</span>}
                    <span className="flex items-center gap-1"><CalendarDays className="w-3 h-3" />{new Date(selectedEvent.start_date).toLocaleDateString("de-DE")} – {new Date(selectedEvent.end_date).toLocaleDateString("de-DE")}</span>
                  </div>
                </div>
                <div className="border-t border-gray-100 pt-4 space-y-4">
                  <div><Label className="text-gray-700 text-sm">Platznummer *</Label><Input value={signupForm.platznummer} onChange={e => setSignupForm(f => ({ ...f, platznummer: e.target.value }))} placeholder="z.B. A12" className="mt-1" data-testid="signup-platznummer" /></div>
                  <div><Label className="text-gray-700 text-sm">Fahrgeschäft / Betrieb *</Label><Input value={signupForm.fahrgeschaeft} onChange={e => setSignupForm(f => ({ ...f, fahrgeschaeft: e.target.value }))} placeholder="z.B. Achterbahn, Autoscooter, Imbissbude" className="mt-1" data-testid="signup-fahrgeschaeft" /></div>
                  <div>
                    <Label className="text-gray-700 text-sm">Stromanschluss *</Label>
                    <div className="grid grid-cols-3 gap-2 mt-1">
                      {(selectedEvent.prices || []).map(p => (
                        <button key={p.connection_type} onClick={() => setSignupForm(f => ({ ...f, connection_type: p.connection_type }))}
                          className={`p-3 rounded-lg border text-center transition-colors ${signupForm.connection_type === p.connection_type ? "border-fuchsia-500 bg-fuchsia-50 text-fuchsia-700" : "border-gray-200 text-gray-600 hover:border-gray-300"}`}
                          data-testid={`conn-${p.connection_type}`}>
                          <Zap className="w-4 h-4 mx-auto mb-1" />
                          <span className="text-xs font-medium block">{p.connection_type}</span>
                          <span className="text-[10px] text-gray-400 block">{p.price.toFixed(2)} EUR</span>
                        </button>
                      ))}
                    </div>
                  </div>
                  <div>
                    <Label className="text-gray-700 text-sm">Zahlungsmittel</Label>
                    <select value={signupForm.payment_method} onChange={e => setSignupForm(f => ({ ...f, payment_method: e.target.value }))} className="w-full mt-1 px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:border-fuchsia-500 bg-white" data-testid="signup-payment">
                      {PAYMENT_METHODS.filter(m => m.value !== "rechnung" || schausteller?.kauf_auf_rechnung).map(m => <option key={m.value} value={m.value}>{m.label}</option>)}
                    </select>
                  </div>
                  {signupForm.connection_type && (() => {
                    const p = (selectedEvent.prices || []).find(pr => pr.connection_type === signupForm.connection_type);
                    const depositAmt = depositAmounts[signupForm.connection_type];
                    return (
                      <div className="space-y-2">
                        {p && (
                          <div className="bg-fuchsia-50 border border-fuchsia-200 rounded-lg p-4">
                            <div className="flex justify-between items-center">
                              <span className="text-sm text-fuchsia-700 font-medium">Anschlussgebühr</span>
                              <span className="text-lg font-bold text-fuchsia-800">{p.price.toFixed(2)} EUR</span>
                            </div>
                          </div>
                        )}
                        {depositAmt > 0 && (
                          <div className="bg-amber-50 border border-amber-200 rounded-lg p-4">
                            <div className="flex justify-between items-center">
                              <span className="text-sm text-amber-700 font-medium">Kaution ({signupForm.connection_type})</span>
                              <span className="text-lg font-bold text-amber-800">{depositAmt.toFixed(2)} EUR</span>
                            </div>
                            <p className="text-[10px] text-amber-600 mt-1">Wird nach der Anmeldung per Kreditkarte fällig</p>
                          </div>
                        )}
                      </div>
                    );
                  })()}
                </div>
                <Button onClick={handleSignup} disabled={saving} className="w-full bg-fuchsia-600 hover:bg-fuchsia-700 text-white" data-testid="submit-signup-btn">
                  {saving ? "Wird angemeldet..." : "Verbindlich anmelden"} <ArrowRight className="w-4 h-4 ml-1" />
                </Button>
              </div>
            </div>
          )}

          {/* Payment – Kaution bezahlen */}
          {step === "payment" && (
            <div className="bg-white border border-gray-200 rounded-xl p-8 text-center" data-testid="payment-step">
              <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-amber-100 flex items-center justify-center">
                <Zap className="w-8 h-8 text-amber-600" />
              </div>
              <h2 className="text-xl font-bold text-gray-900 mb-2">Kaution bezahlen</h2>
              <p className="text-sm text-gray-500 mb-4">
                Ihre Anmeldung für <strong>{selectedEvent?.name}</strong> wurde vorgemerkt. Die Buchung wird erst nach Zahlungseingang bestätigt.
              </p>
              <div className="bg-gray-50 rounded-lg p-4 text-left text-sm space-y-1 mb-4">
                <p><span className="text-gray-500">Platz:</span> <strong>{signupForm.platznummer}</strong></p>
                <p><span className="text-gray-500">Fahrgeschäft:</span> <strong>{signupForm.fahrgeschaeft}</strong></p>
                <p><span className="text-gray-500">Anschluss:</span> <strong>{signupForm.connection_type}</strong></p>
              </div>
              <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 mb-6">
                <div className="flex justify-between items-center">
                  <span className="text-sm text-amber-700 font-medium">Kaution</span>
                  <span className="text-2xl font-bold text-amber-800">{(depositAmounts[signupForm.connection_type] || 0).toFixed(2)} EUR</span>
                </div>
                <p className="text-[10px] text-amber-600 mt-1">Wird nach der Veranstaltung erstattet</p>
              </div>
              <Button onClick={handlePayDeposit} disabled={saving} className="w-full bg-fuchsia-600 hover:bg-fuchsia-700 text-white mb-3" data-testid="pay-deposit-btn">
                {saving ? "Weiterleitung..." : "Jetzt bezahlen"} <ArrowRight className="w-4 h-4 ml-1" />
              </Button>
              <button onClick={() => { loadBookings(schausteller.id); setStep("dashboard"); setSignupForm({ platznummer: "", fahrgeschaeft: "", connection_type: "", payment_method: "kreditkarte" }); }} className="text-xs text-gray-400 hover:text-gray-600 underline" data-testid="skip-payment-btn">
                Später bezahlen (Buchung bleibt unbestätigt)
              </button>
            </div>
          )}

          {/* Payment Check – polling */}
          {step === "payment_check" && (
            <div className="bg-white border border-gray-200 rounded-xl p-8 text-center" data-testid="payment-check-step">
              <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-blue-100 flex items-center justify-center animate-pulse">
                <Check className="w-8 h-8 text-blue-600" />
              </div>
              <h2 className="text-xl font-bold text-gray-900 mb-2">Zahlung wird geprüft...</h2>
              <p className="text-sm text-gray-500 mb-4">Bitte warten Sie, während wir Ihre Zahlung bestätigen.</p>
              {paymentChecking && (
                <div className="flex items-center justify-center gap-2 text-sm text-blue-600">
                  <svg className="animate-spin w-4 h-4" viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" className="opacity-25"/><path d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" fill="currentColor"/></svg>
                  Prüfe Zahlungsstatus...
                </div>
              )}
            </div>
          )}

          {/* Done */}
          {step === "done" && (
            <div className="bg-white border border-gray-200 rounded-xl p-8 text-center" data-testid="done-step">
              <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-emerald-100 flex items-center justify-center"><Check className="w-8 h-8 text-emerald-600" /></div>
              <h2 className="text-xl font-bold text-gray-900 mb-2">Anmeldung erfolgreich!</h2>
              <p className="text-sm text-gray-500 mb-4">Sie wurden für <strong>{selectedEvent?.name}</strong> angemeldet. Sie erhalten eine Bestätigung per E-Mail.</p>
              <div className="bg-gray-50 rounded-lg p-4 text-left text-sm space-y-1 mb-6">
                <p><span className="text-gray-500">Platz:</span> <strong>{signupForm.platznummer}</strong></p>
                <p><span className="text-gray-500">Fahrgeschäft:</span> <strong>{signupForm.fahrgeschaeft}</strong></p>
                <p><span className="text-gray-500">Anschluss:</span> <strong>{signupForm.connection_type}</strong></p>
              </div>
              <div className="flex flex-col gap-3">
                <Button onClick={() => { setSignupForm({ platznummer: "", fahrgeschaeft: "", connection_type: "", payment_method: "kreditkarte" }); setStep("signup"); }} variant="outline" className="border-fuchsia-200 text-fuchsia-600 hover:bg-fuchsia-50" data-testid="another-signup-btn">
                  <Plus className="w-4 h-4 mr-1" /> Weiteren Stand anmelden
                </Button>
                <Button onClick={() => { loadBookings(schausteller.id); setStep("dashboard"); setSignupForm({ platznummer: "", fahrgeschaeft: "", connection_type: "", payment_method: "kreditkarte" }); }} className="bg-fuchsia-600 hover:bg-fuchsia-700 text-white" data-testid="to-dashboard-btn">
                  <LayoutDashboard className="w-4 h-4 mr-1" /> Zu meinem Bereich
                </Button>
              </div>
            </div>
          )}
        </div>
      </main>

      <footer className="bg-white border-t border-gray-200 p-4 text-center text-sm text-gray-500">
        &copy; {new Date().getFullYear()} Eventenergie Deutschland GmbH & Co. KG
      </footer>
    </div>
  );
}
