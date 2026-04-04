import { useState, useEffect, useCallback } from "react";
import { useSearchParams } from "react-router-dom";
import { Logo } from "../components/Logo";
import { toast } from "sonner";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import {
  CalendarDays, MapPin, Zap, Check, ArrowRight, ArrowLeft, UserPlus, LogIn,
  Mail, Eye, EyeOff, FileText, Download, LayoutDashboard, Plus, LogOut, KeyRound, X, Home,
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
  const verifiedParam = searchParams.get("verified");
  const verifiedEmail = searchParams.get("email");

  // Steps: auth -> verify -> setpw -> dashboard -> event -> signup -> done
  const [step, setStep] = useState("auth");
  const [authMode, setAuthMode] = useState("login");
  const [showImpressum, setShowImpressum] = useState(false);
  const [showDatenschutz, setShowDatenschutz] = useState(false);
  const [agbAccepted, setAgbAccepted] = useState(false);
  const [showAgb, setShowAgb] = useState(false);
  const [schausteller, setSchausteller] = useState(null);
  const [events, setEvents] = useState([]);
  const [selectedEvent, setSelectedEvent] = useState(null);
  const [saving, setSaving] = useState(false);
  const [myBookings, setMyBookings] = useState({ signups: [], invoices: [] });
  const [lastdiagramme, setLastdiagramme] = useState({ available: [], purchased: [] });
  const [ldPurchasing, setLdPurchasing] = useState(null);
  const [ldDownloading, setLdDownloading] = useState(null);

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
  const [additionalSignups, setAdditionalSignups] = useState([]);
  const [lastSignupId, setLastSignupId] = useState(null);
  const [depositAmounts, setDepositAmounts] = useState({});
  const [paymentChecking, setPaymentChecking] = useState(false);

  const loadBookings = useCallback(async (schId) => {
    try { const r = await api.get(`/kirmes/public/my-bookings?schausteller_id=${schId}`); setMyBookings(r.data); } catch { /* ignore */ }
  }, []);

  const loadLastdiagramme = useCallback(async (schId) => {
    try { const r = await api.get(`/kirmes/public/lastdiagramm/available?schausteller_id=${schId}`); setLastdiagramme(r.data); } catch { /* ignore */ }
  }, []);

  const purchaseLastdiagramm = async (signupId) => {
    if (!schausteller) return;
    setLdPurchasing(signupId);
    try {
      const payMethod = schausteller.kauf_auf_rechnung ? "rechnung" : "kreditkarte";
      const r = await api.post("/kirmes/public/lastdiagramm/purchase", {
        schausteller_id: schausteller.id,
        signup_id: signupId,
        payment_method: payMethod,
      });
      toast.success(`Lastdiagramm bestellt! Rechnung: ${r.data.invoice?.invoice_number}`);
      loadLastdiagramme(schausteller.id);
      loadBookings(schausteller.id);
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Fehler beim Bestellen");
    } finally {
      setLdPurchasing(null);
    }
  };

  const downloadLastdiagramm = async (orderId) => {
    if (!schausteller) return;
    setLdDownloading(orderId);
    try {
      const resp = await fetch(`${BACKEND_URL}/api/kirmes/public/lastdiagramm/${orderId}/pdf?schausteller_id=${schausteller.id}`);
      if (!resp.ok) { const d = await resp.json(); throw { response: { data: d } }; }
      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "Lastdiagramm.pdf";
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Fehler beim Download");
    } finally {
      setLdDownloading(null);
    }
  };

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

  // Auto-verify: wenn User über E-Mail-Link bestätigt hat → direkt zum Passwort-Schritt
  useEffect(() => {
    if (verifiedParam === "1" && verifiedEmail) {
      setVerifyEmail(verifiedEmail);
      toast.success("E-Mail erfolgreich bestätigt!");
      // Prüfen ob Passwort bereits gesetzt ist
      (async () => {
        try {
          const r = await api.post("/kirmes/public/verify-email", { email: verifiedEmail, code: "already-verified" });
          if (r.data?.password_hash !== undefined || r.data?.email_verified) {
            goToDashboard(r.data);
          }
        } catch {
          setStep("setpw");
        }
      })();
    }
  }, [verifiedParam, verifiedEmail]); // eslint-disable-line react-hooks/exhaustive-deps


  const goToDashboard = (sch) => {
    setSchausteller(sch);
    loadBookings(sch.id);
    loadLastdiagramme(sch.id);
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
    for (let i = 0; i < additionalSignups.length; i++) {
      const a = additionalSignups[i];
      if (!a.platznummer || !a.fahrgeschaeft || !a.connection_type) {
        toast.error(`Bitte alle Felder beim ${i + 2}. Anschluss ausfüllen`); return;
      }
    }
    setSaving(true);
    try {
      // Submit main signup
      const r = await api.post("/kirmes/public/signup", { event_id: selectedEvent.id, schausteller_id: schausteller.id, ...signupForm });
      const signupId = r.data?.signup_id || r.data?.id;
      setLastSignupId(signupId);

      // Submit additional signups
      for (const extra of additionalSignups) {
        await api.post("/kirmes/public/signup", { event_id: selectedEvent.id, schausteller_id: schausteller.id, ...extra });
      }

      if (r.data?.payment_status === "pending_payment") {
        toast.success(`${1 + additionalSignups.length} Anmeldung(en) vorgemerkt! Bitte bezahlen Sie die Kaution.`);
        setStep("payment");
      } else {
        toast.success(`${1 + additionalSignups.length} Anmeldung(en) erfolgreich!`);
        setStep("done");
      }
      setAdditionalSignups([]);
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
        if (schausteller) { loadBookings(schausteller.id); loadLastdiagramme(schausteller.id); }
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
                  <Button onClick={handleLogin} disabled={saving} className="w-full bg-fuchsia-600 hover:bg-fuchsia-700 text-white" data-testid="login-btn">
                    {saving ? "Wird geprüft..." : "Anmelden"} <ArrowRight className="w-4 h-4 ml-1" />
                  </Button>
                  <button onClick={() => { setResetEmail(loginEmail); setStep("reset-request"); }} className="w-full text-center text-xs text-gray-400 hover:text-fuchsia-600 underline mt-1" data-testid="forgot-password-link">
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
                  <Button onClick={handleRegister} disabled={saving} className="w-full bg-fuchsia-600 hover:bg-fuchsia-700 text-white mt-2" data-testid="register-btn">
                    {saving ? "Wird registriert..." : "Registrieren"} <ArrowRight className="w-4 h-4 ml-1" />
                  </Button>
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

              {/* Lastdiagramme Section */}
              <div className="bg-white border border-gray-200 rounded-xl overflow-hidden mt-4" data-testid="lastdiagramm-section">
                <div className="px-4 py-3 bg-gray-50 border-b border-gray-200 flex items-center gap-2">
                  <Zap className="w-4 h-4 text-amber-500" />
                  <span className="text-sm font-semibold text-gray-700">Lastdiagramme ({lastdiagramme.available.length + lastdiagramme.purchased.length})</span>
                </div>
                {(lastdiagramme.available.length > 0 || lastdiagramme.purchased.length > 0) ? (
                  <div className="divide-y divide-gray-100">
                    {/* Purchased - can download */}
                    {lastdiagramme.purchased.map(item => (
                      <div key={item.signup_id} className="px-4 py-3" data-testid={`ld-purchased-${item.signup_id}`}>
                        <div className="flex items-start justify-between">
                          <div className="min-w-0 flex-1">
                            <p className="text-sm font-semibold text-gray-900">{item.event_name}</p>
                            <div className="flex flex-wrap gap-x-3 gap-y-1 mt-1 text-xs text-gray-500">
                              {item.event_start && <span className="flex items-center gap-1"><CalendarDays className="w-3 h-3" />{new Date(item.event_start).toLocaleDateString("de-DE")} – {new Date(item.event_end).toLocaleDateString("de-DE")}</span>}
                              <span className="flex items-center gap-1"><Zap className="w-3 h-3" />{item.connection_type}</span>
                              <span>Platz: <strong>{item.platznummer}</strong></span>
                            </div>
                            <div className="mt-1.5 flex items-center gap-2">
                              <span className="text-[10px] bg-emerald-100 text-emerald-700 px-1.5 py-0.5 rounded font-medium">Gekauft</span>
                              <span className="text-xs text-gray-400 font-mono">{item.invoice_number}</span>
                            </div>
                          </div>
                          <button
                            onClick={() => downloadLastdiagramm(item.order_id)}
                            disabled={ldDownloading === item.order_id}
                            className="ml-2 flex items-center gap-1.5 px-3 py-1.5 bg-fuchsia-600 hover:bg-fuchsia-700 text-white text-xs rounded-lg transition-colors disabled:opacity-50"
                            data-testid={`ld-download-${item.signup_id}`}
                          >
                            <Download className="w-3.5 h-3.5" />
                            {ldDownloading === item.order_id ? "Laden..." : "PDF"}
                          </button>
                        </div>
                      </div>
                    ))}
                    {/* Available - can purchase */}
                    {lastdiagramme.available.map(item => (
                      <div key={item.signup_id} className="px-4 py-3" data-testid={`ld-available-${item.signup_id}`}>
                        <div className="flex items-start justify-between">
                          <div className="min-w-0 flex-1">
                            <p className="text-sm font-semibold text-gray-900">{item.event_name}</p>
                            <div className="flex flex-wrap gap-x-3 gap-y-1 mt-1 text-xs text-gray-500">
                              {item.event_start && <span className="flex items-center gap-1"><CalendarDays className="w-3 h-3" />{new Date(item.event_start).toLocaleDateString("de-DE")} – {new Date(item.event_end).toLocaleDateString("de-DE")}</span>}
                              <span className="flex items-center gap-1"><Zap className="w-3 h-3" />{item.connection_type}</span>
                              <span>Platz: <strong>{item.platznummer}</strong></span>
                              {item.kwh_used != null && <span>Verbrauch: <strong>{item.kwh_used.toFixed(2)} kWh</strong></span>}
                            </div>
                          </div>
                          <button
                            onClick={() => {
                              if (window.confirm(`Lastdiagramm für "${item.event_name}" kaufen?\n\n125,00 EUR zzgl. MwSt.\n= 148,75 EUR brutto\n\nZahlung: ${schausteller?.kauf_auf_rechnung ? "Auf Rechnung" : "Kreditkarte / PayPal"}`)) {
                                purchaseLastdiagramm(item.signup_id);
                              }
                            }}
                            disabled={ldPurchasing === item.signup_id}
                            className="ml-2 flex items-center gap-1.5 px-3 py-1.5 bg-amber-500 hover:bg-amber-600 text-white text-xs rounded-lg transition-colors disabled:opacity-50 whitespace-nowrap"
                            data-testid={`ld-buy-${item.signup_id}`}
                          >
                            {ldPurchasing === item.signup_id ? "Wird bestellt..." : "Kaufen (148,75 EUR)"}
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="p-6 text-center text-sm text-gray-400">Noch keine Lastdiagramme vorhanden</div>
                )}
              </div>
            </div>
          )}

          {/* Select Event */}
          {step === "event" && (
            <div data-testid="event-step">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-bold text-gray-900">Veranstaltung wählen</h2>
                <button onClick={() => { loadBookings(schausteller.id); loadLastdiagramme(schausteller.id); setStep("dashboard"); }} className="text-sm text-fuchsia-600 hover:text-fuchsia-700 flex items-center gap-1" data-testid="back-dashboard-btn">
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
                    const p = [...(selectedEvent.prices || []), ...(selectedEvent.wohnwagen_prices || [])].find(pr => pr.connection_type === signupForm.connection_type);
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

                {/* Zusätzliche Anschlüsse */}
                {additionalSignups.map((extra, idx) => (
                  <div key={idx} className={`border rounded-xl p-4 space-y-4 relative ${extra.isWohnwagen ? "border-amber-200 bg-amber-50/30" : "border-gray-200 bg-gray-50"}`} data-testid={`extra-signup-${idx}`}>
                    <div className="flex items-center justify-between mb-1">
                      <span className={`text-xs font-semibold uppercase tracking-wider ${extra.isWohnwagen ? "text-amber-600" : "text-gray-500"}`}>
                        {extra.isWohnwagen ? `Wohnwagen ${idx + 1}` : `${idx + 2}. Anschluss`}
                      </span>
                      <button onClick={() => setAdditionalSignups(prev => prev.filter((_, i) => i !== idx))} className="text-xs text-red-400 hover:text-red-600" data-testid={`remove-extra-${idx}`}>Entfernen</button>
                    </div>
                    {extra.isWohnwagen ? (
                      <>
                        <div className="grid grid-cols-2 gap-3">
                          <div><Label className="text-gray-700 text-sm">Position / Platznummer</Label><Input value={extra.platznummer} onChange={e => { const v = e.target.value; setAdditionalSignups(prev => prev.map((s, i) => i === idx ? { ...s, platznummer: v } : s)); }} className="mt-1" placeholder="z.B. A15" data-testid={`extra-platznummer-${idx}`} /></div>
                          <div><Label className="text-gray-700 text-sm">Nutzung</Label><Input value={extra.fahrgeschaeft} onChange={e => { const v = e.target.value; setAdditionalSignups(prev => prev.map((s, i) => i === idx ? { ...s, fahrgeschaeft: v } : s)); }} className="mt-1" placeholder="Wohnwagen" data-testid={`extra-fahrgeschaeft-${idx}`} /></div>
                        </div>
                        <div>
                          <Label className="text-gray-700 text-sm">Anschluss</Label>
                          <div className="grid grid-cols-3 gap-2 mt-1">
                            {(selectedEvent.wohnwagen_prices || []).map(p => (
                              <button key={p.connection_type} type="button"
                                onClick={() => setAdditionalSignups(prev => prev.map((s, i) => i === idx ? { ...s, connection_type: p.connection_type } : s))}
                                className={`p-2.5 rounded-lg border text-center transition-colors ${extra.connection_type === p.connection_type ? "border-amber-500 bg-amber-100 text-amber-700" : "border-gray-200 text-gray-600 hover:border-gray-300 bg-white"}`}
                                data-testid={`extra-conn-ww-${idx}-${p.connection_type}`}>
                                <Home className="w-3.5 h-3.5 mx-auto mb-0.5" />
                                <span className="text-xs font-medium block">{p.connection_type}</span>
                                <span className="text-[10px] text-gray-400 block">{p.price.toFixed(2)} EUR</span>
                              </button>
                            ))}
                          </div>
                        </div>
                      </>
                    ) : (
                      <>
                        <div><Label className="text-gray-700 text-sm">Platznummer *</Label><Input value={extra.platznummer} onChange={e => { const v = e.target.value; setAdditionalSignups(prev => prev.map((s, i) => i === idx ? { ...s, platznummer: v } : s)); }} className="mt-1" placeholder="z.B. A12" data-testid={`extra-platznummer-${idx}`} /></div>
                        <div><Label className="text-gray-700 text-sm">Fahrgeschäft / Betrieb *</Label><Input value={extra.fahrgeschaeft} onChange={e => { const v = e.target.value; setAdditionalSignups(prev => prev.map((s, i) => i === idx ? { ...s, fahrgeschaeft: v } : s)); }} className="mt-1" placeholder="z.B. Achterbahn, Autoscooter, Imbissbude" data-testid={`extra-fahrgeschaeft-${idx}`} /></div>
                        <div>
                          <Label className="text-gray-700 text-sm">Stromanschluss *</Label>
                          <div className="grid grid-cols-3 gap-2 mt-1">
                            {(selectedEvent.prices || []).map(p => (
                              <button key={p.connection_type} type="button"
                                onClick={() => setAdditionalSignups(prev => prev.map((s, i) => i === idx ? { ...s, connection_type: p.connection_type } : s))}
                                className={`p-3 rounded-lg border text-center transition-colors ${extra.connection_type === p.connection_type ? "border-fuchsia-500 bg-fuchsia-50 text-fuchsia-700" : "border-gray-200 text-gray-600 hover:border-gray-300 bg-white"}`}
                                data-testid={`extra-conn-${idx}-${p.connection_type}`}>
                                <Zap className="w-4 h-4 mx-auto mb-1" />
                                <span className="text-xs font-medium block">{p.connection_type}</span>
                                <span className="text-[10px] text-gray-400 block">{p.price.toFixed(2)} EUR</span>
                              </button>
                            ))}
                          </div>
                        </div>
                      </>
                    )}
                    <div>
                      <Label className="text-gray-700 text-sm">Zahlungsmittel</Label>
                      <select value={extra.payment_method} onChange={e => { const v = e.target.value; setAdditionalSignups(prev => prev.map((s, i) => i === idx ? { ...s, payment_method: v } : s)); }} className="w-full mt-1 px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:border-fuchsia-500 bg-white" data-testid={`extra-payment-${idx}`}>
                        {PAYMENT_METHODS.filter(m => m.value !== "rechnung" || schausteller?.kauf_auf_rechnung).map(m => <option key={m.value} value={m.value}>{m.label}</option>)}
                      </select>
                    </div>
                  </div>
                ))}

                {/* Buttons: Weiteren Anschluss / Wohnwagen */}
                <div className="flex flex-col gap-2">
                  <button
                    type="button"
                    onClick={() => setAdditionalSignups(prev => [...prev, { platznummer: "", fahrgeschaeft: "", connection_type: "", payment_method: signupForm.payment_method, isWohnwagen: false }])}
                    className="flex-1 flex items-center justify-center gap-2 px-3 py-2.5 border-2 border-dashed border-fuchsia-300 rounded-lg text-sm font-medium text-fuchsia-600 hover:bg-fuchsia-50 hover:border-fuchsia-400 transition-colors"
                    data-testid="add-extra-signup-btn"
                  >
                    <Plus className="w-4 h-4" /> Weiteren Anschluss anmelden
                  </button>
                  <button
                    type="button"
                    onClick={() => setAdditionalSignups(prev => [...prev, { platznummer: "", fahrgeschaeft: "Wohnwagen", connection_type: "", payment_method: signupForm.payment_method, isWohnwagen: true }])}
                    className="flex-1 flex items-center justify-center gap-2 px-3 py-2.5 border-2 border-dashed border-amber-300 rounded-lg text-sm font-medium text-amber-600 hover:bg-amber-50 hover:border-amber-400 transition-colors"
                    data-testid="add-wohnwagen-btn"
                  >
                    <Plus className="w-4 h-4" /> Wohnwagen-Anschluss anmelden
                  </button>
                </div>

                {/* AGB Checkbox */}
                <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                  <label className="flex items-start gap-3 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={agbAccepted}
                      onChange={e => setAgbAccepted(e.target.checked)}
                      className="mt-0.5 w-5 h-5 rounded border-blue-300 text-blue-600 focus:ring-blue-500 flex-shrink-0"
                      data-testid="agb-checkbox"
                    />
                    <span className="text-sm text-blue-900">
                      Hiermit akzeptiere ich die{" "}
                      <button type="button" onClick={(e) => { e.preventDefault(); setShowAgb(true); }} className="text-blue-600 font-semibold underline hover:text-blue-800" data-testid="agb-link">
                        AGB's der Eventenergie Deutschland GmbH & Co. KG
                      </button>
                    </span>
                  </label>
                </div>

                <Button onClick={handleSignup} disabled={saving || !agbAccepted} className="w-full bg-fuchsia-600 hover:bg-fuchsia-700 text-white disabled:opacity-50" data-testid="submit-signup-btn">
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
                <Button onClick={() => { setSignupForm({ platznummer: "", fahrgeschaeft: "", connection_type: "", payment_method: "kreditkarte" }); setAdditionalSignups([]); setStep("signup"); }} variant="outline" className="border-fuchsia-200 text-fuchsia-600 hover:bg-fuchsia-50" data-testid="another-signup-btn">
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
        <span>&copy; {new Date().getFullYear()} Eventenergie Deutschland GmbH & Co. KG</span>
        <span className="mx-2">·</span>
        <button onClick={() => setShowDatenschutz(true)} className="text-fuchsia-600 hover:text-fuchsia-700 underline" data-testid="datenschutz-btn">Datenschutz</button>
        <span className="mx-2">·</span>
        <button onClick={() => setShowImpressum(true)} className="text-fuchsia-600 hover:text-fuchsia-700 underline" data-testid="impressum-btn">Impressum</button>
      </footer>

      {/* AGB Modal */}
      {showAgb && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4" onClick={() => setShowAgb(false)} data-testid="agb-modal">
          <div className="bg-white rounded-xl shadow-xl max-w-lg w-full max-h-[85vh] overflow-hidden" onClick={e => e.stopPropagation()}>
            <div className="p-4 border-b border-gray-200 flex items-center justify-between">
              <h2 className="font-semibold text-gray-900">Allgemeine Geschäftsbedingungen</h2>
              <button onClick={() => setShowAgb(false)} className="text-gray-400 hover:text-gray-600" data-testid="agb-close"><X className="w-5 h-5" /></button>
            </div>
            <div className="p-5 overflow-y-auto max-h-[70vh] space-y-6 text-sm text-gray-700 leading-relaxed">
              {/* Abrechnung */}
              <div>
                <h3 className="font-bold text-gray-900 text-base mb-2">Abrechnung</h3>
                <ol className="list-decimal pl-5 space-y-2">
                  <li>Die angebotenen Preise sind Nettopreise und werden zuzüglich der jeweils geltenden gesetzlichen Mehrwertsteuer berechnet.</li>
                  <li>Falls in unserem Angebot oder Auftrag eine Anzahlungsaufforderung enthalten ist, beachten Sie bitte Folgendes: Überweisen Sie den angegebenen Betrag der Brutto-Angebots- oder Auftragssumme auf unser Konto. Unsere Kontoverbindung finden Sie auf unserem Geschäftspapier im unteren Abschnitt. Um den Betrag zuordnen zu können, geben Sie bitte immer unsere Referenz Nummer an (Angebots- oder Rechnungsnummer). Eine eventuelle Rückerstattung der Anzahlung erfolgt in der Schlussrechnung zum Mietvertrag. Selbstverständlich lassen wir Ihnen nach Rücksprache im Vorfeld eine Rechnung zukommen. Bei Nichteinhaltung der Anzahlung erfolgt keine Lieferung (oder Bereitstellung für Selbstabholer) unseres Mietmaterials und keine Dienstleistungen. Ihr Auftrag (Bestellung) wird zu unseren weiter unten angegebenen Stornierungskosten berechnet und anschließend von uns geschlossen.</li>
                  <li><strong>Stromverbrauch:</strong> Der aktuelle Zählerstand unseres geeichten Zählers wird bei Aufbau notiert. Beim Abbau wird der neue Stand ebenfalls notiert und 1:1 an das jeweilige EVU gemeldet. Diese schreiben die Rechnung an den Kunden.</li>
                </ol>
              </div>

              {/* Versorgung */}
              <div>
                <h3 className="font-bold text-gray-900 text-base mb-2">Versorgung</h3>
                <ol className="list-decimal pl-5 space-y-2">
                  <li>Sämtliche Anschlussarbeiten an Fremdgewerke sind vor Inbetriebnahme der Anlagen durch den Anlagenverantwortlichen des jeweiligen Fremdgewerks auf Richtigkeit zu prüfen. Unsere Installation wird eigenständig geprüft und freigegeben. Der Anschlusspunkt (z.B. Steckdose) ist der Übergabepunkt zum Fremdgewerk. Für den ordnungsgemäßen Anschluss der Anlagen ist somit das Inbetriebsetzen Unternehmen verantwortlich. Der Potenzialausgleich in den Fremdgewerken endet mit Montage eines Übergabepunktes. Der örtliche Potenzialausgleich wird durch das Gewerk realisiert.</li>
                </ol>
              </div>

              {/* Kalkulation */}
              <div>
                <h3 className="font-bold text-gray-900 text-base mb-2">Kalkulation</h3>
                <ol className="list-decimal pl-5 space-y-2">
                  <li>Grundsätzlich gelten für unsere Kalkulation nur die in Verbindung stehenden Planunterlagen, Ausschreibungen, Details, und Leistungsverzeichnisse. Darüber hinaus zur Verfügung gestellte Pläne der Fremdgewerke sind nur informativ und finden in unserer Kalkulation keine Berücksichtigung. Bei unserer Kalkulation sind wir davon ausgegangen, dass wir eine koordinierte Ausführungsplanung erhalten, die den anerkannten Regeln und Richtlinien entspricht. Dies ist die Grundlage zur Erstellung unserer Werks- und Montageplanung.</li>
                  <li>Wir setzen voraus, dass alle Montagetätigkeiten zügig ohne Unterbrechung und während unserer normalen Arbeitszeit Mo-Do 7:30-16:30 und Fr. 7:30 - 15:15 Uhr, ausgeführt werden können. Mehraufwand durch Montagezeiten außerhalb dieser Zeiten werden gesondert berechnet. Wartezeiten, die nicht von uns verschuldet werden, sowie Mehraufwand durch Schwierigkeiten oder nicht kalkulierten Arbeiten, werden zusätzlich nach tatsächlichem Aufwand berechnet.</li>
                  <li>Etwaige Anforderungen durch das Amt für Immissionsschutz wurden nicht berücksichtigt.</li>
                  <li>Unsere Kalkulation basiert auf den zurzeit gültigen Vorschriften- und Gesetzesstand. Sollten sich diese während der Projektphase ändern, so weisen wir darauf hin, dass wir dem Auftraggeber ein Angebot unterbreiten, welches wir nach entsprechender Beauftragung umsetzen werden.</li>
                </ol>
              </div>

              {/* Kraftstoff / Aggregate */}
              <div>
                <h3 className="font-bold text-gray-900 text-base mb-2">Kraftstoff / Aggregate</h3>
                <ol className="list-decimal pl-5 space-y-2">
                  <li>Fuel-Management wird durch Eventenergie Deutschland GmbH & Co. KG durchgeführt, wenn nicht ausdrücklich anders vereinbart. Zum Zeitpunkt der Betankung legen wir, zur Abrechnung an den Veranstalter, den tagesaktuellen Heizölpreis zuzüglich einer Handling-Pauschale von 35% zugrunde.</li>
                  <li><strong>Kraftstoffregelung Deutschland:</strong> Hinweis für Betreiber (Mieter) von Kraftstoffanlagen gemäß WHG (Wasserhaushaltsgesetz). Nach §5 Wasserhaushaltsgesetz (WHG) und §2 Abs. 9 der Anlagenverordnung (AwSV) darf keine nachteilige Veränderung der Gewässereigenschaften durch die Anlage (auch Miet-Anlagen) entstehen. Anlagen mit einem Tank größer 1.001 Liter, welche länger als ein halbes Jahr betrieben werden, sind fachbetriebspflichtig und müssen von einem Sachverständigen abgenommen werden. Außerdem gehören diese Anlagen 6 Wochen vor dem Betrieb, der unteren Wasserbehörde angezeigt. Die Verantwortung für die Einhaltung dieser Vorgaben übernimmt der Mieter. Er verpflichtet sich evtl. Verstöße an den Vermieter mitzuteilen.</li>
                  <li><strong>Betriebsarten / Leistungsabgabe:</strong> Standardausführung zum Mietmaterial. 400V / 50 Hz für die Netzform TN-C-S. Änderungen sind auf Anfrage und gegen Aufpreis möglich. Unter Berücksichtigung der im Angebot angegebenen Leistung (entspricht 100%) sind unsere Aggregate für folgende Betriebsarten/Leistungsabgaben geeignet:
                    <ul className="list-disc pl-5 mt-1 space-y-0.5">
                      <li>Dauerbetrieb bis max. 80 % der angegebenen Leistung</li>
                      <li>Kurzzeitbetrieb bis 100 % der angegebenen Leistung (Max. 3-5 Betriebsstunden)</li>
                      <li>Stoßlasten max. 50 % der angegebenen Leistung</li>
                      <li>Schieflasten max. 20 % der angegebenen Leistung</li>
                    </ul>
                    <p className="mt-1">Alle Angaben nur während des Betriebs möglich, nicht aus dem Stand-by-Betrieb während der Anlaufphase.</p>
                  </li>
                  <li>Bitte beachten Sie bei Ihrer Planung die gewünschte Versorgungssicherheit der Mietanlage. Wenn in Ihrer Planung Aggregate zum Einsatz kommen beachten Sie bitte, dass sich in allen Aggregaten drehende, mechanische und elektronische Teile befinden. Es gibt somit keine 100 % Garantie, dass es nie zu einem Störfall (Ausfall) kommen kann.</li>
                  <li><strong>Folgende Planungsmöglichkeiten bieten wir an:</strong>
                    <ul className="list-disc pl-5 mt-1 space-y-1">
                      <li><strong>Ein Single Aggregat:</strong> Im Störfall kann eine Versorgungsunterbrechung einen längeren Zeitraum andauern.</li>
                      <li><strong>Zwei oder mehr Aggregate (Redundanz mit kurzzeitiger Unterbrechung):</strong> Im Störfall erfolgt eine automatische Umschaltung von einem zum anderen Aggregat. Die Versorgungsunterbrechung beträgt ca. 15-20 Sekunden.</li>
                      <li><strong>Zwei oder mehrere Aggregate gleichzeitig betrieben:</strong> Im Störfall wird eine unterbrechungsfreie Versorgungssicherheit, durch das oder die anderen Aggregate gewährleistet.</li>
                    </ul>
                  </li>
                  <li>Stromerzeuger, Tanks und Lichtmasten werden vollgetankt ausgeliefert - wenn nicht anders vereinbart. (Zusatztanks nur Festland, Inseln auf Anfrage).</li>
                  <li>Unsere Aggregate und Zusatztanks können mit HEL (Heizöl extra leicht) DIN 51 603-01 betankt werden. Das HEL muss ausreichend mit Kälteadditiv (Sommer wie Winter) additiviert sein (bis -20°C). Damit die Kältesicherheit gewährleistet ist, muss das Kälteadditiv vor dem Frost bei über 0°C zum HEL gegeben werden. Das Verwenden von nicht additiviertem Heizöl kann bei niedrigen Temperaturen zum Stillstand der Maschine führen. Dadurch entstehende Kosten werden dem Auftraggeber gesondert nach Aufwand berechnet.</li>
                  <li>Bei Nutzung eines externen Tanks, kann der interne Tank nur bedingt genutzt werden. (Umschaltung am 3 Wege-Kraftstoffventil nur bei Motorstillstand zulässig). Zusätzlich empfehlen wir Ihnen unser Winterset mit zu bestellen.</li>
                </ol>
              </div>

              {/* Transport */}
              <div>
                <h3 className="font-bold text-gray-900 text-base mb-2">Transport</h3>
                <ol className="list-decimal pl-5 space-y-2">
                  <li>Auf- und Abbau wird durch einen Techniker der Eventenergie Deutschland GmbH & Co. KG durchgeführt.</li>
                  <li>Bei Anlieferungen sind 2 Stunden Abladezeit Inklusive. Jede weitere angefangene Wartestunde berechnen wir mit 65€ pro Stunde. Zum Aufladen bei Abholung ist 1 Stunde inklusive, jede weitere angefangene Stunde berechnen wir ebenfalls mit 65€ pro Stunde.</li>
                  <li>Für alle Bestellungen und Lieferungen unter 10 Tage gilt: Die Auslieferung zum Mietmaterial erfolgt nach Absprache und Prüfung der Verfügbarkeit, jedoch frühestens 8-10 Tage nach Erhalt Ihrer Bestellung. Expresslieferungen und Notfälle müssen gesondert schriftlich vereinbart werden und gehen mit einer Erhöhung von 20% der angebotenen Mietartikel einher.</li>
                  <li><strong>GPS-Tracking:</strong> Der Vermieter weist darauf hin, dass die Mietgeräte teilweise mit einem GPS-Ortungssystem ausgerüstet sind. Die an den Vermieter bei Aktivierung übermittelten Daten, dienen der Erfassung von technischen Betriebszuständen des Mietgeräts.</li>
                  <li>Aus gegebenem Anlass zum stark variierenden Kraftstoffpreis, behalten wir uns eine Anpassung zum angebotenen Transportpreis ab Bestelleingang vor.</li>
                </ol>
              </div>

              {/* Pflichten des Mieters */}
              <div>
                <h3 className="font-bold text-gray-900 text-base mb-2">Pflichten des Mieters</h3>
                <ol className="list-decimal pl-5 space-y-2">
                  <li>Der Mietgegenstand darf nur zu den vereinbarten Arbeiten und an dem vereinbarten Ort genutzt werden. Der Mieter ist ohne Zustimmung des Vermieters nicht berechtigt, den Mietgegenstand einem Dritten zu überlassen oder den Mietgegenstand weiter zu vermieten.</li>
                  <li>Zeigen sich Störungen, muss der Mieter dies dem Vermieter unverzüglich schriftlich anzeigen. Der Mieter ist nicht berechtigt, ohne Zustimmung des Vermieters Reparaturen an dem Mietgegenstand durchzuführen. <strong>Wir weisen ausdrücklich darauf hin, dass wir keine Haftung, Ausfallkosten oder an uns gerichtete Regressansprüche übernehmen, die durch einen Störfall verursacht wurden.</strong></li>
                  <li>Der Mieter ist verpflichtet, den Mietgegenstand nur durch eingewiesenes und fachkundiges Personal bedienen zu lassen.</li>
                  <li>Die Mietobjekte sind in gleichem Zustand wie geliefert bereitzustellen. Für Diebstahl, Schäden und Verunreinigungen jeglicher Art, haftet der Mieter. Gitterboxen sind entsprechend dem Auslieferungszustand gepackt zu übergeben. Bei Missachtung behalten wir uns vor, erforderliche Arbeiten und/oder Reinigungskosten in Rechnung zu stellen.</li>
                  <li>Der Mieter ist verpflichtet, zur Abdeckung der Risiken gegen Verlust oder Beschädigung des Mietgegenstandes eine Versicherung in Höhe des Wiederbeschaffungswertes des Mietgegenstandes abzuschließen und diese auf Verlangen des Vermieters nachzuweisen.</li>
                </ol>
              </div>

              {/* Mietvertrag */}
              <div>
                <h3 className="font-bold text-gray-900 text-base mb-2">Mietvertrag</h3>
                <ol className="list-decimal pl-5 space-y-2">
                  <li>Ein Vertrag (Mietvertrag) ist abgeschlossen, wenn der Mieter den Auftrag (Angebot) schriftlich bestätigt oder wenn ein Vertrag von den Parteien wechselseitig unterzeichnet wird.</li>
                  <li>Das Mietverhältnis beginnt mit dem Tag der Anlieferung (Berechnung voller Miettag). Ist bei der Auftragserteilung durch den Kunden kein Mietende angegeben (nur werktags Mo.-Do. 07:30-16:30 Uhr und Fr. 07:30 - 15:15 Uhr möglich, samstags, sonn- und feiertags nur nach vorheriger Absprache und Mehrkostenaufwand) gilt: Freimeldungen (für den gleichen Werktag der Abmeldung) müssen bis spätestens 11:00 Uhr schriftlich unserem Büro gemeldet werden. Ihre Freimeldung senden Sie bitte an: <a href="mailto:info@eventenergie-deutschland.de" className="text-blue-600 hover:underline">info@eventenergie-deutschland.de</a></li>
                  <li>Unser Mietmaterial unterliegt vor der Auslieferung einer hausinternen Werksprüfung. Weitere Prüfungen zum Mietmaterial während der Mietperiode sind nicht im Mietpreis enthalten. Diese werden vom Mieter nach eigener Gefährdungsbeurteilung durchgeführt. Die Kosten trägt der Mieter. Der Mieter hat den Mietgegenstand bei Übergabe zu prüfen.</li>
                  <li>Mängel hat der Mieter dem Vermieter unverzüglich, spätestens jedoch einen Tag nach Übergabe schriftlich anzuzeigen und zu rügen. Nach Ablauf der Rügefrist gilt der Mietgegenstand als vertragsgemäß mängelfrei übergeben.</li>
                  <li>Das Mietmaterial unterliegt während der Mietzeit der Obhutspflicht des Mieters. Der Mieter erklärt sich damit einverstanden, dass bei einem Verlust der Mietsache der aktuelle Wiederbeschaffungswert unabhängig vom Zeitwert der Mietsache berechnet wird.</li>
                  <li>Eine Rückvergütung der Mietsache gegenüber bereits geleisteten Zahlungen oder offenen Forderungen erfolgt nicht.</li>
                  <li>Im Störfall einer Mietsache stehen wir Ihnen innerhalb unserer o.a. Bürozeiten und selbstverständlich mit unserem 24 Stunden Service außerhalb der Bürozeiten jederzeit unter der Nummer <strong>0171/7775543</strong> zur Verfügung. Wir sind bemüht, schnellstmöglich den Störfall zu beheben.</li>
                  <li>Eine Mietminderung erfolgt nur, wenn der Mieter den Störfall unverzüglich anzeigt, sich der Mietgegenstand innerhalb von Deutschland befindet und der Mangel durch uns nicht innerhalb von 24 Stunden behoben werden kann (ab Störfall-Meldeeingang beim Vermieter und bei nachweislichem Nichtverschulden des Mieters).</li>
                </ol>
              </div>

              {/* Stornierungskosten */}
              <div>
                <h3 className="font-bold text-gray-900 text-base mb-2">Stornierungskosten</h3>
                <p className="mb-2">Sofern der Mieter vor Auslieferung bzw. Beginn des Mietzeitraums vom Vertrag zurücktritt oder den Vertrag storniert, ist der Vermieter berechtigt, folgende pauschalierten Sätze zu berechnen:</p>
                <div className="bg-gray-50 border border-gray-200 rounded-lg p-3 space-y-1">
                  <div className="flex justify-between text-sm"><span>56 und länger Tage vor Auslieferung</span><span className="font-semibold">25 %</span></div>
                  <div className="flex justify-between text-sm"><span>28 Tage vor Auslieferung</span><span className="font-semibold">50 %</span></div>
                  <div className="flex justify-between text-sm"><span>14 Tage vor Auslieferung</span><span className="font-semibold">75 %</span></div>
                  <div className="flex justify-between text-sm"><span>7 Tage vor Auslieferung</span><span className="font-semibold">90 %</span></div>
                  <div className="flex justify-between text-sm border-t border-gray-300 pt-1 mt-1"><span>Stornierung einer Expresslieferung</span><span className="font-bold text-red-600">100 %</span></div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Datenschutz Modal */}
      {showDatenschutz && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4" onClick={() => setShowDatenschutz(false)} data-testid="datenschutz-modal">
          <div className="bg-white rounded-xl shadow-xl max-w-2xl w-full max-h-[85vh] overflow-hidden" onClick={e => e.stopPropagation()}>
            <div className="p-4 border-b border-gray-200 flex items-center justify-between">
              <h2 className="font-semibold text-gray-900">Datenschutzerklärung</h2>
              <button onClick={() => setShowDatenschutz(false)} className="text-gray-400 hover:text-gray-600" data-testid="datenschutz-close"><X className="w-5 h-5" /></button>
            </div>
            <div className="p-5 overflow-y-auto max-h-[70vh] space-y-6 text-sm text-gray-700 leading-relaxed">

              <div>
                <h3 className="text-base font-semibold text-gray-900 mb-2">1. Datenschutz auf einen Blick</h3>
                <h4 className="font-semibold text-gray-900 mt-3 mb-1">Allgemeine Hinweise</h4>
                <p>Die folgenden Hinweise geben einen einfachen Überblick darüber, was mit Ihren personenbezogenen Daten passiert, wenn Sie unsere Website besuchen. Personenbezogene Daten sind alle Daten, mit denen Sie persönlich identifiziert werden können. Ausführliche Informationen zum Thema Datenschutz entnehmen Sie unserer unter diesem Text aufgeführten Datenschutzerklärung.</p>
              </div>

              <div>
                <h4 className="font-semibold text-gray-900 mb-1">Datenerfassung auf unserer Website</h4>
                <p className="font-medium text-gray-800 mt-2 mb-1">Wer ist verantwortlich für die Datenerfassung auf dieser Website?</p>
                <p>Die Datenverarbeitung auf dieser Website erfolgt durch den Websitebetreiber. Dessen Kontaktdaten können Sie dem Impressum dieser Website entnehmen.</p>
                <p className="font-medium text-gray-800 mt-3 mb-1">Wie erfassen wir Ihre Daten?</p>
                <p>Ihre Daten werden zum einen dadurch erhoben, dass Sie uns diese mitteilen. Hierbei kann es sich z.B. um Daten handeln, die Sie in ein Kontaktformular eingeben.</p>
                <p className="mt-2">Andere Daten werden automatisch beim Besuch der Website durch unsere IT-Systeme erfasst. Das sind vor allem technische Daten (z.B. Internetbrowser, Betriebssystem oder Uhrzeit des Seitenaufrufs). Die Erfassung dieser Daten erfolgt automatisch, sobald Sie unsere Website betreten.</p>
                <p className="font-medium text-gray-800 mt-3 mb-1">Wofür nutzen wir Ihre Daten?</p>
                <p>Ein Teil der Daten wird erhoben, um eine fehlerfreie Bereitstellung der Website zu gewährleisten. Andere Daten können zur Analyse Ihres Nutzerverhaltens verwendet werden.</p>
                <p className="font-medium text-gray-800 mt-3 mb-1">Welche Rechte haben Sie bezüglich Ihrer Daten?</p>
                <p>Sie haben jederzeit das Recht unentgeltlich Auskunft über Herkunft, Empfänger und Zweck Ihrer gespeicherten personenbezogenen Daten zu erhalten. Sie haben außerdem ein Recht, die Berichtigung, Sperrung oder Löschung dieser Daten zu verlangen. Hierzu sowie zu weiteren Fragen zum Thema Datenschutz können Sie sich jederzeit unter der im Impressum angegebenen Adresse an uns wenden. Des Weiteren steht Ihnen ein Beschwerderecht bei der zuständigen Aufsichtsbehörde zu.</p>
              </div>

              <div>
                <h4 className="font-semibold text-gray-900 mb-1">Analyse-Tools und Tools von Drittanbietern</h4>
                <p>Beim Besuch unserer Website kann Ihr Surf-Verhalten statistisch ausgewertet werden. Das geschieht vor allem mit Cookies und mit sogenannten Analyseprogrammen. Die Analyse Ihres Surf-Verhaltens erfolgt in der Regel anonym; das Surf-Verhalten kann nicht zu Ihnen zurückverfolgt werden. Sie können dieser Analyse widersprechen oder sie durch die Nichtbenutzung bestimmter Tools verhindern. Detaillierte Informationen dazu finden Sie in der folgenden Datenschutzerklärung.</p>
                <p className="mt-2">Sie können dieser Analyse widersprechen. Über die Widerspruchsmöglichkeiten werden wir Sie in dieser Datenschutzerklärung informieren.</p>
              </div>

              <div>
                <h3 className="text-base font-semibold text-gray-900 mb-2">2. Allgemeine Hinweise und Pflichtinformationen</h3>
                <h4 className="font-semibold text-gray-900 mb-1">Datenschutz</h4>
                <p>Die Betreiber dieser Seiten nehmen den Schutz Ihrer persönlichen Daten sehr ernst. Wir behandeln Ihre personenbezogenen Daten vertraulich und entsprechend der gesetzlichen Datenschutzvorschriften sowie dieser Datenschutzerklärung.</p>
                <p className="mt-2">Wenn Sie diese Website benutzen, werden verschiedene personenbezogene Daten erhoben. Personenbezogene Daten sind Daten, mit denen Sie persönlich identifiziert werden können. Die vorliegende Datenschutzerklärung erläutert, welche Daten wir erheben und wofür wir sie nutzen. Sie erläutert auch, wie und zu welchem Zweck das geschieht.</p>
                <p className="mt-2">Wir weisen darauf hin, dass die Datenübertragung im Internet (z.B. bei der Kommunikation per E-Mail) Sicherheitslücken aufweisen kann. Ein lückenloser Schutz der Daten vor dem Zugriff durch Dritte ist nicht möglich.</p>
              </div>

              <div>
                <h4 className="font-semibold text-gray-900 mb-1">Hinweis zur verantwortlichen Stelle</h4>
                <p>Die verantwortliche Stelle für die Datenverarbeitung auf dieser Website ist:</p>
                <p className="mt-2">Christian Ecker<br/>Niederbieberer Str. 126<br/>56567 Neuwied</p>
                <p className="mt-2">Telefon: 02631-94 37 37 0</p>
                <p className="mt-2">Verantwortliche Stelle ist die natürliche oder juristische Person, die allein oder gemeinsam mit anderen über die Zwecke und Mittel der Verarbeitung von personenbezogenen Daten (z.B. Namen, E-Mail-Adressen o. Ä.) entscheidet.</p>
              </div>

              <div>
                <h4 className="font-semibold text-gray-900 mb-1">Widerruf Ihrer Einwilligung zur Datenverarbeitung</h4>
                <p>Viele Datenverarbeitungsvorgänge sind nur mit Ihrer ausdrücklichen Einwilligung möglich. Sie können eine bereits erteilte Einwilligung jederzeit widerrufen. Dazu reicht eine formlose Mitteilung per E-Mail an uns. Die Rechtmäßigkeit der bis zum Widerruf erfolgten Datenverarbeitung bleibt vom Widerruf unberührt.</p>
              </div>

              <div>
                <h4 className="font-semibold text-gray-900 mb-1">Beschwerderecht bei der zuständigen Aufsichtsbehörde</h4>
                <p>Im Falle datenschutzrechtlicher Verstöße steht dem Betroffenen ein Beschwerderecht bei der zuständigen Aufsichtsbehörde zu. Zuständige Aufsichtsbehörde in datenschutzrechtlichen Fragen ist der Landesdatenschutzbeauftragte des Bundeslandes, in dem unser Unternehmen seinen Sitz hat. Eine Liste der Datenschutzbeauftragten sowie deren Kontaktdaten können folgendem Link entnommen werden: <a href="https://www.bfdi.bund.de/DE/Infothek/Anschriften_Links/anschriften_links-node.html" target="_blank" rel="noreferrer" className="text-fuchsia-600 hover:underline break-all">https://www.bfdi.bund.de</a>.</p>
              </div>

              <div>
                <h4 className="font-semibold text-gray-900 mb-1">Recht auf Datenübertragbarkeit</h4>
                <p>Sie haben das Recht, Daten, die wir auf Grundlage Ihrer Einwilligung oder in Erfüllung eines Vertrags automatisiert verarbeiten, an sich oder an einen Dritten in einem gängigen, maschinenlesbaren Format aushändigen zu lassen. Sofern Sie die direkte Übertragung der Daten an einen anderen Verantwortlichen verlangen, erfolgt dies nur, soweit es technisch machbar ist.</p>
              </div>

              <div>
                <h4 className="font-semibold text-gray-900 mb-1">SSL- bzw. TLS-Verschlüsselung</h4>
                <p>Diese Seite nutzt aus Sicherheitsgründen und zum Schutz der Übertragung vertraulicher Inhalte, wie zum Beispiel Bestellungen oder Anfragen, die Sie an uns als Seitenbetreiber senden, eine SSL-bzw. TLS-Verschlüsselung. Eine verschlüsselte Verbindung erkennen Sie daran, dass die Adresszeile des Browsers von &quot;http://&quot; auf &quot;https://&quot; wechselt und an dem Schloss-Symbol in Ihrer Browserzeile.</p>
                <p className="mt-2">Wenn die SSL- bzw. TLS-Verschlüsselung aktiviert ist, können die Daten, die Sie an uns übermitteln, nicht von Dritten mitgelesen werden.</p>
              </div>

              <div>
                <h4 className="font-semibold text-gray-900 mb-1">Verschlüsselter Zahlungsverkehr auf dieser Website</h4>
                <p>Besteht nach dem Abschluss eines kostenpflichtigen Vertrags eine Verpflichtung, uns Ihre Zahlungsdaten (z.B. Kontonummer bei Einzugsermächtigung) zu übermitteln, werden diese Daten zur Zahlungsabwicklung benötigt.</p>
                <p className="mt-2">Der Zahlungsverkehr über die gängigen Zahlungsmittel (Visa/MasterCard, Lastschriftverfahren) erfolgt ausschließlich über eine verschlüsselte SSL- bzw. TLS-Verbindung. Eine verschlüsselte Verbindung erkennen Sie daran, dass die Adresszeile des Browsers von &quot;http://&quot; auf &quot;https://&quot; wechselt und an dem Schloss-Symbol in Ihrer Browserzeile.</p>
                <p className="mt-2">Bei verschlüsselter Kommunikation können Ihre Zahlungsdaten, die Sie an uns übermitteln, nicht von Dritten mitgelesen werden.</p>
              </div>

              <div>
                <h4 className="font-semibold text-gray-900 mb-1">Auskunft, Sperrung, Löschung</h4>
                <p>Sie haben im Rahmen der geltenden gesetzlichen Bestimmungen jederzeit das Recht auf unentgeltliche Auskunft über Ihre gespeicherten personenbezogenen Daten, deren Herkunft und Empfänger und den Zweck der Datenverarbeitung und ggf. ein Recht auf Berichtigung, Sperrung oder Löschung dieser Daten. Hierzu sowie zu weiteren Fragen zum Thema personenbezogene Daten können Sie sich jederzeit unter der im Impressum angegebenen Adresse an uns wenden.</p>
              </div>

              <div>
                <h4 className="font-semibold text-gray-900 mb-1">Widerspruch gegen Werbe-Mails</h4>
                <p>Der Nutzung von im Rahmen der Impressumspflicht veröffentlichten Kontaktdaten zur Übersendung von nicht ausdrücklich angeforderter Werbung und Informationsmaterialien wird hiermit widersprochen. Die Betreiber der Seiten behalten sich ausdrücklich rechtliche Schritte im Falle der unverlangten Zusendung von Werbeinformationen, etwa durch Spam-E-Mails, vor.</p>
              </div>

              <div>
                <h3 className="text-base font-semibold text-gray-900 mb-2">3. Datenerfassung auf unserer Website</h3>
                <h4 className="font-semibold text-gray-900 mb-1">Cookies</h4>
                <p>Die Internetseiten verwenden teilweise so genannte Cookies. Cookies richten auf Ihrem Rechner keinen Schaden an und enthalten keine Viren. Cookies dienen dazu, unser Angebot nutzerfreundlicher, effektiver und sicherer zu machen. Cookies sind kleine Textdateien, die auf Ihrem Rechner abgelegt werden und die Ihr Browser speichert.</p>
                <p className="mt-2">Die meisten der von uns verwendeten Cookies sind so genannte &quot;Session-Cookies&quot;. Sie werden nach Ende Ihres Besuchs automatisch gelöscht. Andere Cookies bleiben auf Ihrem Endgerät gespeichert bis Sie diese löschen. Diese Cookies ermöglichen es uns, Ihren Browser beim nächsten Besuch wiederzuerkennen.</p>
                <p className="mt-2">Sie können Ihren Browser so einstellen, dass Sie über das Setzen von Cookies informiert werden und Cookies nur im Einzelfall erlauben, die Annahme von Cookies für bestimmte Fälle oder generell ausschließen sowie das automatische Löschen der Cookies beim Schließen des Browser aktivieren. Bei der Deaktivierung von Cookies kann die Funktionalität dieser Website eingeschränkt sein.</p>
                <p className="mt-2">Cookies, die zur Durchführung des elektronischen Kommunikationsvorgangs oder zur Bereitstellung bestimmter, von Ihnen erwünschter Funktionen (z.B. Warenkorbfunktion) erforderlich sind, werden auf Grundlage von Art. 6 Abs. 1 lit. f DSGVO gespeichert. Der Websitebetreiber hat ein berechtigtes Interesse an der Speicherung von Cookies zur technisch fehlerfreien und optimierten Bereitstellung seiner Dienste. Soweit andere Cookies (z.B. Cookies zur Analyse Ihres Surfverhaltens) gespeichert werden, werden diese in dieser Datenschutzerklärung gesondert behandelt.</p>
              </div>

              <div>
                <h4 className="font-semibold text-gray-900 mb-1">Server-Log-Dateien</h4>
                <p>Der Provider der Seiten erhebt und speichert automatisch Informationen in so genannten Server-Log-Dateien, die Ihr Browser automatisch an uns übermittelt. Dies sind:</p>
                <ul className="list-disc list-inside mt-2 space-y-1 ml-2">
                  <li>Browsertyp und Browserversion</li>
                  <li>verwendetes Betriebssystem</li>
                  <li>Referrer URL</li>
                  <li>Hostname des zugreifenden Rechners</li>
                  <li>Uhrzeit der Serveranfrage</li>
                  <li>IP-Adresse</li>
                </ul>
                <p className="mt-2">Eine Zusammenführung dieser Daten mit anderen Datenquellen wird nicht vorgenommen.</p>
                <p className="mt-2">Grundlage für die Datenverarbeitung ist Art. 6 Abs. 1 lit. f DSGVO, der die Verarbeitung von Daten zur Erfüllung eines Vertrags oder vorvertraglicher Maßnahmen gestattet.</p>
              </div>

              <div>
                <h4 className="font-semibold text-gray-900 mb-1">Kontaktformular</h4>
                <p>Wenn Sie uns per Kontaktformular Anfragen zukommen lassen, werden Ihre Angaben aus dem Anfrageformular inklusive der von Ihnen dort angegebenen Kontaktdaten zwecks Bearbeitung der Anfrage und für den Fall von Anschlussfragen bei uns gespeichert. Diese Daten geben wir nicht ohne Ihre Einwilligung weiter.</p>
                <p className="mt-2">Die Verarbeitung der in das Kontaktformular eingegebenen Daten erfolgt somit ausschließlich auf Grundlage Ihrer Einwilligung (Art. 6 Abs. 1 lit. a DSGVO). Sie können diese Einwilligung jederzeit widerrufen. Dazu reicht eine formlose Mitteilung per E-Mail an uns. Die Rechtmäßigkeit der bis zum Widerruf erfolgten Datenverarbeitungsvorgänge bleibt vom Widerruf unberührt.</p>
                <p className="mt-2">Die von Ihnen im Kontaktformular eingegebenen Daten verbleiben bei uns, bis Sie uns zur Löschung auffordern, Ihre Einwilligung zur Speicherung widerrufen oder der Zweck für die Datenspeicherung entfällt (z.B. nach abgeschlossener Bearbeitung Ihrer Anfrage). Zwingende gesetzliche Bestimmungen – insbesondere Aufbewahrungsfristen – bleiben unberührt.</p>
              </div>

              <div>
                <h3 className="text-base font-semibold text-gray-900 mb-2">4. Analyse Tools und Werbung</h3>
                <h4 className="font-semibold text-gray-900 mb-1">Google Analytics</h4>
                <p>Diese Website nutzt Funktionen des Webanalysedienstes Google Analytics. Anbieter ist die Google Inc., 1600 Amphitheatre Parkway, Mountain View, CA 94043, USA.</p>
                <p className="mt-2">Google Analytics verwendet so genannte &quot;Cookies&quot;. Das sind Textdateien, die auf Ihrem Computer gespeichert werden und die eine Analyse der Benutzung der Website durch Sie ermöglichen. Die durch den Cookie erzeugten Informationen über Ihre Benutzung dieser Website werden in der Regel an einen Server von Google in den USA übertragen und dort gespeichert.</p>
                <p className="mt-2">Die Speicherung von Google-Analytics-Cookies erfolgt auf Grundlage von Art. 6 Abs. 1 lit. f DSGVO. Der Websitebetreiber hat ein berechtigtes Interesse an der Analyse des Nutzerverhaltens, um sowohl sein Webangebot als auch seine Werbung zu optimieren.</p>
              </div>

              <div>
                <p className="font-medium text-gray-800 mb-1">IP Anonymisierung</p>
                <p>Wir haben auf dieser Website die Funktion IP-Anonymisierung aktiviert. Dadurch wird Ihre IP-Adresse von Google innerhalb von Mitgliedstaaten der Europäischen Union oder in anderen Vertragsstaaten des Abkommens über den Europäischen Wirtschaftsraum vor der Übermittlung in die USA gekürzt. Nur in Ausnahmefällen wird die volle IP-Adresse an einen Server von Google in den USA übertragen und dort gekürzt. Im Auftrag des Betreibers dieser Website wird Google diese Informationen benutzen, um Ihre Nutzung der Website auszuwerten, um Reports über die Websiteaktivitäten zusammenzustellen und um weitere mit der Websitenutzung und der Internetnutzung verbundene Dienstleistungen gegenüber dem Websitebetreiber zu erbringen. Die im Rahmen von Google Analytics von Ihrem Browser übermittelte IP-Adresse wird nicht mit anderen Daten von Google zusammengeführt.</p>
              </div>

              <div>
                <p className="font-medium text-gray-800 mb-1">Browser Plugin</p>
                <p>Sie können die Speicherung der Cookies durch eine entsprechende Einstellung Ihrer Browser-Software verhindern; wir weisen Sie jedoch darauf hin, dass Sie in diesem Fall gegebenenfalls nicht sämtliche Funktionen dieser Website vollumfänglich werden nutzen können. Sie können darüber hinaus die Erfassung der durch den Cookie erzeugten und auf Ihre Nutzung der Website bezogenen Daten (inkl. Ihrer IP-Adresse) an Google sowie die Verarbeitung dieser Daten durch Google verhindern, indem Sie das unter dem folgenden Link verfügbare Browser-Plugin herunterladen und installieren: <a href="https://tools.google.com/dlpage/gaoptout?hl=de" target="_blank" rel="noreferrer" className="text-fuchsia-600 hover:underline break-all">https://tools.google.com/dlpage/gaoptout?hl=de</a>.</p>
              </div>

              <div>
                <p className="font-medium text-gray-800 mb-1">Widerspruch gegen Datenerfassung</p>
                <p>Sie können die Erfassung Ihrer Daten durch Google Analytics verhindern, indem Sie auf folgenden Link klicken. Es wird ein Opt-Out-Cookie gesetzt, der die Erfassung Ihrer Daten bei zukünftigen Besuchen dieser Website verhindert: Google Analytics deaktivieren.</p>
                <p className="mt-2">Mehr Informationen zum Umgang mit Nutzerdaten bei Google Analytics finden Sie in der Datenschutzerklärung von Google: <a href="https://support.google.com/analytics/answer/6004245?hl=de" target="_blank" rel="noreferrer" className="text-fuchsia-600 hover:underline break-all">https://support.google.com/analytics/answer/6004245?hl=de</a>.</p>
              </div>

              <div>
                <p className="font-medium text-gray-800 mb-1">Auftragsdatenverarbeitung</p>
                <p>Wir haben mit Google einen Vertrag zur Auftragsdatenverarbeitung abgeschlossen und setzen die strengen Vorgaben der deutschen Datenschutzbehörden bei der Nutzung von Google Analytics vollständig um.</p>
              </div>

              <div>
                <p className="font-medium text-gray-800 mb-1">Demografische Merkmale bei Google Analytics</p>
                <p>Diese Website nutzt die Funktion &quot;demografische Merkmale&quot; von Google Analytics. Dadurch können Berichte erstellt werden, die Aussagen zu Alter, Geschlecht und Interessen der Seitenbesucher enthalten. Diese Daten stammen aus interessenbezogener Werbung von Google sowie aus Besucherdaten von Drittanbietern. Diese Daten können keiner bestimmten Person zugeordnet werden. Sie können diese Funktion jederzeit über die Anzeigeneinstellungen in Ihrem Google-Konto deaktivieren oder die Erfassung Ihrer Daten durch Google Analytics wie im Punkt &quot;Widerspruch gegen Datenerfassung&quot; dargestellt generell untersagen.</p>
              </div>

              <div>
                <h3 className="text-base font-semibold text-gray-900 mb-2">5. Plugins und Tools</h3>
                <h4 className="font-semibold text-gray-900 mb-1">YouTube</h4>
                <p>Unsere Website nutzt Plugins der von Google betriebenen Seite YouTube. Betreiber der Seiten ist die YouTube, LLC, 901 Cherry Ave., San Bruno, CA 94066, USA.</p>
                <p className="mt-2">Wenn Sie eine unserer mit einem YouTube-Plugin ausgestatteten Seiten besuchen, wird eine Verbindung zu den Servern von YouTube hergestellt. Dabei wird dem YouTube-Server mitgeteilt, welche unserer Seiten Sie besucht haben.</p>
                <p className="mt-2">Wenn Sie in Ihrem YouTube-Account eingeloggt sind, ermöglichen Sie YouTube, Ihr Surfverhalten direkt Ihrem persönlichen Profil zuzuordnen. Dies können Sie verhindern, indem Sie sich aus Ihrem YouTube-Account ausloggen.</p>
                <p className="mt-2">Die Nutzung von YouTube erfolgt im Interesse einer ansprechenden Darstellung unserer Online-Angebote. Dies stellt ein berechtigtes Interesse im Sinne von Art. 6 Abs. 1 lit. f DSGVO dar.</p>
                <p className="mt-2">Weitere Informationen zum Umgang mit Nutzerdaten finden Sie in der Datenschutzerklärung von YouTube unter: <a href="https://www.google.de/intl/de/policies/privacy" target="_blank" rel="noreferrer" className="text-fuchsia-600 hover:underline break-all">https://www.google.de/intl/de/policies/privacy</a>.</p>
              </div>

              <div>
                <h4 className="font-semibold text-gray-900 mb-1">Google Web Fonts</h4>
                <p>Diese Seite nutzt zur einheitlichen Darstellung von Schriftarten so genannte Web Fonts, die von Google bereitgestellt werden. Beim Aufruf einer Seite lädt Ihr Browser die benötigten Web Fonts in ihren Browsercache, um Texte und Schriftarten korrekt anzuzeigen.</p>
                <p className="mt-2">Zu diesem Zweck muss der von Ihnen verwendete Browser Verbindung zu den Servern von Google aufnehmen. Hierdurch erlangt Google Kenntnis darüber, dass über Ihre IP-Adresse unsere Website aufgerufen wurde. Die Nutzung von Google Web Fonts erfolgt im Interesse einer einheitlichen und ansprechenden Darstellung unserer Online-Angebote. Dies stellt ein berechtigtes Interesse im Sinne von Art. 6 Abs. 1 lit. f DSGVO dar.</p>
                <p className="mt-2">Wenn Ihr Browser Web Fonts nicht unterstützt, wird eine Standardschrift von Ihrem Computer genutzt.</p>
                <p className="mt-2">Weitere Informationen zu Google Web Fonts finden Sie unter <a href="https://developers.google.com/fonts/faq" target="_blank" rel="noreferrer" className="text-fuchsia-600 hover:underline">https://developers.google.com/fonts/faq</a> und in der Datenschutzerklärung von Google: <a href="https://www.google.com/policies/privacy/" target="_blank" rel="noreferrer" className="text-fuchsia-600 hover:underline">https://www.google.com/policies/privacy/</a>.</p>
              </div>

              <div>
                <h4 className="font-semibold text-gray-900 mb-1">Google Maps</h4>
                <p>Diese Seite nutzt über eine API den Kartendienst Google Maps. Anbieter ist die Google Inc., 1600 Amphitheatre Parkway, Mountain View, CA 94043, USA.</p>
                <p className="mt-2">Zur Nutzung der Funktionen von Google Maps ist es notwendig, Ihre IP Adresse zu speichern. Diese Informationen werden in der Regel an einen Server von Google in den USA übertragen und dort gespeichert. Der Anbieter dieser Seite hat keinen Einfluss auf diese Datenübertragung.</p>
                <p className="mt-2">Die Nutzung von Google Maps erfolgt im Interesse einer ansprechenden Darstellung unserer Online-Angebote und an einer leichten Auffindbarkeit der von uns auf der Website angegebenen Orte. Dies stellt ein berechtigtes Interesse im Sinne von Art. 6 Abs. 1 lit. f DSGVO dar.</p>
                <p className="mt-2">Mehr Informationen zum Umgang mit Nutzerdaten finden Sie in der Datenschutzerklärung von Google: <a href="https://www.google.de/intl/de/policies/privacy/" target="_blank" rel="noreferrer" className="text-fuchsia-600 hover:underline break-all">https://www.google.de/intl/de/policies/privacy/</a>.</p>
              </div>

            </div>
          </div>
        </div>
      )}

      {/* Impressum Modal */}
      {showImpressum && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4" onClick={() => setShowImpressum(false)} data-testid="impressum-modal">
          <div className="bg-white rounded-xl shadow-xl max-w-lg w-full max-h-[85vh] overflow-hidden" onClick={e => e.stopPropagation()}>
            <div className="p-4 border-b border-gray-200 flex items-center justify-between">
              <h2 className="font-semibold text-gray-900">Impressum</h2>
              <button onClick={() => setShowImpressum(false)} className="text-gray-400 hover:text-gray-600" data-testid="impressum-close"><X className="w-5 h-5" /></button>
            </div>
            <div className="p-5 overflow-y-auto max-h-[70vh] space-y-4 text-sm text-gray-700">
              <div>
                <p className="text-xs text-gray-500 mb-2">Diensteanbieter:</p>
                <p className="font-semibold text-gray-900">Eventenergie Deutschland GmbH & Co. KG</p>
                <p>Geschäftsführung: Christian Ecker</p>
              </div>
              <div>
                <p>Thyssenstraße 10</p>
                <p>56626 Andernach</p>
                <p className="mt-2">Tel.: 02632 30921 0</p>
                <p className="mt-1"><a href="mailto:info@eventenergie-deutschland.de" className="text-fuchsia-600 hover:underline">info@eventenergie-deutschland.de</a></p>
                <p><a href="https://www.eventenergie-deutschland.de" target="_blank" rel="noreferrer" className="text-fuchsia-600 hover:underline">www.eventenergie-deutschland.de</a></p>
              </div>
              <div>
                <p className="font-semibold text-gray-900 mb-1">Verantwortlich für den Inhalt</p>
                <p>Christian Ecker, Thyssenstraße 10, 56626 Andernach</p>
              </div>
              <div>
                <p className="font-semibold text-gray-900 mb-1">Umsatzsteuer-ID</p>
                <p>Umsatzsteuer-Identifikationsnummer gemäß §27 a Umsatzsteuergesetz: DE29/200/02826</p>
                <p>Steuer-ID: DE333489815</p>
                <p className="mt-1">Finanzamt Mayen</p>
              </div>
              <div>
                <p className="font-semibold text-gray-900 mb-1">Handelsregister</p>
                <p>Handelsregister Nummer: HRA 22723</p>
                <p>Amtsgericht Koblenz</p>
              </div>
              <div>
                <p className="font-semibold text-gray-900 mb-1">Persönlich haftende Gesellschafterin / Komplementärin</p>
                <p>ES Verwaltungs GmbH</p>
                <p>Sitz: Andernach</p>
                <p>Registergericht: Koblenz HR B 26935</p>
                <p>Geschäftsführer: Christian Ecker</p>
              </div>
              <div>
                <p>Herr Christian Ecker ist Elektrotechnikermeister (gesetzliche Berufsbezeichnung), verliehen in der Bundesrepublik Deutschland. Herr Christian Ecker ist Mitglied der Handwerkskammer Koblenz.</p>
              </div>
              <div>
                <p className="font-semibold text-gray-900 mb-1">Berufsrechtliche Regelungen</p>
                <p>Handwerksordnung, einsehbar u.a. unter <a href="http://www.gesetze-im-internet.de/bundesrecht/hwo/gesamt.pdf" target="_blank" rel="noreferrer" className="text-fuchsia-600 hover:underline">www.gesetze-im-internet.de</a></p>
              </div>
              <div>
                <p className="font-semibold text-gray-900 mb-1">Copyright</p>
                <p>Alle auf unseren Seiten enthaltenen Fotos sind urheberrechtlich geschützt und dürfen nicht kopiert werden.</p>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
